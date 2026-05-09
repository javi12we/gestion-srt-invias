ESQUEMA_USUARIOS = {
    "bsonType": "object",
    "required": [
        "usuario",
        "nombre_completo",
        "email",
        "password_hash",
        "activo",
        "roles",
        "permisos_extra",
        "fecha_creacion",
        "fecha_actualizacion",
    ],
    "properties": {
        "usuario": {"bsonType": "string", "minLength": 3},
        "nombre_completo": {"bsonType": "string"},
        "email": {"bsonType": "string"},
        "password_hash": {"bsonType": "string"},
        "activo": {"bsonType": "bool"},
        "roles": {"bsonType": "array", "items": {"bsonType": "string"}},
        "permisos_extra": {"bsonType": "array", "items": {"bsonType": "string"}},
        "fecha_creacion": {"bsonType": "date"},
        "fecha_actualizacion": {"bsonType": "date"},
        "ultimo_acceso": {"bsonType": ["date", "null"]},
        "creado_por": {"bsonType": ["string", "null"]},
        "actualizado_por": {"bsonType": ["string", "null"]},
    },
}

ESQUEMA_ROLES = {
    "bsonType": "object",
    "required": ["nombre", "descripcion", "permisos", "activo"],
    "properties": {
        "nombre": {"bsonType": "string"},
        "descripcion": {"bsonType": "string"},
        "permisos": {"bsonType": "array", "items": {"bsonType": "string"}},
        "activo": {"bsonType": "bool"},
    },
}

ESQUEMA_PERMISOS = {
    "bsonType": "object",
    "required": ["clave", "descripcion", "modulo"],
    "properties": {
        "clave": {"bsonType": "string"},
        "descripcion": {"bsonType": "string"},
        "modulo": {"bsonType": "string"},
    },
}

ESQUEMA_SESIONES = {
    "bsonType": "object",
    "required": [
        "id_sesion",
        "id_usuario",
        "usuario",
        "fecha_inicio",
        "estado",
    ],
    "properties": {
        "id_sesion": {"bsonType": "string"},
        "id_usuario": {"bsonType": "string"},
        "usuario": {"bsonType": "string"},
        "nombre_completo": {"bsonType": ["string", "null"]},
        "fecha_inicio": {"bsonType": "date"},
        "fecha_cierre": {"bsonType": ["date", "null"]},
        "estado": {"bsonType": "string"},
        "motivo_cierre": {"bsonType": ["string", "null"]},
        "duracion_segundos": {"bsonType": ["int", "long", "null"]},
    },
}

ESQUEMA_OPCIONES_CONFIGURACION = {
    "bsonType": "object",
    "required": ["categoria", "opciones"],
    "properties": {
        "categoria": {
            "enum": ["tipo", "grupo", "clase_correspondencia", "estados"],
            "description": "Define a qué desplegable pertenece",
        },
        "opciones": {
            "bsonType": "array",
            "items": {
                "bsonType": "object",
                "required": ["clave", "etiqueta", "activo"],
                "properties": {
                    "clave": {
                        "bsonType": "string",
                        "description": "Valor técnico (slug)",
                    },
                    "etiqueta": {
                        "bsonType": "string",
                        "description": "Valor visual",
                    },
                    "activo": {"bsonType": "bool"},
                },
            },
        },
    },
}