from bson import ObjectId

from app.db.mongo import obtener_coleccion


class CorrespondenciaRepositorio:
    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("correspondencia")

    def buscar_por_id(self, id_correspondencia: str):
        return self.coleccion.find_one({"_id": ObjectId(id_correspondencia)})
    
    def buscar_por_radicado(self, numero_radicado: str):
        normalizado = (numero_radicado or "").replace(" ", "").upper()
        return self.coleccion.find_one({"numero_radicado": normalizado})

    def listar(self, query: dict = None, skip: int = 0, limit: int = 10, projection: dict = None):
        q = query or {}
        return list(
            self.coleccion.find(q, projection)
            .sort("fecha_radicacion", -1)
            .skip(max(0, skip))
            .limit(limit)
        )
        
    def listar_abiertas_con_vencimiento_hasta(self, fecha_limite, estados_cerrados: list):
        """Radicados sin cerrar, con responsable asignado, que vencen hasta
        `fecha_limite` (incluye los ya vencidos). Solo los campos del aviso."""
        return list(
            self.coleccion.find(
                {
                    "estado_actual": {"$nin": estados_cerrados},
                    "responsable_actual.usuario_id": {"$exists": True},
                    "fecha_vencimiento": {"$lte": fecha_limite},
                },
                {"numero_radicado": 1, "asunto": 1, "fecha_vencimiento": 1, "responsable_actual.usuario_id": 1},
            )
        )

    def contar(self, query: dict = None):
        q = query or {}
        return self.coleccion.count_documents(q)

    def crear(self, datos: dict):
        return self.coleccion.insert_one(datos).inserted_id

    def actualizar_con_trazabilidad(self, id_correspondencia: str, campos_actualizar: dict, evento_trazabilidad: dict):
        """
        Actualiza los campos de la correspondencia y añade el evento de trazabilidad
        en una sola operación atómica.
        """
        update_doc = {}
        
        if campos_actualizar:
            update_doc["$set"] = campos_actualizar
            
        update_doc["$push"] = {"trazabilidad": evento_trazabilidad}
        
        return self.coleccion.update_one(
            {"_id": ObjectId(id_correspondencia)},
            update_doc
        )
