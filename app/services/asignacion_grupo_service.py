"""Asignación de usuarios a grupos de trabajo (colección 'asignaciones_grupo').

Un usuario puede estar activo en varios grupos a la vez. Cada periodo de pertenencia
es un documento; al retirar se conserva el historial con la razón del retiro.

Quién gestiona un grupo:
- el administrador (permiso 'grupo.gestionar_miembros'): todos los grupos, y es el único
  que designa líderes o retira a un líder;
- el líder del grupo (asignación activa con es_lider=True): asigna y retira miembros
  de su(s) grupo(s).
"""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from app.core.autorizacion import ValidacionAutorizacion, validar_permiso
from app.repositories.asignacion_grupo_repo import AsignacionGrupoRepositorio
from app.repositories.grupo_repo import GrupoRepositorio
from app.repositories.usuario_repo import UsuarioRepositorio

PERMISO_GESTIONAR = "grupo.gestionar_miembros"
MIN_RAZON_RETIRO = 5


class ErrorAsignacionGrupo(Exception):
    """Error de negocio al asignar o retirar (se muestra al usuario con st.warning)."""


class AsignacionGrupoService:
    def __init__(self, repo_asignaciones=None, repo_grupos=None, repo_usuarios=None) -> None:
        self.asignaciones = repo_asignaciones or AsignacionGrupoRepositorio()
        self.grupos = repo_grupos or GrupoRepositorio()
        self.usuarios = repo_usuarios or UsuarioRepositorio()

    # ── Autorización ──────────────────────────────────────────────────────────
    @staticmethod
    def _es_admin(permisos_actor: list[str] | None) -> bool:
        return PERMISO_GESTIONAR in (permisos_actor or [])

    def es_lider_de(self, actor_id: str | None, grupo_clave: str) -> bool:
        if not actor_id:
            return False
        try:
            ObjectId(actor_id)
        except (InvalidId, TypeError):
            return False
        activa = self.asignaciones.obtener_activa(actor_id, grupo_clave)
        return bool(activa and activa.get("es_lider"))

    def puede_gestionar_grupo(self, grupo_clave: str, permisos_actor: list[str],
                              actor_id: str | None = None) -> bool:
        return self._es_admin(permisos_actor) or self.es_lider_de(actor_id, grupo_clave)

    def _autorizar(self, grupo_clave: str, permisos_actor: list[str], actor_id: str | None) -> None:
        if not self.puede_gestionar_grupo(grupo_clave, permisos_actor, actor_id):
            raise ValidacionAutorizacion(
                "Solo el administrador o el líder del grupo pueden gestionar sus miembros."
            )

    def grupos_gestionables(self, permisos_actor: list[str], actor_id: str | None = None) -> list[str]:
        """Claves de los grupos que el actor puede gestionar (todos si es admin)."""
        if self._es_admin(permisos_actor):
            return [g["clave"] for g in self.grupos.listar(solo_activos=True)]
        if not actor_id:
            return []
        return [a["grupo_clave"] for a in self.asignaciones.listar_por_usuario(actor_id, solo_activas=True)
                if a.get("es_lider")]

    # ── Escritura ─────────────────────────────────────────────────────────────
    def asignar(self, usuario_id: str, grupo_clave: str, actor: str, permisos_actor: list[str],
                razon_ingreso: str | None = None, actor_id: str | None = None):
        self._autorizar(grupo_clave, permisos_actor, actor_id)
        usuario = self._usuario_activo(usuario_id)
        self._grupo_activo(grupo_clave)

        if self.asignaciones.obtener_activa(usuario_id, grupo_clave):
            raise ErrorAsignacionGrupo("El usuario ya pertenece a este grupo.")

        ahora = datetime.now(timezone.utc)
        razon = (razon_ingreso or "").strip() or None
        doc = {
            "usuario_id": usuario["_id"],
            "grupo_clave": grupo_clave,
            "estado": "activo",
            "es_lider": False,
            "fecha_ingreso": ahora,
            "razon_ingreso": razon,
            "asignado_por": actor,
            "fecha_retiro": None,
            "razon_retiro": None,
            "retirado_por": None,
            "trazabilidad": [
                {"fecha": ahora, "accion": "asignado", "usuario": actor, "detalle": razon}
            ],
        }
        try:
            return self.asignaciones.insertar(doc)
        except DuplicateKeyError:
            raise ErrorAsignacionGrupo("El usuario ya pertenece a este grupo.")

    def retirar(self, usuario_id: str, grupo_clave: str, razon: str, actor: str,
                permisos_actor: list[str], actor_id: str | None = None) -> None:
        self._autorizar(grupo_clave, permisos_actor, actor_id)
        razon = (razon or "").strip()
        if len(razon) < MIN_RAZON_RETIRO:
            raise ErrorAsignacionGrupo(
                f"La razón del retiro es obligatoria (mínimo {MIN_RAZON_RETIRO} caracteres)."
            )
        self._id_valido(usuario_id)

        activa = self.asignaciones.obtener_activa(usuario_id, grupo_clave)
        if not activa:
            raise ErrorAsignacionGrupo("El usuario no pertenece actualmente a este grupo.")
        if activa.get("es_lider") and not self._es_admin(permisos_actor):
            raise ErrorAsignacionGrupo("Solo un administrador puede retirar al líder del grupo.")

        ahora = datetime.now(timezone.utc)
        retirada = self.asignaciones.retirar(
            activa["_id"],
            {"estado": "retirado", "fecha_retiro": ahora, "razon_retiro": razon, "retirado_por": actor},
            {"fecha": ahora, "accion": "retirado", "usuario": actor, "detalle": razon},
        )
        if not retirada:
            raise ErrorAsignacionGrupo("La asignación ya había sido retirada.")

    def definir_lider(self, usuario_id: str, grupo_clave: str, es_lider: bool, actor: str,
                      permisos_actor: list[str]) -> None:
        """Designa o quita el liderazgo de un miembro activo. Solo el administrador."""
        validar_permiso(permisos_actor, PERMISO_GESTIONAR)
        self._id_valido(usuario_id)
        activa = self.asignaciones.obtener_activa(usuario_id, grupo_clave)
        if not activa:
            raise ErrorAsignacionGrupo("El usuario no pertenece actualmente a este grupo.")
        if bool(activa.get("es_lider")) == bool(es_lider):
            return
        ahora = datetime.now(timezone.utc)
        detalle = "Designado líder del grupo" if es_lider else "Se quitó el liderazgo del grupo"
        if not self.asignaciones.definir_lider(
            activa["_id"], bool(es_lider),
            {"fecha": ahora, "accion": "lider_definido", "usuario": actor, "detalle": detalle},
        ):
            raise ErrorAsignacionGrupo("La asignación ya no está activa.")

    # ── Consulta ──────────────────────────────────────────────────────────────
    def listar_grupos(self, solo_activos: bool = True) -> list[dict]:
        return self.grupos.listar(solo_activos=solo_activos)

    def listar_miembros(self, grupo_clave: str, estado: str | None = "activo") -> list[dict]:
        return self.asignaciones.listar_por_grupo(grupo_clave, estado)

    def miembros_detalle(self, grupo_clave: str, estado: str | None = "activo") -> list[dict]:
        """Asignaciones de un grupo con los datos visibles del usuario (nombre, usuario)."""
        asignaciones = self.asignaciones.listar_por_grupo(grupo_clave, estado)
        usuarios = {
            u["_id"]: u for u in self.usuarios.listar_por_ids([a["usuario_id"] for a in asignaciones])
        }
        detalle = []
        for a in asignaciones:
            u = usuarios.get(a["usuario_id"], {})
            detalle.append({
                "usuario_id": str(a["usuario_id"]),
                "nombre": u.get("nombre_completo") or u.get("usuario") or "(usuario eliminado)",
                "usuario": u.get("usuario", ""),
                "es_lider": bool(a.get("es_lider")),
                "fecha_ingreso": a.get("fecha_ingreso"),
                "razon_ingreso": a.get("razon_ingreso"),
                "asignado_por": a.get("asignado_por"),
                "fecha_retiro": a.get("fecha_retiro"),
                "razon_retiro": a.get("razon_retiro"),
                "retirado_por": a.get("retirado_por"),
            })
        return sorted(detalle, key=lambda d: (not d["es_lider"], d["nombre"].lower()))

    def usuarios_de_grupo(self, grupo_clave: str) -> list[dict]:
        """Documentos de usuario de los miembros activos de un grupo."""
        ids = [a["usuario_id"] for a in self.asignaciones.listar_por_grupo(grupo_clave, "activo")]
        return self.usuarios.listar_por_ids(ids)

    def grupos_de_usuario(self, usuario_id: str, solo_activas: bool = True) -> list[dict]:
        self._id_valido(usuario_id)
        return self.asignaciones.listar_por_usuario(usuario_id, solo_activas)

    def claves_de_usuario(self, usuario_id: str) -> dict:
        """{'grupos': [claves activas], 'lider': [claves donde es líder]} para la sesión."""
        activas = self.grupos_de_usuario(usuario_id, solo_activas=True)
        return {
            "grupos": [a["grupo_clave"] for a in activas],
            "lider": [a["grupo_clave"] for a in activas if a.get("es_lider")],
        }

    def nombres_grupos_texto(self, usuario_id: str) -> str:
        """Texto legible con los grupos activos del usuario (para mostrar en el perfil)."""
        try:
            claves = self.claves_de_usuario(str(usuario_id))["grupos"]
            nombres = {g["clave"]: g["nombre"] for g in self.grupos.listar()}
        except Exception:
            return "No disponible"
        return ", ".join(nombres.get(c, c) for c in claves) or "Sin grupo asignado"

    def mapa_grupos_activos(self) -> dict:
        """{str(usuario_id): [claves de grupos activos]} para reportes."""
        mapa: dict = {}
        for a in self.asignaciones.listar_activas():
            mapa.setdefault(str(a["usuario_id"]), []).append(a["grupo_clave"])
        return mapa

    # ── Migración desde usuarios.informacion_laboral.grupo_trabajo ────────────
    def migrar_desde_usuarios(self, simular: bool = True) -> dict:
        """Crea una asignación activa por cada usuario que hoy tiene grupo_trabajo.

        Idempotente: no duplica si el usuario ya tiene asignación activa en ese grupo.
        No modifica la colección 'usuarios'.
        """
        resumen = {"a_crear": 0, "creadas": 0, "ya_existian": 0, "inactivos": 0, "por_grupo": {}}
        ahora = datetime.now(timezone.utc)
        for grupo in self.grupos.listar():
            clave = grupo["clave"]
            for usuario in self.usuarios.listar_por_grupo_trabajo(clave):
                if self.asignaciones.obtener_activa(str(usuario["_id"]), clave):
                    resumen["ya_existian"] += 1
                    continue
                resumen["a_crear"] += 1
                resumen["por_grupo"][clave] = resumen["por_grupo"].get(clave, 0) + 1
                if not usuario.get("activo", True):
                    resumen["inactivos"] += 1
                if simular:
                    continue
                detalle = "Migración inicial desde informacion_laboral.grupo_trabajo"
                try:
                    self.asignaciones.insertar({
                        "usuario_id": usuario["_id"],
                        "grupo_clave": clave,
                        "estado": "activo",
                        "es_lider": False,
                        "fecha_ingreso": ahora,
                        "razon_ingreso": detalle,
                        "asignado_por": "migracion",
                        "fecha_retiro": None,
                        "razon_retiro": None,
                        "retirado_por": None,
                        "trazabilidad": [
                            {"fecha": ahora, "accion": "asignado", "usuario": "migracion", "detalle": detalle}
                        ],
                    })
                    resumen["creadas"] += 1
                except DuplicateKeyError:
                    resumen["ya_existian"] += 1
        return resumen

    # ── Validaciones internas ─────────────────────────────────────────────────
    @staticmethod
    def _id_valido(usuario_id: str) -> None:
        try:
            ObjectId(usuario_id)
        except (InvalidId, TypeError):
            raise ErrorAsignacionGrupo("Identificador de usuario inválido.")

    def _usuario_activo(self, usuario_id: str) -> dict:
        self._id_valido(usuario_id)
        usuario = self.usuarios.buscar_por_id(usuario_id)
        if not usuario:
            raise ErrorAsignacionGrupo("El usuario no existe.")
        if not usuario.get("activo", False):
            raise ErrorAsignacionGrupo("El usuario está inactivo.")
        return usuario

    def _grupo_activo(self, grupo_clave: str) -> dict:
        grupo = self.grupos.obtener_por_clave(grupo_clave)
        if not grupo:
            raise ErrorAsignacionGrupo("El grupo no existe.")
        if not grupo.get("activo", False):
            raise ErrorAsignacionGrupo("El grupo está inactivo.")
        return grupo
