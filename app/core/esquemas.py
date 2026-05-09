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

ESQUEMA_CORRESPONDENCIA = {
    "bsonType": "object",
    "required": [
        "numero_radicado", 
        "asunto", 
        "peticionario", 
        "estado_actual", 
        "fecha_radicacion", 
        "fecha_vencimiento", 
        "tipo", 
        "grupo", 
        "trazabilidad"
    ],
    "properties": {
        "numero_radicado": {
            "bsonType": "string",
            "description": "Debe ser un string y es obligatorio (Ej: RE26-0001)"
        },
        "asunto": {
            "bsonType": "string",
            "description": "Descripción del contenido del radicado"
        },
        "peticionario": {
            "bsonType": "string",
            "description": "Nombre de la persona o entidad que envía"
        },
        "estado_actual": {
            "enum": ["pendiente", "en_tramite", "en_revision", "respondido", "archivado", "traslado_competencia"],
            "description": "Solo puede ser uno de los estados definidos"
        },
        "fecha_radicacion": {
            "bsonType": "date",
            "description": "Fecha y hora de ingreso al sistema"
        },
        "fecha_vencimiento": {
            "bsonType": "date",
            "description": "Fecha límite para dar respuesta oportuna"
        },
        "tipo": { "bsonType": "string" },
        "grupo": { "bsonType": "string" },
        "clase": { "bsonType": "string" },
        "responsable_actual": {
            "bsonType": "object",
            "required": ["usuario_id", "nombre", "fecha_asignacion"],
            "properties": {
                "usuario_id": { "bsonType": "string" },
                "nombre": { "bsonType": "string" },
                "fecha_asignacion": { "bsonType": "date" }
            },
            "description": "Opcional: No existe hasta que un coordinador lo asigne"
        },
        "respuesta": {
            "bsonType": "object",
            "properties": {
                "numero_oficio": { "bsonType": "string" },
                "fecha_salida": { "bsonType": "date" }
            },
            "description": "Opcional: Solo se completa al finalizar el trámite"
        },
        "observaciones_generales": { "bsonType": "string" },
        "metadatos_adicionales": { "bsonType": "object" },
        "trazabilidad": {
            "bsonType": "array",
            "minItems": 1,
            "items": {
                "bsonType": "object",
                "required": ["fecha", "tipo_evento", "usuario_ejecutor", "estado_nuevo"],
                "properties": {
                    "fecha": { "bsonType": "date" },
                    "tipo_evento": { 
                        "enum": ["radicacion", "asignacion", "reasignacion", "cambio_estado", "carga_respuesta", "cierre"] 
                    },
                    "usuario_ejecutor": { "bsonType": "string" },
                    "estado_anterior": { "bsonType": ["string", "null"] },
                    "estado_nuevo": { "bsonType": "string" },
                    "responsable_anterior": { "bsonType": ["string", "null"] },
                    "responsable_nuevo": { "bsonType": ["string", "null"] },
                    "comentario": { "bsonType": ["string", "null"] }
                }
            }
        }
    }
}