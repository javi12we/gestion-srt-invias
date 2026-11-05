from bson import ObjectId

from app.db.mongo import obtener_coleccion


class AsignacionGrupoRepositorio:
    """Acceso a la colección 'asignaciones_grupo' (pertenencia de usuarios a grupos)."""

    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("asignaciones_grupo")

    def listar_por_usuario(self, usuario_id: str, solo_activas: bool = False) -> list[dict]:
        filtro = {"usuario_id": ObjectId(usuario_id)}
        if solo_activas:
            filtro["estado"] = "activo"
        return list(self.coleccion.find(filtro).sort("fecha_ingreso", -1))

    def listar_por_grupo(self, grupo_clave: str, estado: str | None = None) -> list[dict]:
        filtro = {"grupo_clave": grupo_clave}
        if estado:
            filtro["estado"] = estado
        return list(self.coleccion.find(filtro).sort("fecha_ingreso", -1))

    def obtener_activa(self, usuario_id: str, grupo_clave: str):
        return self.coleccion.find_one(
            {"usuario_id": ObjectId(usuario_id), "grupo_clave": grupo_clave, "estado": "activo"}
        )

    def listar_activas(self) -> list[dict]:
        return list(self.coleccion.find({"estado": "activo"}))

    def definir_lider(self, asignacion_id, es_lider: bool, entrada_trazabilidad: dict) -> bool:
        """Marca/desmarca el liderazgo de una asignación que siga activa."""
        resultado = self.coleccion.update_one(
            {"_id": asignacion_id, "estado": "activo"},
            {"$set": {"es_lider": es_lider}, "$push": {"trazabilidad": entrada_trazabilidad}},
        )
        return resultado.matched_count == 1

    def insertar(self, doc: dict):
        return self.coleccion.insert_one(doc).inserted_id

    def retirar(self, asignacion_id, cambios: dict, entrada_trazabilidad: dict) -> bool:
        """Marca como retirada una asignación que siga activa. True si la modificó."""
        resultado = self.coleccion.update_one(
            {"_id": asignacion_id, "estado": "activo"},
            {"$set": cambios, "$push": {"trazabilidad": entrada_trazabilidad}},
        )
        return resultado.modified_count == 1
