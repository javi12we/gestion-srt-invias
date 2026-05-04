from datetime import datetime, timezone
from uuid import uuid4

from app.repositories.sesion_repo import SesionRepositorio
from app.services.auditoria_service import AuditoriaService


class SesionService:
    """Servicio simplificado: solo maneja ciclo de sesión (apertura/cierre).
    No registra eventos granulares (vistas, módulos, acciones). Modelo: login/logout/duración.
    """

    def __init__(self) -> None:
        self.repositorio = SesionRepositorio()
        self.auditoria = AuditoriaService()

    def abrir_sesion(self, usuario_sesion: dict) -> str:
        """Inicia una sesión: primero cierra sesiones previas del usuario, luego crea la nueva."""
        # Cerrar sesiones previas activas (evita sesiones fantasma)
        cerradas = self.repositorio.cerrar_sesiones_previas(usuario_sesion["id"], motivo="nueva_sesion")
        if cerradas > 0:
            self.auditoria.registrar_accion(usuario_sesion["id"], "cerrar_sesiones_previas", "sesion", {"cantidad": cerradas})
        
        # Crear nueva sesión
        id_sesion = uuid4().hex
        ahora = datetime.now(timezone.utc)
        self.repositorio.crear(
            {
                "id_sesion": id_sesion,
                "id_usuario": usuario_sesion["id"],
                "usuario": usuario_sesion["usuario"],
                "nombre_completo": usuario_sesion.get("nombre_completo"),
                "fecha_inicio": ahora,
                "fecha_cierre": None,
                "estado": "activa",
                "motivo_cierre": None,
                "duracion_segundos": None,
            }
        )
        # Registrar acción crítica en auditoría
        self.auditoria.registrar_accion(usuario_sesion["id"], "iniciar_sesion", "sesion", {"id_sesion": id_sesion})
        return id_sesion

    def cerrar_sesion(self, id_sesion: str, usuario_sesion: dict, motivo_cierre: str = "logout"):
        """Cierra una sesión: calcula duración, registra fecha_cierre."""
        if not id_sesion:
            return None

        sesion = self.repositorio.buscar_por_id_sesion(id_sesion)
        if not sesion:
            return None

        # Calcular duración en segundos
        fecha_cierre = datetime.now(timezone.utc)
        fecha_inicio = sesion.get("fecha_inicio")
        duracion_segundos = None
        if fecha_inicio:
            # Asegurar que fecha_inicio sea offset-aware (agregar UTC si es naive)
            if fecha_inicio.tzinfo is None:
                fecha_inicio = fecha_inicio.replace(tzinfo=timezone.utc)
            duracion_segundos = int((fecha_cierre - fecha_inicio).total_seconds())

        resultado = self.repositorio.cerrar(id_sesion, motivo_cierre, duracion_segundos)
        # Registrar acción crítica en auditoría
        self.auditoria.registrar_accion(usuario_sesion["id"], "cerrar_sesion", "sesion", {"id_sesion": id_sesion, "motivo_cierre": motivo_cierre, "duracion_segundos": duracion_segundos})
        return resultado
