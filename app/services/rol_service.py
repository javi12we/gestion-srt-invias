from app.core.autorizacion import ValidacionAutorizacion, validar_permiso
from app.repositories.rol_repo import RolRepositorio
from app.services.auditoria_service import AuditoriaService


class RolService:
    def __init__(self) -> None:
        self.repositorio = RolRepositorio()
        self.auditoria = AuditoriaService()

    def listar_roles(self):
        return self.repositorio.listar()

    def crear_rol(self, datos: dict, permisos_usuario: list = None):
        nombre = datos.get("nombre", "").strip()
        if not nombre:
            raise ValueError("El nombre del rol es obligatorio")

        if permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "rol.crear")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))

        existente = self.repositorio.buscar_por_nombre(nombre)
        if existente:
            raise ValueError("Ya existe un rol con ese nombre")

        datos_rol = {
            "nombre": nombre,
            "descripcion": datos.get("descripcion", ""),
            "permisos": datos.get("permisos", []),
            "activo": datos.get("activo", True),
            "creado_por": datos.get("creado_por"),
        }
        id_nuevo = self.repositorio.crear(datos_rol)
        self.auditoria.registrar_accion(datos.get("creado_por", "sistema"), "crear", "rol", {"rol_creado": nombre})
        return id_nuevo

    def actualizar_rol(self, id_rol: str, datos: dict, permisos_usuario: list = None):
        if permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "rol.editar")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))

        rol_actual = self.repositorio.buscar_por_id(id_rol)
        if not rol_actual:
            raise ValueError("El rol no existe")

        nombre = datos.get("nombre")
        if nombre:
            nombre = nombre.strip()
            existente = self.repositorio.buscar_por_nombre(nombre)
            if existente and str(existente.get("_id")) != id_rol:
                raise ValueError("Ya existe un rol con ese nombre")

        update = {
            k: v
            for k, v in {
                "nombre": nombre or rol_actual.get("nombre"),
                "descripcion": datos.get("descripcion", rol_actual.get("descripcion", "")),
                "permisos": datos.get("permisos", rol_actual.get("permisos", [])),
                "activo": datos.get("activo", rol_actual.get("activo", True)),
                "actualizado_por": datos.get("actualizado_por"),
            }.items()
            if v is not None
        }

        resultado = self.repositorio.actualizar(id_rol, update)
        self.auditoria.registrar_accion(datos.get("actualizado_por", "sistema"), "editar", "rol", {"rol_editado": update.get("nombre")})
        return resultado

    def activar_rol(self, id_rol: str, permisos_usuario: list = None, usuario_actual: str = None):
        if permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "rol.desactivar")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))

        rol = self.repositorio.buscar_por_id(id_rol)
        resultado = self.repositorio.cambiar_estado(id_rol, True)
        self.auditoria.registrar_accion(usuario_actual or "sistema", "activar", "rol", {"rol_activado": rol.get("nombre")})
        return resultado

    def desactivar_rol(self, id_rol: str, permisos_usuario: list = None, usuario_actual: str = None):
        if permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "rol.desactivar")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))

        rol = self.repositorio.buscar_por_id(id_rol)
        resultado = self.repositorio.cambiar_estado(id_rol, False)
        self.auditoria.registrar_accion(usuario_actual or "sistema", "desactivar", "rol", {"rol_desactivado": rol.get("nombre")})
        return resultado
