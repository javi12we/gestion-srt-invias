# GEMINI.md — Gestión de Correspondencia SRTI-INVIAS

Sistema interno de gestión de correspondencia para la Subdirección de Reglamentación Técnica e Innovación (SRTI) del Instituto Nacional de Vías (INVIAS), Colombia.

## Stack

- **UI:** Streamlit ≥ 1.35 (multi-page con `st.navigation()`)
- **Base de datos:** MongoDB (PyMongo 4.x) con validación de esquema JSON en colecciones
- **Auth:** bcrypt para hashes de contraseña; sesiones en `st.session_state`
- **Reportes:** ReportLab (PDF), XlsxWriter (Excel), Pandas
- **Config:** python-dotenv + `.env`
- **Python:** 3.10+

## Arranque rápido

```bash
pip install -r requirements.txt
python -m app.scripts.init_db      # crea colecciones, índices, catálogos y admin inicial
streamlit run app/main.py
```

Variables en `.env`: `MONGODB_URI`, `MONGODB_DB`, `SECRET_KEY`, `ADMIN_INICIAL_PASSWORD`.

## Arquitectura en capas

```
pages / pages_admin  →  services  →  repositories  →  MongoDB
```

| Carpeta | Rol |
|---------|-----|
| `app/pages/` | Páginas Streamlit de usuario |
| `app/pages_admin/` | Páginas de administración |
| `app/services/` | Lógica de negocio (no toca MongoDB) |
| `app/repositories/` | Acceso a datos (único punto MongoDB) |
| `app/core/` | Utilidades transversales |
| `app/config.py` | `Configuracion` dataclass — fuente única de config |

## Reglas de desarrollo

1. **Separación de capas:** páginas → services → repositories. No saltarse capas.
2. **Trazabilidad:** toda escritura en `correspondencia` agrega entrada al array `trazabilidad`.
3. **Autorización en backend:** validar con `app/core/autorizacion.py`, no solo en UI.
4. **Fechas:** siempre usar `app/core/zona_horaria.py` (Colombia, America/Bogota).
5. **Configuración:** solo desde `Configuracion` importada de `app/config.py`.
6. **Errores UI:** `st.error()` / `st.warning()`; sin excepciones sin manejar en páginas.

## Colecciones MongoDB

`usuarios`, `roles`, `permisos`, `sesiones`, `opciones_configuracion`, `correspondencia`.
Esquemas en `app/core/esquemas.py`. El `init_db` es idempotente.

## Sistema de permisos

Claves en `app/core/permisos.py`:
- `usuario.ver/crear/editar/desactivar`
- `rol.ver/crear/editar/desactivar`
- `correspondencia.ver/crear/editar`
- `dashboard.ver`, `reporte.ver`

Roles base (en `app/core/catalogos.py`): admin, direccion, asignacion, coordinador, lider, gestor.

## Branding

Colores INVIAS: `#FF8C00` / `#FF9800`. CSS en `app/main.py`. Logos en `app/assets/`. Modo oscuro soportado.
