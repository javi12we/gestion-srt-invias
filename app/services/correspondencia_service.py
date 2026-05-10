from datetime import datetime, timezone
from typing import Dict, List, Optional
from bson import ObjectId

from app.repositories.correspondencia_repo import CorrespondenciaRepositorio


class CorrespondenciaService:
    def __init__(self) -> None:
        self.repo = CorrespondenciaRepositorio()

    def listar_correspondencia(self, id_usuario: Optional[str] = None, ver_todas: bool = False, skip: int = 0, limit: int = 10) -> tuple[List[Dict], int]:
        """
        Lista las correspondencias. Si ver_todas es True, devuelve todas.
        Si ver_todas es False y se provee id_usuario, devuelve las asignadas a ese usuario.
        Retorna una tupla: (lista_documentos, total_documentos)
        """
        if ver_todas:
            return self.repo.listar_todas(skip, limit), self.repo.contar_todas()
        if id_usuario:
            return self.repo.listar_por_responsable(id_usuario, skip, limit), self.repo.contar_por_responsable(id_usuario)
        return [], 0

    def buscar_por_id(self, id_correspondencia: str) -> Optional[Dict]:
        return self.repo.buscar_por_id(id_correspondencia)

    def crear_correspondencia(self, datos: dict, usuario_ejecutor_nombre: str) -> str:
        fecha_actual = datetime.now(timezone.utc)
        
        datos["fecha_radicacion"] = fecha_actual
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
        # Solo se permite actualizar campos básicos, no estado ni trazabilidad
        campos_permitidos = ["numero_radicado", "asunto", "peticionario", "fecha_vencimiento", "tipo", "grupo", "clase", "observaciones_generales"]
        campos_a_actualizar = {k: v for k, v in datos_actualizados.items() if k in campos_permitidos}
        
        if not campos_a_actualizar:
            return False
            
        evento_trazabilidad = {
            "fecha": datetime.now(timezone.utc),
            "tipo_evento": "cambio_estado", # No hay un evento "edicion", usamos uno genérico o adaptamos si el schema cambia
            "usuario_ejecutor": usuario_ejecutor_nombre,
            "estado_anterior": None, # No cambia el estado
            "estado_nuevo": None,    # No cambia el estado
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
        comentario: str = "Se dio respuesta al radicado"
    ) -> bool:
        correspondencia = self.repo.buscar_por_id(id_correspondencia)
        if not correspondencia:
            return False

        fecha_actual = datetime.now(timezone.utc)
        estado_anterior = correspondencia.get("estado_actual")
        nuevo_estado = "respondido"
        
        campos_actualizar = {
            "estado_actual": nuevo_estado,
            "respuesta": {
                "numero_oficio": numero_oficio,
                "fecha_salida": fecha_actual
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
