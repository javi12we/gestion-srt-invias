from pymongo.errors import OperationFailure

from app.core.esquemas import (
    ESQUEMA_PERMISOS,
    ESQUEMA_ROLES,
    ESQUEMA_SESIONES,
    ESQUEMA_USUARIOS,
    ESQUEMA_OPCIONES_CONFIGURACION,
    ESQUEMA_CORRESPONDENCIA,
    ESQUEMA_CERTIFICACIONES,
    ESQUEMA_POLITICAS_DATOS,
    ESQUEMA_ACEPTACIONES_POLITICA,
    ESQUEMA_FIRMAS,
    ESQUEMA_INSTRUCTIVOS,
    ESQUEMA_NOTIFICACIONES_CORREO,
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
        self._asegurar_coleccion("certificaciones", ESQUEMA_CERTIFICACIONES)
        self._asegurar_coleccion("politicas_datos", ESQUEMA_POLITICAS_DATOS)
        self._asegurar_coleccion("aceptaciones_politica", ESQUEMA_ACEPTACIONES_POLITICA)
        self._asegurar_coleccion("firmas", ESQUEMA_FIRMAS)
        self._asegurar_coleccion("instructivos", ESQUEMA_INSTRUCTIVOS)
        self._asegurar_coleccion("notificaciones_correo", ESQUEMA_NOTIFICACIONES_CORREO)

        self.db["usuarios"].create_index(
            "usuario", unique=True, name="idx_usuarios_usuario_unico"
        )
        self.db["usuarios"].create_index("activo", name="idx_usuarios_activo")
        self.db["usuarios"].create_index(
            "contratos.numero",
            unique=True,
            sparse=True,
            name="idx_usuarios_contratos_numero_unico",
        )
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
        self.db["correspondencia"].create_index(
            [("fecha_radicacion", -1)],
            name="idx_correspondencia_fecha_radicacion",
        )
        self.db["correspondencia"].create_index(
            [
                ("responsable_actual.usuario_id", 1),
                ("estado_actual", 1),
                ("fecha_vencimiento", 1),
            ],
            name="idx_correspondencia_resp_estado_venc",
        )
        self.db["correspondencia"].create_index(
            [
                ("numero_radicado", "text"),
                ("peticionario", "text"),
                ("asunto", "text"),
                ("respuesta.numero_oficio", "text"),
            ],
            name="idx_correspondencia_texto",
            default_language="spanish",
        )
        self.db["certificaciones"].create_index(
            [("usuario_id", 1), ("año", -1), ("mes", -1)],
            name="idx_cert_usuario_periodo",
        )
        self.db["certificaciones"].create_index(
            [("año", -1), ("mes", -1)],
            name="idx_cert_periodo",
        )
        self.db["certificaciones"].create_index(
            "hash_verificacion",
            unique=True,
            sparse=True,
            name="idx_cert_hash_unico",
        )
        self.db["politicas_datos"].create_index(
            "numero_version", unique=True, name="idx_politicas_version_unica"
        )
        self.db["politicas_datos"].create_index("activa", name="idx_politicas_activa")
        self.db["aceptaciones_politica"].create_index(
            [("usuario_id", 1), ("politica_id", 1)],
            unique=True,
            name="idx_aceptaciones_usuario_politica_unico",
        )
        self.db["aceptaciones_politica"].create_index(
            "usuario_id", name="idx_aceptaciones_usuario"
        )
        self.db["aceptaciones_politica"].create_index(
            "politica_id", name="idx_aceptaciones_politica"
        )
        self.db["firmas"].create_index(
            "usuario_id", unique=True, name="idx_firmas_usuario_unico"
        )
        self.db["instructivos"].create_index("activo", name="idx_instructivos_activo")
        self.db["instructivos"].create_index("orden", name="idx_instructivos_orden")
        self.db["notificaciones_correo"].create_index(
            [("usuario_id", 1), ("tipo", 1), ("clave", 1)],
            unique=True,
            name="idx_notificaciones_usuario_tipo_clave_unico",
        )

    def _asegurar_coleccion(self, nombre: str, esquema: dict) -> None:
        if nombre not in self.db.list_collection_names():
            self.db.create_collection(
                nombre,
                validator={"$jsonSchema": esquema},
                validationLevel="moderate",
                validationAction="error",
            )
            print(f"  Colección '{nombre}' creada con validador.")
            return

        self.db.command(
            "collMod",
            nombre,
            validator={"$jsonSchema": esquema},
            validationLevel="moderate",
            validationAction="error",
        )
        print(f"  Validador de '{nombre}' actualizado.")
