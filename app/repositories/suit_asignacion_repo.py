from bson import ObjectId

from app.db.mongo import obtener_coleccion


class SuitAsignacionRepositorio:
    """Acceso a 'suit_asignaciones' (quién puede diligenciar cada trámite SUIT)."""

    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("suit_asignaciones")

    def listar_activas(self) -> list[dict]:
        return list(self.coleccion.find({"estado": "activo"}))

    def listar_activas_por_usuario(self, usuario_id: str) -> list[dict]:
        return list(self.coleccion.find({"usuario_id": ObjectId(usuario_id), "estado": "activo"}))

    def listar_activas_por_tramite(self, tramite: str) -> list[dict]:
        return list(self.coleccion.find({"tramite": tramite, "estado": "activo"}).sort("fecha_asignacion", 1))

    def obtener_activa(self, usuario_id: str, tramite: str):
        return self.coleccion.find_one(
            {"usuario_id": ObjectId(usuario_id), "tramite": tramite, "estado": "activo"}
        )

    def insertar(self, doc: dict):
        return self.coleccion.insert_one(doc).inserted_id

    def retirar(self, asignacion_id, cambios: dict, entrada_trazabilidad: dict) -> bool:
        """Marca como retirada una asignación que siga activa. True si la modificó."""
        resultado = self.coleccion.update_one(
            {"_id": asignacion_id, "estado": "activo"},
            {"$set": cambios, "$push": {"trazabilidad": entrada_trazabilidad}},
        )
        return resultado.modified_count == 1
