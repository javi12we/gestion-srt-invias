# GPT.md — Gestión de Correspondencia SRTI-INVIAS

Sistema interno de gestión de correspondencia para la Subdirección de Reglamentación Técnica e Innovación (SRTI) del Instituto Nacional de Vías (INVIAS).

## Stack

- **Framework UI:** Streamlit ≥ 1.35 (multi-page con `st.navigation()`)
- **Base de datos:** MongoDB (PyMongo 4.x) con validación de esquema JSON a nivel de colección
- **Autenticación:** bcrypt para hashes de contraseña, sesiones en `st.session_state`
- **Reportes:** ReportLab (PDF), XlsxWriter (Excel), Pandas
- **Config:** python-dotenv, archivo `.env` en raíz
- **Python:** 3.10+

## Arranque

```bash
pip install -r requirements.txt
python -m app.scripts.init_db      # crea colecciones, índices, catálogos y admin inicial
streamlit run app/main.py
```

Variables de entorno mínimas (ver `.env.example`):
- `MONGODB_URI` — cadena de conexión MongoDB
- `MONGODB_DB` — nombre de la base de datos (default: `gestion_srt`)
- `SECRET_KEY` — clave secreta de la app
- `ADMIN_INICIAL_PASSWORD` — contraseña del primer admin (solo en primer arranque)

## Arquitectura en capas

```text
pages / pages_admin   →   services   →   repositories   →   MongoDB
```

- **`app/pages/`** — páginas Streamlit de usuarios (correspondencia, perfil, instructivos, reportes, dashboard)
- **`app/pages_admin/`** — páginas de administración (usuarios, roles)
- **`app/services/`** — lógica de negocio (auth, correspondencia, usuarios, sesiones, reportes, etc.)
- **`app/repositories/`** — acceso a datos, sin lógica de negocio
- **`app/core/`** — utilidades transversales (sesión, autorización, seguridad, esquemas, permisos, zona horaria)
- **`app/db/`** — conexión a MongoDB
- **`app/config.py`** — `Configuracion` dataclass frozen cargada desde `.env`

## Colecciones MongoDB

| Colección | Descripción |
|-----------|-------------|
| `usuarios` | Cuentas de usuario con roles y permisos extra |
| `roles` | Definiciones de roles con permisos asociados |
| `permisos` | Catálogo de claves de permiso por módulo |
| `sesiones` | Registro de sesiones con inicio, cierre y duración |
| `opciones_configuracion` | Catálogos de dropdowns (tipo, grupo, clase, estados) |
| `correspondencia` | Radicados con trazabilidad (audit trail) completa |

Los esquemas y validadores están en `app/core/esquemas.py`.

## Sistema de permisos

Claves de permiso definidas en `app/core/permisos.py`:

- `usuario.*` — ver, crear, editar, desactivar
- `rol.*` — ver, crear, editar, desactivar
- `correspondencia.*` — ver, crear, editar
- `dashboard.ver`, `reporte.ver`

Los roles base están en `app/core/catalogos.py`. La autorización se valida en backend con `app/core/autorizacion.py`; nunca confiar solo en la UI.

## Patrones de código a mantener

- Toda operación de escritura en `correspondencia` debe agregar entrada al array `trazabilidad` del documento.
- Los servicios no acceden directamente a MongoDB; usan el repositorio correspondiente.
- Las páginas Streamlit no contienen lógica de negocio; delegan a services.
- Usar `app/core/zona_horaria.py` para todas las fechas (zona horaria Colombia).
- Los errores de negocio se muestran con `st.error()` o `st.warning()`; nunca dejar excepciones sin manejar en las páginas.
- La configuración de la app se lee siempre desde `Configuracion` (singleton en `app/config.py`), nunca directamente desde `os.environ`.

## Branding y estilos

- Colores corporativos INVIAS: naranja `#FF8C00` / `#FF9800` sobre fondos oscuros/claros.
- El CSS de la app vive en `app/main.py` (función de estilos al inicio).
- Hay modo oscuro togglable desde el sidebar; las páginas deben ser compatibles con ambos modos.
- Logos en `app/assets/`.

## Testing

El proyecto está en etapa MVP; no hay suite de pruebas automatizadas aún. Al agregar tests, usar pytest con fixtures de MongoDB en memoria o una instancia local de prueba.

## Despliegue

- Soporta devcontainer (`.devcontainer/`).
- Entornos separados: `.env.develop` y `.env.prod`.
- El script `init_db` es idempotente y seguro de ejecutar en cada despliegue.
