from app.core.catalogos import PERMISOS_BASE, ROLES_BASE
from app.db.mongo import obtener_coleccion


class CatalogoService:
    def __init__(self) -> None:
        self.coleccion_permisos = obtener_coleccion("permisos")
        self.coleccion_roles = obtener_coleccion("roles")

    def asegurar_catalogos_base(self) -> None:
        for permiso in PERMISOS_BASE:
            self.coleccion_permisos.update_one(
                {"clave": permiso["clave"]},
                {"$setOnInsert": permiso},
                upsert=True,
            )

        for rol in ROLES_BASE:
            self.coleccion_roles.update_one(
                {"nombre": rol["nombre"]},
                {"$set": rol},
                upsert=True,
            )
