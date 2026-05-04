from datetime import datetime, timezone

from bson import ObjectId

from app.db.mongo import obtener_coleccion


class RolRepositorio:
    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("roles")

    def listar(self):
        return list(self.coleccion.find().sort("nombre", 1))

    def buscar_por_nombre(self, nombre: str):
        return self.coleccion.find_one({"nombre": nombre})

    def buscar_por_id(self, id_rol: str):
        return self.coleccion.find_one({"_id": ObjectId(id_rol)})

    def crear(self, datos: dict):
        datos = datos.copy()
        datos.setdefault("activo", True)
        datos.setdefault("permisos", [])
        datos["fecha_creacion"] = datetime.now(timezone.utc)
        datos["fecha_actualizacion"] = datetime.now(timezone.utc)
        return self.coleccion.insert_one(datos).inserted_id

    def actualizar(self, id_rol: str, datos: dict):
        datos = datos.copy()
        datos["fecha_actualizacion"] = datetime.now(timezone.utc)
        return self.coleccion.update_one({"_id": ObjectId(id_rol)}, {"$set": datos})

    def cambiar_estado(self, id_rol: str, activo: bool):
        return self.coleccion.update_one(
            {"_id": ObjectId(id_rol)},
            {"$set": {"activo": activo, "fecha_actualizacion": datetime.now(timezone.utc)}},
        )
