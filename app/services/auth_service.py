from datetime import datetime, timezone

from app.core.seguridad import generar_hash_password, verificar_password
from app.repositories.usuario_repo import UsuarioRepositorio
from app.services.auditoria_service import AuditoriaService
from app.services.sesion_service import SesionService


class AuthService:
    def __init__(self) -> None:
        self.repositorio = UsuarioRepositorio()
        self.auditoria = AuditoriaService()
        self.sesion_service = SesionService()

    def iniciar_sesion(self, usuario: str, password: str):
        registro = self.repositorio.buscar_por_usuario(usuario)
        if not registro:
            return None, "Usuario no encontrado"

        if not registro.get("activo", False):
            return None, "Usuario inactivo"

        if not verificar_password(password, registro["password_hash"]):
            return None, "Contraseña incorrecta"

        permisos = self._obtener_permisos(registro)
        self.repositorio.actualizar(str(registro["_id"]), {"ultimo_acceso": datetime.now(timezone.utc)})
        sesion = {
            "id": str(registro["_id"]),
            "usuario": registro["usuario"],
            "nombre_completo": registro.get("nombre_completo", ""),
            "roles": registro.get("roles", []),
            "permisos": permisos,
        }
        sesion["id_sesion"] = self.sesion_service.abrir_sesion(sesion)
        return sesion, None

    def _obtener_permisos(self, registro: dict) -> list[str]:
        permisos = set(registro.get("permisos_extra", []))
        roles = registro.get("roles", [])
        if not roles:
            return sorted(permisos)

        roles_docs = list(self.repositorio.roles.find({"nombre": {"$in": roles}, "activo": True}))
        for rol in roles_docs:
            permisos.update(rol.get("permisos", []))
        return sorted(permisos)

    def cambiar_password(self, id_usuario: str, password_actual: str, password_nueva: str) -> tuple[bool, str]:
        """Cambia la contraseña del usuario después de validar la actual.
        
        Retorna: (éxito, mensaje)
        """
        if not password_actual or not password_nueva:
            return False, "Completa todas las contraseñas"

        if len(password_nueva) < 6:
            return False, "La nueva contraseña debe tener al menos 6 caracteres"

        registro = self.repositorio.buscar_por_id(id_usuario)
        if not registro:
            return False, "El usuario no existe"

        if not verificar_password(password_actual, registro["password_hash"]):
            return False, "Contraseña actual incorrecta"

        password_hash_nueva = generar_hash_password(password_nueva)
        self.repositorio.actualizar(id_usuario, {"password_hash": password_hash_nueva})
        self.auditoria.registrar_accion(id_usuario, "cambiar_password", "usuario", {"id_usuario": id_usuario})
        return True, "Contraseña actualizada correctamente"
