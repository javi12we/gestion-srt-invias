# Sub-esquema reutilizable: afiliación a una entidad de seguridad social
# (EPS / ARL / AFP / CCF). El aporte lo paga el contratista (registra 'valor',
# 'valor_primer_mes' y 'valor_ultimo_mes') o la entidad (registra 'radicado');
# 'paga' indica cuál de los dos casos aplica.
_ESQUEMA_AFILIACION = {
    "bsonType": ["object", "null"],
    "properties": {
        "entidad": {"bsonType": ["string", "null"], "description": "Clave del catálogo correspondiente"},
        "paga": {
            "bsonType": ["string", "null"],
            "enum": ["contratista", "entidad", None],
            "description": "Quién paga el aporte: 'contratista' (registra valor) o 'entidad' (registra radicado)",
        },
        "valor": {"bsonType": ["int", "long", "double", "null"], "description": "Valor mensual del aporte (COP) para los meses intermedios del contrato (segundo mes en adelante), cuando lo paga el contratista"},
        "valor_primer_mes": {"bsonType": ["int", "long", "double", "null"], "description": "Valor del aporte (COP) correspondiente al primer mes del contrato, cuando lo paga el contratista"},
        "valor_ultimo_mes": {"bsonType": ["int", "long", "double", "null"], "description": "Valor del aporte (COP) correspondiente al último mes del contrato, cuando lo paga el contratista"},
        "radicado": {"bsonType": ["string", "null"], "description": "Número de radicado del pago, cuando lo paga la entidad"},
    },
}

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
        "tipo_documento": {
            "bsonType": ["string", "null"],
            "enum": ["CC", "CE", "TI", "PA", "RC", "PEP", "PPT", None],
            "description": "CC=Cédula de Ciudadanía, CE=Cédula de Extranjería, TI=Tarjeta de Identidad, PA=Pasaporte, RC=Registro Civil, PEP=Permiso Especial de Permanencia, PPT=Permiso por Protección Temporal",
        },
        "numero_documento": {"bsonType": ["string", "null"]},
        "lugar_expedicion_documento": {
            "bsonType": ["string", "null"],
            "description": "Ciudad de expedición del documento de identidad (texto libre)",
        },
        "contratos": {
            "bsonType": ["array", "null"],
            "items": {
                "bsonType": "object",
                "required": ["numero"],
                "properties": {
                    "numero": {"bsonType": "string", "minLength": 1},
                    "tipo": {
                        "bsonType": ["string", "null"],
                        "enum": ["termino_indefinido", "termino_fijo", "obra_labor", "prestacion_servicios", "aprendizaje", None],
                    },
                    "objeto": {"bsonType": ["string", "null"]},
                    "fecha_orden_inicio_contrato": {
                        "bsonType": ["string", "date", "null"],
                        "description": "Radicado / fecha de la orden de inicio (texto libre). 'date' solo por contratos guardados antes de que el campo fuera abierto.",
                    },
                    "valor": {"bsonType": ["int", "long", "double", "null"]},
                    "valor_mensual": {"bsonType": ["int", "long", "double", "null"]},
                    "valor_primer_pago": {"bsonType": ["int", "long", "double", "null"]},
                    "rp_compromiso_presupuestal": {
                        "bsonType": ["string", "null"],
                        "description": "Código de Registro Presupuestal / compromiso presupuestal (alfanumérico)",
                    },
                    "fecha_recurso_presupuestal": {"bsonType": ["date", "null"]},
                    "firma_cps_secop": {"bsonType": ["date", "null"]},
                    "fecha_inicio": {"bsonType": ["date", "null"]},
                    "fecha_fin": {"bsonType": ["date", "null"]},
                    "tiene_inventario": {"bsonType": ["bool", "null"]},
                    "desc_inventario": {"bsonType": ["string", "null"]},
                    "valor_total_por_pagar_contrato": {"bsonType": ["int", "long", "double", "null"]},
                    "valor_total_pagado": {"bsonType": ["int", "long", "double", "null"]},
                    "prorrogra_contrato": {
                        "bsonType": ["object", "null"],
                        "properties": {
                            "tiene_prorroga": {"bsonType": ["bool", "null"]},
                            "fecha_prorrogra": {"bsonType": ["date", "null"]},
                            "radicado_prorrogra": {"bsonType": ["string", "null"]},
                        },
                    },
                    "adiciones_contrato": {
                        "bsonType": ["object", "null"],
                        "properties": {
                            "tiene_adiciones": {"bsonType": ["bool", "null"]},
                            "valor_adicion": {"bsonType": ["int", "long", "double", "null"]},
                        },
                    },
                    "personalizar_ultimacuenta": {"bsonType": ["bool", "null"]},
                    "valor_personalizar_ultimacuenta": {"bsonType": ["int", "long", "double", "null"]},
                    "pagos": {
                        "bsonType": ["array", "null"],
                        "maxItems": 20,
                        "items": {
                            "bsonType": "object",
                            "required": [
                                "numero_pago",
                                "fecha_pago",
                                "valor_bruto_pago",
                                "deducciones_pago",
                                "valor_neto_pago",
                            ],
                            "properties": {
                                "numero_pago": {"bsonType": "string"},
                                "fecha_pago": {"bsonType": "date"},
                                "valor_bruto_pago": {"bsonType": ["int", "long", "double"]},
                                "deducciones_pago": {"bsonType": ["int", "long", "double"]},
                                "valor_neto_pago": {"bsonType": ["int", "long", "double"]},
                            },
                        },
                    },
                },
            },
        },
        "informacion_laboral": {
            "bsonType": ["object", "null"],
            "description": "Datos de seguridad social, bancarios, tributarios y dependientes. Opcional (no aplica a todos los usuarios).",
            "properties": {
                "es_pensionado": {
                    "bsonType": ["bool", "null"],
                    "description": "Si es True, AFP y CCF no aplican y no se validan para descarga de formatos",
                },
                "planilla_mes_vencido": {
                    "bsonType": ["bool", "null"],
                    "description": "True si paga planilla a mes vencido, False en caso contrario",
                },
                "grupo_trabajo": {
                    "bsonType": ["string", "null"],
                    "enum": ["despacho", "normativa_tecnica", "innovacion_tecnica", "permisos", "", None],
                    "description": "Grupo de trabajo al que pertenece",
                },
                "ibc_prestaciones_sociales": {
                    "bsonType": ["int", "long", "double", "null"],
                    "description": "Ingreso Base de Cotización - Prestaciones sociales (valor numérico)",
                },
                "paga_iva": {
                    "bsonType": ["bool", "null"],
                    "description": "Indica si paga IVA",
                },
                "valor_iva": {
                    "bsonType": ["int", "long", "double", "null"],
                    "description": "Valor del IVA",
                },
                "seguridad_social": {
                    "bsonType": ["object", "null"],
                    "properties": {
                        "eps": _ESQUEMA_AFILIACION,
                        "arl": _ESQUEMA_AFILIACION,
                        "afp": _ESQUEMA_AFILIACION,
                        "ccf": _ESQUEMA_AFILIACION,
                    },
                },
                "bancaria": {
                    "bsonType": ["object", "null"],
                    "properties": {
                        "banco": {"bsonType": ["string", "null"], "description": "Clave del catálogo 'banco'"},
                        "numero_cuenta": {
                            "bsonType": ["string", "null"],
                            "description": "Número de cuenta (string para preservar ceros a la izquierda)",
                        },
                        "tipo_cuenta": {
                            "bsonType": ["string", "null"],
                            "enum": ["ahorros", "corriente", "cts", None],
                            "description": "ahorros=Cuenta de Ahorros, corriente=Cuenta Corriente, cts=Cuentas de Trámite Simplificado",
                        },
                    },
                },
                "tributaria": {
                    "bsonType": ["object", "null"],
                    "properties": {
                        "rut": {"bsonType": ["string", "null"], "description": "Número de RUT (alfanumérico, admite símbolos)"},
                        "declarante_renta": {"bsonType": ["bool", "null"]},
                        "regimen": {
                            "bsonType": ["string", "null"],
                            "enum": ["no_responsable_iva", "responsable_iva", "simple_rst", "especial_rte", None],
                            "description": "Clave del catálogo 'regimen_tributario'"
                        },
                    },
                },
                "dependientes": {
                    "bsonType": ["array", "null"],
                    "description": "Dependientes económicos; lista vacía = sin dependientes",
                    "items": {
                        "bsonType": "object",
                        "required": ["nombre"],
                        "properties": {
                            "nombre": {"bsonType": "string", "minLength": 1},
                            "tipo_documento": {
                                "bsonType": ["string", "null"],
                                "enum": ["CC", "TI", "CE", "RC", "OTRO", None],
                            },
                            "numero_documento": {"bsonType": ["string", "null"]},
                            "tipo": {"bsonType": ["string", "null"], "description": "Clave del catálogo 'tipo_dependiente'"},
                        },
                    },
                },
            },
        },
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
    "required": ["categoria"],
    "properties": {
        "categoria": {
            "bsonType": "string",
            "description": "Categoría del documento de configuración",
        },
        "opciones": {
            "bsonType": ["array", "null"],
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

ESQUEMA_CERTIFICACIONES = {
    "bsonType": "object",
    "required": ["usuario_id", "nombre_usuario", "año", "mes", "estado", "creado_en"],
    "properties": {
        "usuario_id": {"bsonType": "objectId"},
        "nombre_usuario": {"bsonType": "string"},
        "año": {"bsonType": "int"},
        "mes": {"bsonType": "int"},
        "estado": {"enum": ["pendiente", "aprobado", "rechazado"]},
        "tipo_formato": {"bsonType": "string"},
        "fecha_corte": {"bsonType": ["date", "null"]},
        "snapshot_al_dia": {"bsonType": ["bool", "null"]},
        "observaciones": {"bsonType": ["string", "null"]},
        "observacion": {"bsonType": ["string", "null"]},
        "aprobado_por": {
            "bsonType": "object",
            "required": ["usuario_id", "nombre", "fecha"],
            "properties": {
                "usuario_id": {"bsonType": "objectId"},
                "nombre": {"bsonType": "string"},
                "fecha": {"bsonType": "date"},
            },
        },
        "firmas": {
            "bsonType": ["object", "null"],
            "description": "Aprobaciones de firmantes designados: corr/gd/secop (correspondencia) o financiera/abogado/jefe (actas)",
            "properties": {
                "corr":  {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "gd":    {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "secop": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "financiera": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "abogado": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "jefe": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "extra_control": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "extra_acta_compromiso": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "extra_balance_general": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "extra_acta_recibo_entrega": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
            },
        },
        "eventos": {
            "bsonType": ["array", "null"],
            "description": "Bitácora de eventos del documento (ej. revocaciones en cascada de firmas de actas)",
            "items": {
                "bsonType": "object",
                "properties": {
                    "tipo":         {"bsonType": "string"},
                    "rol_revocado": {"bsonType": "string"},
                    "causada_por":  {"bsonType": "string"},
                    "fecha":        {"bsonType": "date"},
                },
            },
        },
        "hash_verificacion": {"bsonType": ["string", "null"]},
        "creado_en": {"bsonType": "date"},
    },
}

ESQUEMA_POLITICAS_DATOS = {
    "bsonType": "object",
    "required": ["numero_version", "titulo", "contenido", "activa", "fecha_vigencia", "fecha_creacion"],
    "properties": {
        "numero_version": {"bsonType": "int", "minimum": 1},
        "titulo": {"bsonType": "string"},
        "contenido": {"bsonType": "string"},
        "activa": {"bsonType": "bool"},
        "fecha_vigencia": {"bsonType": "date"},
        "fecha_creacion": {"bsonType": "date"},
        "creada_por": {"bsonType": ["string", "null"]},
    },
}

ESQUEMA_ACEPTACIONES_POLITICA = {
    "bsonType": "object",
    "required": [
        "usuario_id",
        "politica_id",
        "numero_version",
        "fecha_aceptacion",
        "metodo",
    ],
    "properties": {
        "usuario_id": {"bsonType": "objectId"},
        "politica_id": {"bsonType": "objectId"},
        "numero_version": {"bsonType": "int"},
        "fecha_aceptacion": {"bsonType": "date"},
        "ip_address": {"bsonType": ["string", "null"]},
        "user_agent": {"bsonType": ["string", "null"]},
        "nombre_completo": {"bsonType": ["string", "null"]},
        "email": {"bsonType": ["string", "null"]},
        "sesion_id": {"bsonType": ["string", "null"]},
        "metodo": {"bsonType": "string"},
    },
}

ESQUEMA_INSTRUCTIVOS = {
    "bsonType": "object",
    "required": ["titulo", "url", "tipo", "activo", "orden", "fecha_creacion"],
    "properties": {
        "titulo": {"bsonType": "string", "minLength": 1},
        "descripcion": {"bsonType": ["string", "null"]},
        "url": {"bsonType": "string", "minLength": 1},
        "tipo": {
            "enum": ["pdf", "video", "enlace"],
            "description": "pdf y video se incrustan en iframe; enlace solo muestra botón externo",
        },
        "icono": {"bsonType": ["string", "null"], "description": "Emoji o texto corto para el botón"},
        "activo": {"bsonType": "bool"},
        "orden": {"bsonType": "int", "minimum": 1},
        "embed_height": {"bsonType": ["int", "null"], "description": "Altura del iframe en px"},
        "fecha_creacion": {"bsonType": "date"},
        "fecha_actualizacion": {"bsonType": ["date", "null"]},
        "creado_por": {"bsonType": ["string", "null"]},
        "actualizado_por": {"bsonType": ["string", "null"]},
    },
}

ESQUEMA_FIRMAS = {
    "bsonType": "object",
    "required": ["usuario_id", "imagen", "bytes", "actualizado_en"],
    "description": "Firma del usuario como PNG procesado (fondo transparente). Colección aparte para no inflar el documento usuario.",
    "properties": {
        "usuario_id": {"bsonType": "objectId"},
        "imagen": {"bsonType": "binData", "description": "PNG con transparencia, ya procesado y optimizado"},
        "ancho": {"bsonType": ["int", "null"]},
        "alto": {"bsonType": ["int", "null"]},
        "bytes": {"bsonType": ["int", "long"], "description": "Tamaño del PNG procesado"},
        "actualizado_en": {"bsonType": "date"},
        "actualizado_por": {"bsonType": ["string", "null"]},
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
        "trazabilidad",
    ],
    "properties": {
        "numero_radicado": {
            "bsonType": "string",
            "description": "Debe ser un string y es obligatorio (Ej: RE26-0001)",
        },
        "asunto": {
            "bsonType": "string",
            "description": "Descripción del contenido del radicado",
        },
        "peticionario": {
            "bsonType": "string",
            "description": "Nombre de la persona o entidad que envía",
        },
        "estado_actual": {
            "enum": [
                "pendiente",
                "en_tramite",
                "en_revision",
                "respondido",
                "archivado",
                "traslado_competencia",
            ],
            "description": "Solo puede ser uno de los estados definidos",
        },
        "fecha_radicacion": {
            "bsonType": "date",
            "description": "Fecha y hora de ingreso al sistema",
        },
        "fecha_vencimiento": {
            "bsonType": "date",
            "description": "Fecha límite para dar respuesta oportuna",
        },
        "tipo": {"bsonType": "string"},
        "grupo": {"bsonType": "string"},
        "clase": {"bsonType": "string"},
        "creado_por": {
            "bsonType": "object",
            "required": ["usuario_id", "nombre", "fecha"],
            "properties": {
                "usuario_id": {"bsonType": "objectId"},
                "nombre": {"bsonType": "string"},
                "fecha": {"bsonType": "date"},
            },
            "description": "Usuario que creó la correspondencia",
        },
        "actualizado_por": {
            "bsonType": "object",
            "required": ["usuario_id", "nombre", "fecha"],
            "properties": {
                "usuario_id": {"bsonType": "objectId"},
                "nombre": {"bsonType": "string"},
                "fecha": {"bsonType": "date"},
            },
            "description": "Usuario que realizó la última actualización",
        },
        "responsable_actual": {
            "bsonType": "object",
            "required": ["usuario_id", "nombre", "fecha_asignacion"],
            "properties": {
                "usuario_id": {"bsonType": "objectId"},
                "nombre": {"bsonType": "string"},
                "fecha_asignacion": {"bsonType": "date"},
            },
            "description": "Opcional: No existe hasta que un coordinador lo asigne",
        },
        "respuesta": {
            "bsonType": "object",
            "properties": {
                "numero_oficio": {"bsonType": "string"},
                "fecha_salida": {"bsonType": "date"},
            },
            "description": "Opcional: Solo se completa al finalizar el trámite",
        },
        "observaciones_generales": {"bsonType": ["string", "null"]},
        "metadatos_adicionales": {"bsonType": "object"},
        "trazabilidad": {
            "bsonType": "array",
            "minItems": 1,
            "items": {
                "bsonType": "object",
                "required": ["fecha", "tipo_evento", "usuario_ejecutor", "estado_nuevo"],
                "properties": {
                    "fecha": {"bsonType": "date"},
                    "tipo_evento": {
                        "enum": [
                            "radicacion",
                            "asignacion",
                            "reasignacion",
                            "cambio_estado",
                            "carga_respuesta",
                            "cierre",
                        ]
                    },
                    "usuario_ejecutor": {"bsonType": "string"},
                    "estado_anterior": {"bsonType": ["string", "null"]},
                    "estado_nuevo": {"bsonType": "string"},
                    "responsable_anterior": {"bsonType": ["string", "null"]},
                    "responsable_nuevo": {"bsonType": ["string", "null"]},
                    "comentario": {"bsonType": ["string", "null"]},
                },
            },
        },
    },
}
