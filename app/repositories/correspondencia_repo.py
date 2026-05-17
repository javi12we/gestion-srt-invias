from bson import ObjectId

from app.db.mongo import obtener_coleccion


class CorrespondenciaRepositorio:
    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("correspondencia")

    def buscar_por_id(self, id_correspondencia: str):
        return self.coleccion.find_one({"_id": ObjectId(id_correspondencia)})
    
    def buscar_por_radicado(self, numero_radicado: str):
        import re
        return self.coleccion.find_one({
            "numero_radicado": {"$regex": f"^{re.escape(numero_radicado)}$", "$options": "i"}
        })

    def listar(self, query: dict = None, skip: int = 0, limit: int = 10):
        q = query or {}
        return list(self.coleccion.find(q).sort("fecha_radicacion", -1).skip(skip).limit(limit))
        
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
