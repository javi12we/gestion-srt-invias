from pymongo.errors import OperationFailure

from app.core.esquemas import (
    ESQUEMA_PERMISOS,
    ESQUEMA_ROLES,
    ESQUEMA_SESIONES,
    ESQUEMA_USUARIOS,
    ESQUEMA_OPCIONES_CONFIGURACION,
    ESQUEMA_CORRESPONDENCIA,
)
from app.db.mongo import obtener_base_datos


class MongoBootstrapService:
    def __init__(self) -> None:
        self.db = obtener_base_datos()

    def asegurar_estructura(self) -> None:
        self._asegurar_coleccion("usuarios", ESQUEMA_USUARIOS)
        self._asegurar_coleccion("roles", ESQUEMA_ROLES)
        self._asegurar_coleccion("permisos", ESQUEMA_PERMISOS)
        self._asegurar_coleccion("sesiones", ESQUEMA_SESIONES)
        self._asegurar_coleccion(
            "opciones_configuracion", ESQUEMA_OPCIONES_CONFIGURACION
        )
        self._asegurar_coleccion("correspondencia", ESQUEMA_CORRESPONDENCIA)

        self.db["usuarios"].create_index(
            "usuario", unique=True, name="idx_usuarios_usuario_unico"
        )
        self.db["usuarios"].create_index("activo", name="idx_usuarios_activo")
        self.db["usuarios"].create_index("roles", name="idx_usuarios_roles")
        self.db["roles"].create_index(
            "nombre", unique=True, name="idx_roles_nombre_unico"
        )
        self.db["permisos"].create_index(
            "clave", unique=True, name="idx_permisos_clave_unico"
        )
        self.db["sesiones"].create_index(
            "id_sesion", unique=True, name="idx_sesiones_id_sesion_unico"
        )
        self.db["sesiones"].create_index("id_usuario", name="idx_sesiones_id_usuario")
        self.db["sesiones"].create_index("estado", name="idx_sesiones_estado")
        self.db["sesiones"].create_index(
            "fecha_inicio", name="idx_sesiones_fecha_inicio"
        )
        self.db["opciones_configuracion"].create_index(
            "categoria", unique=True, name="idx_opciones_categoria_unico"
        )
        # Eliminar el índice de unicidad si existe para permitir duplicados según requerimiento
        try:
            self.db["correspondencia"].drop_index("idx_correspondencia_radicado")
        except:
            pass

        self.db["correspondencia"].create_index(
            "numero_radicado", unique=False, name="idx_correspondencia_radicado"
        )
        self.db["correspondencia"].create_index(
            "estado_actual", name="idx_correspondencia_estado"
        )
        self.db["correspondencia"].create_index(
            "responsable_actual.usuario_id", name="idx_correspondencia_responsable"
        )

    def _asegurar_coleccion(self, nombre: str, esquema: dict) -> None:
        if nombre not in self.db.list_collection_names():
            self.db.create_collection(
                nombre,
                validator={"$jsonSchema": esquema},
                validationLevel="moderate",
                validationAction="error",
            )
            return

        try:
            self.db.command(
                "collMod",
                nombre,
                validator={"$jsonSchema": esquema},
                validationLevel="moderate",
                validationAction="error",
            )
        except OperationFailure:
            pass
