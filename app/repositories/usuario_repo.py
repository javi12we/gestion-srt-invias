from datetime import datetime, timezone

from bson import ObjectId

from app.db.mongo import obtener_coleccion


class UsuarioRepositorio:
    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("usuarios")
        self.roles = obtener_coleccion("roles")
        self.permisos = obtener_coleccion("permisos")

    def buscar_por_usuario(self, usuario: str):
        return self.coleccion.find_one({"usuario": usuario})

    def buscar_por_id(self, id_usuario: str):
        return self.coleccion.find_one({"_id": ObjectId(id_usuario)})

    def buscar_por_numero_documento(self, numero_documento: str):
        return self.coleccion.find_one({"numero_documento": numero_documento})

    def buscar_por_numero_contrato(self, numero: str, excluir_id: str = None):
        query = {"contratos.numero": numero}
        if excluir_id:
            query["_id"] = {"$ne": ObjectId(excluir_id)}
        return self.coleccion.find_one(query)

    def agregar_contrato_a_usuario(self, id_usuario: str, contrato: dict):
        self.coleccion.update_one(
            {"_id": ObjectId(id_usuario)},
            {
                "$push": {"contratos": contrato},
                "$set": {"fecha_actualizacion": datetime.now(timezone.utc)},
            },
        )

    def editar_contrato_en_usuario(self, id_usuario: str, numero_contrato: str, nuevo_contrato: dict):
        self.coleccion.update_one(
            {"_id": ObjectId(id_usuario), "contratos.numero": numero_contrato},
            {
                "$set": {
                    "contratos.$": nuevo_contrato,
                    "fecha_actualizacion": datetime.now(timezone.utc),
                }
            },
        )

    def listar(self):
        return list(self.coleccion.find({}, {"password_hash": 0}).sort("usuario", 1))

    def listar_por_grupo_trabajo(self, grupo: str):
        return list(
            self.coleccion.find(
                {"informacion_laboral.grupo_trabajo": grupo}, {"password_hash": 0}
            ).sort("usuario", 1)
        )

    def crear(self, datos: dict):
        datos["fecha_creacion"] = datetime.now(timezone.utc)
        datos["fecha_actualizacion"] = datetime.now(timezone.utc)
        return self.coleccion.insert_one(datos).inserted_id

    def actualizar(self, id_usuario: str, datos: dict):
        datos["fecha_actualizacion"] = datetime.now(timezone.utc)
        return self.coleccion.update_one({"_id": ObjectId(id_usuario)}, {"$set": datos})

    def cambiar_estado(self, id_usuario: str, activo: bool):
        return self.coleccion.update_one(
            {"_id": ObjectId(id_usuario)},
            {"$set": {"activo": activo, "fecha_actualizacion": datetime.now(timezone.utc)}},
        )

    def listar_roles(self):
        return list(self.roles.find().sort("nombre", 1))

    def listar_permisos(self):
        return list(self.permisos.find().sort("clave", 1))
