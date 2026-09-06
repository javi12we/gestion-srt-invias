TIPOS_CONTRATO = {
    "": "— Sin especificar —",
    "termino_indefinido": "Término indefinido",
    "termino_fijo": "Término fijo",
    "obra_labor": "Obra o labor",
    "prestacion_servicios": "Prestación de servicios",
    "aprendizaje": "Aprendizaje",
}

# Tipos de documento admitidos para un dependiente económico
TIPOS_DOC_DEPENDIENTE = {
    "": "— Sin especificar —",
    "CC": "CC — Cédula de Ciudadanía",
    "TI": "TI — Tarjeta de Identidad",
    "CE": "CE — Cédula de Extranjería",
    "RC": "RC — Registro Civil",
    "OTRO": "Otro",
}

# Tipos de cuenta bancaria admitidos
TIPOS_CUENTA_BANCARIA = {
    "": "— Sin especificar —",
    "ahorros": "Cuenta de Ahorros",
    "corriente": "Cuenta Corriente",
    "cts": "Cuenta de Trámite Simplificado (CTS/ Depósitos Electrónicos)",
}

# Grupos de trabajo
GRUPOS_TRABAJO = {
    "": "— Sin especificar —",
    "despacho": "DESPACHO",
    "normativa_tecnica": "NORMATIVA",
    "innovacion_tecnica": "INNOVACIÓN",
    "permisos": "PERMISOS",
}


# Fuente única de los 7 permisos SUIT que puede tramitar la entidad. Se usa para
# generar el catálogo de permisos de app (PERMISOS_BASE) y para construir tanto los
# botones de "Cargue SUIT Permiso" como el multiselect de asignación en Gestores Perm.
PERMISOS_SUIT_CARGUE = [
    {
        "clave": "suit.ver_carga_extradimensionada",
        "label_corto": "Movilización de carga extradimensionada",
        "nombre_completo": "Permiso para movilización de carga extradimensionada por las vías nacionales.",
    },
    {
        "clave": "suit.ver_carga_indivisible_vcc",
        "label_corto": "Carga indivisible y extra pesada ..-V.C.C",
        "nombre_completo": (
            "Permiso para la movilización de carga indivisible extrapesada, indivisible extradimensionada "
            "o indivisible extrapesada y extradimensionada a la vez y permiso para el transporte de carga "
            "divisible con vehículos combinados de carga - V.C.C."
        ),
    },
    {
        "clave": "suit.ver_concepto_estaciones_servicio",
        "label_corto": "Concepto Técnico de Ubicación de Estaciones de Servicios",
        "nombre_completo": "Concepto Técnico de Ubicación de Estaciones de Servicios.",
    },
    {
        "clave": "suit.ver_cierre_vias",
        "label_corto": "Permiso de cierre de vías",
        "nombre_completo": "Permiso de cierre de vías.",
    },
    {
        "clave": "suit.ver_uso_zona_via",
        "label_corto": "Permiso de uso de zona de vía",
        "nombre_completo": "Permiso de uso de zona de vía.",
    },
    {
        "clave": "suit.ver_tarifa_diferencial_peajes",
        "label_corto": "Permiso Tarifa Diferencial o Exenta en peajes INVIAS",
        "nombre_completo": "Permiso Tarifa Diferencial o Exenta en las estaciones de peaje a cargo del INVIAS.",
    },
    {
        "clave": "suit.ver_obras_riberas_rios",
        "label_corto": "Construcción de obras en riberas de ríos y vías fluviales",
        "nombre_completo": (
            "Permiso para la construcción de obras en las riberas de los ríos o dentro de su cauce "
            "y en las demás vías fluviales."
        ),
    },
]


