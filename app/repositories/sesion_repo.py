from datetime import datetime, timezone

from bson import ObjectId

from app.db.mongo import obtener_coleccion


class SesionRepositorio:
    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("sesiones")

    def crear(self, datos: dict):
        registro = datos.copy()
        registro.setdefault("fecha_inicio", datetime.now(timezone.utc))
        registro.setdefault("estado", "activa")
        return self.coleccion.insert_one(registro).inserted_id

    def buscar_por_id_sesion(self, id_sesion: str):
        return self.coleccion.find_one({"id_sesion": id_sesion})

    def listar(self, filtro: dict = None, limite: int = 200):
        filtro = filtro or {}
        return list(self.coleccion.find(filtro).sort("fecha_inicio", -1).limit(limite))

    def cerrar_sesiones_previas(self, id_usuario: str, motivo: str = "nueva_sesion") -> int:
        """Cierra todas las sesiones activas previas de un usuario (evita sesiones fantasma)."""
        fecha_cierre = datetime.now(timezone.utc)
        # Buscar sesiones activas previas para calcular duración
        sesiones_activas = list(self.coleccion.find({
            "id_usuario": id_usuario,
            "estado": "activa"
        }))
        
        # Cerrar todas
        resultado = self.coleccion.update_many(
            {
                "id_usuario": id_usuario,
                "estado": "activa"
            },
            {
                "$set": {
                    "estado": "cerrada",
                    "motivo_cierre": motivo,
                    "fecha_cierre": fecha_cierre,
                }
            },
        )
        
        # Calcular duración para cada una (basada en fecha_inicio)
        for sesion in sesiones_activas:
            fecha_inicio = sesion.get("fecha_inicio")
            if not fecha_inicio:
                continue
            
            # Asegurar que fecha_inicio sea offset-aware (agregar UTC si es naive)
            if fecha_inicio.tzinfo is None:
                fecha_inicio = fecha_inicio.replace(tzinfo=timezone.utc)
            
            duracion = int((fecha_cierre - fecha_inicio).total_seconds())
            self.coleccion.update_one(
                {"_id": sesion["_id"]},
                {"$set": {"duracion_segundos": duracion}}
            )
        
        return resultado.modified_count

    def cerrar(self, id_sesion: str, motivo_cierre: str, duracion_segundos: int = None):
        """Cierra una sesión: marca como cerrada con fecha y duración."""
        sesion = self.buscar_por_id_sesion(id_sesion)
        if not sesion:
            return None

        fecha_cierre = datetime.now(timezone.utc)
        return self.coleccion.update_one(
            {"id_sesion": id_sesion},
            {
                "$set": {
                    "estado": "cerrada",
                    "motivo_cierre": motivo_cierre,
                    "fecha_cierre": fecha_cierre,
                    "duracion_segundos": duracion_segundos,
                }
            },
        )
