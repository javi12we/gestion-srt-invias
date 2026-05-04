"""Repositorio de auditoría para registrar cambios y acciones."""

from datetime import datetime, timezone

from app.db.mongo import obtener_coleccion


class AuditoriaRepositorio:
    """Registra cambios y acciones en la base de datos."""

    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("auditoria")

    def registrar(self, usuario: str, accion: str, recurso: str, detalle: dict = None, exito: bool = True) -> None:
        """Registra una acción en auditoría.
        
        Args:
            usuario: usuario que realizó la acción
            accion: tipo de acción (crear, editar, desactivar, etc.)
            recurso: tipo de recurso (usuario, rol, etc.)
            detalle: detalles adicionales de la operación
            exito: si la operación fue exitosa
        """
        registro = {
            "usuario": usuario,
            "accion": accion,
            "recurso": recurso,
            "detalle": detalle or {},
            "exito": exito,
            "fecha": datetime.now(timezone.utc),
        }
        self.coleccion.insert_one(registro)

    def listar(self, filtro: dict = None, limite: int = 100):
        """Lista registros de auditoría."""
        filtro = filtro or {}
        return list(self.coleccion.find(filtro).sort("fecha", -1).limit(limite))
