"""Servicio de auditoría."""

from app.repositories.auditoria_repo import AuditoriaRepositorio


class AuditoriaService:
    """Servicio para registrar auditoría."""

    def __init__(self) -> None:
        self.repositorio = AuditoriaRepositorio()

    def registrar_accion(
        self, usuario: str, accion: str, recurso: str, detalle: dict = None, exito: bool = True
    ) -> None:
        """Registra una acción en auditoría."""
        self.repositorio.registrar(usuario, accion, recurso, detalle, exito)
