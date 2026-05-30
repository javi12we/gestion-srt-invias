# AGENTS.md — Gestión de Correspondencia SRTI-INVIAS

Sistema interno de gestión de correspondencia para la Subdirección de Reglamentación Técnica e Innovación (SRTI) del Instituto Nacional de Vías (INVIAS), Colombia.

## Stack

- **UI:** Streamlit ≥ 1.35 (multi-page con `st.navigation()`)
- **Base de datos:** MongoDB (PyMongo 4.x) con validación de esquema JSON a nivel de colección
- **Auth:** bcrypt para hashes, sesiones en `st.session_state`
- **Reportes:** ReportLab (PDF), XlsxWriter (Excel), Pandas
- **Config:** python-dotenv + archivo `.env`
- **Python:** 3.10+

## Arranque

```bash
pip install -r requirements.txt
python -m app.scripts.init_db      # colecciones, índices, catálogos y admin inicial
streamlit run app/main.py
```

Variables requeridas en `.env` (ver `.env.example`): `MONGODB_URI`, `MONGODB_DB`, `SECRET_KEY`, `ADMIN_INICIAL_PASSWORD`.

## Arquitectura

```
pages / pages_admin  →  services  →  repositories  →  MongoDB
```

- `app/pages/` — páginas Streamlit (correspondencia, perfil, instructivos, reportes, dashboard)
- `app/pages_admin/` — páginas de administración (usuarios, roles)
- `app/services/` — lógica de negocio; nunca accede a MongoDB directamente
- `app/repositories/` — único punto de acceso a MongoDB; sin lógica de negocio
- `app/core/` — utilidades transversales (sesión, autorización, seguridad, esquemas, permisos, zona horaria)
- `app/config.py` — `Configuracion` dataclass frozen; única fuente de configuración

## Colecciones MongoDB

`usuarios`, `roles`, `permisos`, `sesiones`, `opciones_configuracion`, `correspondencia`.
Esquemas y validadores en `app/core/esquemas.py`. El script `init_db` es idempotente.

## Permisos y roles

Claves en `app/core/permisos.py`. Roles base en `app/core/catalogos.py`. Validación en `app/core/autorizacion.py`.

**Claves:** `usuario.*`, `rol.*`, `correspondencia.*`, `dashboard.ver`, `reporte.ver`.
**Roles:** admin, direccion, asignacion, coordinador, lider, gestor.

## Reglas de desarrollo

1. Las páginas Streamlit **no** contienen lógica de negocio; delegan a services.
2. Los services **no** acceden a MongoDB directamente; usan repositories.
3. Toda escritura en `correspondencia` **debe** agregar entrada al array `trazabilidad`.
4. La autorización se valida en backend (`autorizacion.py`), nunca solo en UI.
5. Todas las fechas usan `app/core/zona_horaria.py` (zona horaria Colombia).
6. La configuración se lee desde `Configuracion`, nunca desde `os.environ` directamente.
7. Errores de negocio en páginas: `st.error()` / `st.warning()`, nunca excepciones sin manejar.

## Branding

Colores INVIAS: naranja `#FF8C00` / `#FF9800`. CSS en `app/main.py`. Logos en `app/assets/`. Soporta modo oscuro.
