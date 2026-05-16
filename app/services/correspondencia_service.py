from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import holidays
import re
from bson import ObjectId

from app.repositories.correspondencia_repo import CorrespondenciaRepositorio


class CorrespondenciaService:
    def __init__(self) -> None:
        self.repo = CorrespondenciaRepositorio()
        self.festivos_co = holidays.CO()

    def listar_correspondencia(self, id_usuario: Optional[str] = None, ver_todas: bool = False, skip: int = 0, limit: int = 10, filtros: dict = None) -> tuple[List[Dict], int]:
        """
        Lista las correspondencias. Si ver_todas es True, devuelve todas.
        Si ver_todas es False y se provee id_usuario, devuelve las asignadas a ese usuario.
        Retorna una tupla: (lista_documentos, total_documentos)
        """
        query = {}
        if not ver_todas and id_usuario:
            query["responsable_actual.usuario_id"] = id_usuario
            
        if filtros:
            # Estado
            if "estado" in filtros and filtros["estado"] != "Todos":
                query["estado_actual"] = filtros["estado"]
            
            # Grupo
            if "grupo" in filtros and filtros["grupo"] != "Todos":
                query["grupo"] = filtros["grupo"]
            
            # Vencimiento (Solo aplica para activas si es que no hemos filtrado por estado ya cerrado)
            if "vencimiento" in filtros and filtros["vencimiento"] != "Todos":
                hoy_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                hoy = datetime.strptime(hoy_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                
                # Para filtros de vencimiento, excluimos los cerrados si el usuario no especificó un estado
                if "estado" not in filtros or filtros["estado"] == "Todos":
                    query["estado_actual"] = {"$nin": ["respondido", "archivado", "traslado_competencia"]}
                    
                venc_filtro = filtros["vencimiento"]
                if venc_filtro == "Vencidas":
                    query["fecha_vencimiento"] = {"$lt": hoy}
                elif venc_filtro == "Vencen Hoy":
                    query["fecha_vencimiento"] = {"$gte": hoy, "$lt": hoy + timedelta(days=1)}
                elif venc_filtro == "Próximas a Vencer":
                    # Ahora es hasta 5 días
                    query["fecha_vencimiento"] = {"$gte": hoy + timedelta(days=1), "$lte": hoy + timedelta(days=5)}
                elif venc_filtro == "A Tiempo":
                    query["fecha_vencimiento"] = {"$gt": hoy + timedelta(days=5)}

            # Filtro por responsable (para coordinadores/admin)
            if "responsable_id" in filtros and filtros["responsable_id"] != "Todos":
                query["responsable_actual.usuario_id"] = filtros["responsable_id"]

            if "busqueda" in filtros and filtros["busqueda"]:
                busqueda_escapada = re.escape(filtros["busqueda"])
                query["numero_radicado"] = {"$regex": busqueda_escapada, "$options": "i"}


        return self.repo.listar(query, skip, limit), self.repo.contar(query)

    def buscar_por_id(self, id_correspondencia: str) -> Optional[Dict]:
        return self.repo.buscar_por_id(id_correspondencia)

    def _agregar_dias_habiles(self, fecha_inicial: datetime, dias: int) -> datetime:
        fecha_actual = fecha_inicial
        dias_agregados = 0
        
        # Si el día de inicio es hábil, se cuenta como el primer día
        if fecha_actual.weekday() < 5 and fecha_actual not in self.festivos_co:
            dias_agregados = 1
            
        while dias_agregados < dias:
            fecha_actual += timedelta(days=1)
            # 0 = Lunes, ..., 4 = Viernes. Además se verifica si es festivo en Colombia
            if fecha_actual.weekday() < 5 and fecha_actual not in self.festivos_co:
                dias_agregados += 1
        return fecha_actual

    def crear_correspondencia(self, datos: dict, usuario_ejecutor_nombre: str) -> str:
        fecha_actual = datetime.now(timezone.utc)
        
        # Si no se provee fecha_radicacion, usar la actual
        if "fecha_radicacion" not in datos or not datos["fecha_radicacion"]:
            datos["fecha_radicacion"] = fecha_actual
            
        # Calcular fecha de vencimiento sumando 10 días hábiles
        datos["fecha_vencimiento"] = self._agregar_dias_habiles(datos["fecha_radicacion"], 10)
        
        datos["estado_actual"] = "pendiente"
        
        # Generar trazabilidad inicial
        evento_trazabilidad = {
            "fecha": fecha_actual,
            "tipo_evento": "radicacion",
            "usuario_ejecutor": usuario_ejecutor_nombre,
            "estado_anterior": None,
            "estado_nuevo": "pendiente",
            "comentario": "Ingreso de correspondencia al sistema"
        }
        datos["trazabilidad"] = [evento_trazabilidad]
        
        # Validamos que no tenga responsable todavía o respuesta
        if "responsable_actual" in datos:
            del datos["responsable_actual"]
        if "respuesta" in datos:
            del datos["respuesta"]

        return str(self.repo.crear(datos))
        
    def editar_correspondencia(self, id_correspondencia: str, datos_actualizados: dict, usuario_ejecutor_nombre: str) -> bool:
        """Permite editar campos básicos del radicado."""
        # Obtener el radicado actual para conocer su estado y validar existencia
        correspondencia = self.repo.buscar_por_id(id_correspondencia)
        if not correspondencia:
            return False
            
        estado_actual = correspondencia.get("estado_actual", "pendiente")
        
        # Solo se permite actualizar campos básicos, no estado ni trazabilidad
        campos_permitidos = ["numero_radicado", "asunto", "peticionario", "fecha_vencimiento", "tipo", "grupo", "clase", "observaciones_generales"]
        campos_a_actualizar = {k: v for k, v in datos_actualizados.items() if k in campos_permitidos}
        
        if not campos_a_actualizar:
            return False
            
        evento_trazabilidad = {
            "fecha": datetime.now(timezone.utc),
            "tipo_evento": "cambio_estado", 
            "usuario_ejecutor": usuario_ejecutor_nombre,
            "estado_anterior": estado_actual,
            "estado_nuevo": estado_actual, # Mantener el mismo estado para cumplir con el esquema (string requerido)
            "comentario": "Se actualizaron los datos básicos del radicado"
        }
        
        resultado = self.repo.actualizar_con_trazabilidad(id_correspondencia, campos_a_actualizar, evento_trazabilidad)
        return resultado.modified_count > 0

    def asignar_correspondencia(
        self, 
        id_correspondencia: str, 
        nuevo_responsable_id: str, 
        nuevo_responsable_nombre: str, 
        usuario_ejecutor_nombre: str,
        comentario: str = "Asignación de correspondencia"
    ) -> bool:
        correspondencia = self.repo.buscar_por_id(id_correspondencia)
        if not correspondencia:
            return False

        fecha_actual = datetime.now(timezone.utc)
        estado_anterior = correspondencia.get("estado_actual")
        responsable_anterior = correspondencia.get("responsable_actual", {}).get("nombre")
        
        # Si estaba pendiente, al asignar pasa a en_tramite
        nuevo_estado = "en_tramite" if estado_anterior == "pendiente" else estado_anterior
        
        campos_actualizar = {
            "responsable_actual": {
                "usuario_id": str(nuevo_responsable_id),
                "nombre": nuevo_responsable_nombre,
                "fecha_asignacion": fecha_actual
            },
            "estado_actual": nuevo_estado
        }

        evento_trazabilidad = {
            "fecha": fecha_actual,
            "tipo_evento": "asignacion" if not responsable_anterior else "reasignacion",
            "usuario_ejecutor": usuario_ejecutor_nombre,
            "estado_anterior": estado_anterior,
            "estado_nuevo": nuevo_estado,
            "responsable_nuevo": nuevo_responsable_nombre,
            "comentario": comentario
        }
        
        if responsable_anterior:
            evento_trazabilidad["responsable_anterior"] = responsable_anterior

        resultado = self.repo.actualizar_con_trazabilidad(id_correspondencia, campos_actualizar, evento_trazabilidad)
        return resultado.modified_count > 0

    def cambiar_estado(self, id_correspondencia: str, nuevo_estado: str, usuario_ejecutor_nombre: str, comentario: str) -> bool:
        correspondencia = self.repo.buscar_por_id(id_correspondencia)
        if not correspondencia:
            return False

        estado_anterior = correspondencia.get("estado_actual")
        if estado_anterior == nuevo_estado:
            return False

        campos_actualizar = {"estado_actual": nuevo_estado}
        
        evento_trazabilidad = {
            "fecha": datetime.now(timezone.utc),
            "tipo_evento": "cambio_estado",
            "usuario_ejecutor": usuario_ejecutor_nombre,
            "estado_anterior": estado_anterior,
            "estado_nuevo": nuevo_estado,
            "comentario": comentario
        }

        resultado = self.repo.actualizar_con_trazabilidad(id_correspondencia, campos_actualizar, evento_trazabilidad)
        return resultado.modified_count > 0

    def dar_respuesta(
        self, 
        id_correspondencia: str, 
        numero_oficio: str, 
        usuario_ejecutor_nombre: str, 
        comentario: str = "Se dio respuesta al radicado",
        fecha_respuesta: Optional[datetime] = None
    ) -> bool:
        correspondencia = self.repo.buscar_por_id(id_correspondencia)
        if not correspondencia:
            return False

        fecha_actual = datetime.now(timezone.utc)
        fecha_salida = fecha_respuesta if fecha_respuesta else fecha_actual
        estado_anterior = correspondencia.get("estado_actual")
        nuevo_estado = "respondido"
        
        campos_actualizar = {
            "estado_actual": nuevo_estado,
            "respuesta": {
                "numero_oficio": numero_oficio,
                "fecha_salida": fecha_salida
            }
        }

        
        evento_trazabilidad = {
            "fecha": fecha_actual,
            "tipo_evento": "carga_respuesta",
            "usuario_ejecutor": usuario_ejecutor_nombre,
            "estado_anterior": estado_anterior,
            "estado_nuevo": nuevo_estado,
            "comentario": comentario
        }

        resultado = self.repo.actualizar_con_trazabilidad(id_correspondencia, campos_actualizar, evento_trazabilidad)
        return resultado.modified_count > 0

    def archivar(self, id_correspondencia: str, usuario_ejecutor_nombre: str, comentario: str = "Se archivó el radicado") -> bool:
        correspondencia = self.repo.buscar_por_id(id_correspondencia)
        if not correspondencia:
            return False

        estado_anterior = correspondencia.get("estado_actual")
        nuevo_estado = "archivado"
        
        campos_actualizar = {
            "estado_actual": nuevo_estado
        }
        
        evento_trazabilidad = {
            "fecha": datetime.now(timezone.utc),
            "tipo_evento": "cierre",
            "usuario_ejecutor": usuario_ejecutor_nombre,
            "estado_anterior": estado_anterior,
            "estado_nuevo": nuevo_estado,
            "comentario": comentario
        }

        resultado = self.repo.actualizar_con_trazabilidad(id_correspondencia, campos_actualizar, evento_trazabilidad)
        return resultado.modified_count > 0

    def obtener_metricas_dashboard(self, id_usuario: Optional[str] = None) -> dict:
        """Obtiene métricas rápidas para el dashboard del usuario o generales."""
        hoy = datetime.now(timezone.utc)
        
        # Base de consulta (si hay usuario, solo lo asignado a él; si no, todo lo activo)
        query_activos = {"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}}
        if id_usuario:
            query_activos["responsable_actual.usuario_id"] = id_usuario
            
        # Vencidos o por vencer en menos de 5 días
        query_urgentes = query_activos.copy()
        query_urgentes["fecha_vencimiento"] = {"$lte": hoy + timedelta(days=5)}

        
        # Recién asignados (últimas 48h)
        hace_48h = hoy - timedelta(days=2)
        query_recientes = query_activos.copy()
        # Nota: La fecha de radicación es la que tenemos más a mano
        query_recientes["fecha_radicacion"] = {"$gte": hace_48h}

        return {
            "pendientes": self.repo.contar(query_activos),
            "urgentes": self.repo.contar(query_urgentes),
            "recientes": self.repo.contar(query_recientes)
        }

