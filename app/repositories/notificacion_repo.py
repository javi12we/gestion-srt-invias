from datetime import datetime

from bson import ObjectId

from app.db.mongo import obtener_coleccion


class NotificacionRepositorio:
    """Registro de lo que ya se notificó por correo, para no repetir avisos.

    Un documento por (usuario, tipo, clave) con la fecha del último envío:
    - tipo "correspondencia", clave = fecha ISO del día avisado.
    - tipo "formatos", clave = "AAAA-MM" del período avisado.
    - tipo "firmas", clave = id de la certificación.
    """

    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("notificaciones_correo")

    def fecha_envio(self, usuario_id: str, tipo: str, clave: str) -> datetime | None:
        doc = self.coleccion.find_one(
            {"usuario_id": ObjectId(usuario_id), "tipo": tipo, "clave": clave}, {"fecha_envio": 1}
        )
        return doc.get("fecha_envio") if doc else None

    def eliminar_anteriores_a(self, fecha: datetime) -> int:
        """Borra las marcas de avisos enviados antes de `fecha`; devuelve cuántas."""
        return self.coleccion.delete_many({"fecha_envio": {"$lt": fecha}}).deleted_count

    def registrar(self, usuario_id: str, tipo: str, clave: str, fecha: datetime) -> None:
        self.coleccion.update_one(
            {"usuario_id": ObjectId(usuario_id), "tipo": tipo, "clave": clave},
            {"$set": {"fecha_envio": fecha}},
            upsert=True,
        )
