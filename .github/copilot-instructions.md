# GitHub Copilot Instructions — Gestión de Correspondencia SRTI-INVIAS

Sistema Streamlit + MongoDB para gestión de correspondencia de la SRTI del INVIAS (Colombia).

## Stack y entorno

- Python 3.10+, Streamlit ≥ 1.35, PyMongo 4.x, bcrypt, ReportLab, XlsxWriter, Pandas
- MongoDB con validación de esquema JSON a nivel de colección
- Configuración desde `.env` vía `app/config.py` (`Configuracion` dataclass frozen)

## Estructura de directorios

```
app/
  main.py              # Entrada Streamlit, CSS de branding, navegación
  config.py            # Configuracion dataclass (singleton de configuración)
  pages/               # Páginas de usuario (correspondencia, perfil, reportes…)
  pages_admin/         # Páginas de admin (usuarios, roles)
  services/            # Lógica de negocio
  repositories/        # Acceso a datos MongoDB
  core/
    autorizacion.py    # Validación de permisos en backend
    permisos.py        # Claves de permiso
    catalogos.py       # Roles base
    esquemas.py        # Esquemas JSON para MongoDB
    zona_horaria.py    # Fechas en zona horaria Colombia
    sesion.py          # Estado de sesión Streamlit
    seguridad.py       # Hashing bcrypt
  db/                  # Conexión MongoDB
  assets/              # Logos INVIAS
  scripts/
    init_db.py         # Bootstrap idempotente de la BD
```

## Patrones que Copilot debe seguir

### Separación de capas
- Las páginas (`pages/`, `pages_admin/`) solo llaman a **services**; nunca a repositories ni a MongoDB.
- Los services solo acceden a datos a través de **repositories**.
- Los repositories son el único punto que usa `pymongo` directamente.

### Trazabilidad obligatoria
Cualquier modificación a un documento de `correspondencia` debe agregar una entrada al array `trazabilidad` dentro del mismo documento. No omitir este paso.

### Autorización en backend
Siempre validar permisos con `app/core/autorizacion.py` en el service correspondiente. Ocultar elementos en la UI es insuficiente.

### Fechas
Usar siempre `app/core/zona_horaria.py` para obtener `datetime.now()` en zona horaria Colombia (America/Bogota). No usar `datetime.utcnow()` ni `datetime.now()` sin zona horaria.

### Configuración
Leer configuración desde `Configuracion` (importada de `app/config.py`), nunca desde `os.environ` directamente.

### Manejo de errores en UI
En páginas Streamlit: capturar excepciones de negocio y mostrar `st.error()` o `st.warning()`. No dejar `st.exception()` en producción.

## Colecciones MongoDB

`usuarios`, `roles`, `permisos`, `sesiones`, `opciones_configuracion`, `correspondencia`.

## Permisos disponibles

`usuario.ver`, `usuario.crear`, `usuario.editar`, `usuario.desactivar`,
`rol.ver`, `rol.crear`, `rol.editar`, `rol.desactivar`,
`correspondencia.ver`, `correspondencia.crear`, `correspondencia.editar`,
`dashboard.ver`, `reporte.ver`.

## Estilos

CSS inline en `app/main.py`. Colores corporativos INVIAS: `#FF8C00` / `#FF9800`. Compatible con modo oscuro.
