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
]

ROLES_BASE = [
    {
        "nombre": "admin",
        "descripcion": "Administrador del sistema",
        "permisos": [permiso["clave"] for permiso in PERMISOS_BASE],
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
]