PERMISOS_BASE = [
    {"clave": "usuario.ver", "descripcion": "Ver usuarios", "modulo": "usuarios"},
    {"clave": "usuario.crear", "descripcion": "Crear usuarios", "modulo": "usuarios"},
    {"clave": "usuario.editar", "descripcion": "Editar usuarios", "modulo": "usuarios"},
    {"clave": "usuario.desactivar", "descripcion": "Desactivar usuarios", "modulo": "usuarios"},
    {"clave": "rol.ver", "descripcion": "Ver roles", "modulo": "roles"},
    {"clave": "rol.crear", "descripcion": "Crear roles", "modulo": "roles"},
    {"clave": "rol.editar", "descripcion": "Editar roles", "modulo": "roles"},
    {"clave": "rol.desactivar", "descripcion": "Desactivar roles", "modulo": "roles"},
    {"clave": "dashboard.ver", "descripcion": "Ver dashboard", "modulo": "dashboard"},
    {"clave": "reporte.ver", "descripcion": "Ver reportes", "modulo": "reportes"},
    {"clave": "correspondencia.ver", "descripcion": "Ver correspondencia", "modulo": "correspondencia"},
    {"clave": "correspondencia.crear", "descripcion": "Crear correspondencia", "modulo": "correspondencia"},
    {"clave": "correspondencia.editar", "descripcion": "Editar correspondencia", "modulo": "correspondencia"},
    {"clave": "certificacion.ver", "descripcion": "Ver certificaciones propias", "modulo": "certificaciones"},
    {"clave": "certificacion.aprobar", "descripcion": "Aprobar certificaciones de colaboradores", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_corr", "descripcion": "Firmar aprobación de Correspondencia", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_gd", "descripcion": "Firmar aprobación de Gestión Documental", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_secop", "descripcion": "Firmar aprobación de SECOP II", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_financiera", "descripcion": "Firmar aprobación Financiera (actas)", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_abogado", "descripcion": "Firmar aprobación Jurídica (actas)", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_jefe", "descripcion": "Firmar aprobación del Jefe (actas)", "modulo": "certificaciones"},
    {"clave": "certificacion.gestionar_firmantes", "descripcion": "Configurar firmantes designados de certificaciones", "modulo": "certificaciones"},
    {"clave": "grupo.despacho.ver", "descripcion": "Ver sección de Despacho", "modulo": "grupos"},
    {"clave": "grupo.permisos.ver", "descripcion": "Ver sección de Permisos (SUIT)", "modulo": "grupos"},
    {"clave": "grupo.normativa_tecnica.ver", "descripcion": "Ver sección de Normativa Técnica", "modulo": "grupos"},
    {"clave": "grupo.innovacion_tecnica.ver", "descripcion": "Ver sección de Innovación Técnica", "modulo": "grupos"},
] + [
    {"clave": p["clave"], "descripcion": f"Ver y cargar: {p['label_corto']}", "modulo": "suit"}
    for p in PERMISOS_SUIT_CARGUE
]

_PERMISOS_SOLO_FIRMANTES = {
    "certificacion.firmar_corr",
    "certificacion.firmar_gd",
    "certificacion.firmar_secop",
    "certificacion.firmar_financiera",
    "certificacion.firmar_abogado",
    "certificacion.firmar_jefe",
}

ROLES_BASE = [
    {
        "nombre": "admin",
        "descripcion": "Administrador del sistema",
        "permisos": [p["clave"] for p in PERMISOS_BASE if p["clave"] not in _PERMISOS_SOLO_FIRMANTES],
        "activo": True,
    },
    {
        "nombre": "firmante_certificacion",
        "descripcion": "Firmante designado para aprobación de certificaciones",
        "permisos": ["certificacion.ver"],
        "activo": True,
    },
    {
        "nombre": "direccion",
        "descripcion": "Dirección con acceso a reportes",
        "permisos": ["reporte.ver", "dashboard.ver"],
        "activo": True,
    },
    {
        "nombre": "asignacion",
        "descripcion": "Rol de asignación de correspondencia",
        "permisos": ["correspondencia.ver", "correspondencia.crear", "correspondencia.editar"],
        "activo": True,
    },
    {
        "nombre": "coordinador",
        "descripcion": "Coordinador de área",
        "permisos": ["correspondencia.ver", "dashboard.ver", "reporte.ver"],
        "activo": True,
    },
    {
        "nombre": "lider",
        "descripcion": "Líder de equipo",
        "permisos": ["correspondencia.ver"],
        "activo": True,
    },
    {
        "nombre": "gestor",
        "descripcion": "Gestor de correspondencia",
        "permisos": ["correspondencia.ver"],
        "activo": True,
    },
    {
        "nombre": "supervisor",
        "descripcion": "Supervisor de certificaciones mensuales",
        "permisos": [
            "certificacion.ver",
            "certificacion.aprobar",
            "correspondencia.ver",
            "dashboard.ver",
        ],
        "activo": True,
    },
]
