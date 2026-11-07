# CLAUDE.md — Gestión de Correspondencia SRTI-INVIAS

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

```
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
| `certificaciones` | Certificaciones mensuales y actas con firmas secuenciales |
| `firmas` | Firma PNG procesada por usuario |
| `instructivos` | Instructivos de ayuda |
| `politicas_datos` / `aceptaciones_politica` | Política de tratamiento de datos y su aceptación |
| `notificaciones_correo` | Avisos por correo ya enviados (anti-repetición) |
| `grupos_trabajo` | Catálogo de grupos de trabajo |
| `asignaciones_grupo` | Pertenencia de usuarios a grupos (estado, razón, trazabilidad) |
| `suit_asignaciones` | Quién diligencia cada trámite SUIT (un documento por periodo de encargo, con historial) |
| `suit_cargues` | Cargue mensual SUIT: un documento por (trámite, año, mes) con 7 contadores y trazabilidad |

Los esquemas y validadores están en `app/core/esquemas.py`.

**Grupos de trabajo:** `grupos_trabajo` es el catálogo (despacho, permisos, normativa_tecnica, innovacion_tecnica; sembrado por `init_db`). `asignaciones_grupo` es la fuente de la pertenencia: un documento por periodo con `estado` activo/retirado, `es_lider`, razón de retiro y trazabilidad; un usuario puede estar activo en varios grupos. Solo el administrador (`grupo.gestionar_miembros`) o el líder del grupo asigna y retira miembros (únicamente el admin designa líderes o retira a uno); el usuario ya no elige su grupo. Lógica en `app/services/asignacion_grupo_service.py`; página en Administración › Grupos de trabajo (`pages_admin/admin_grupos.py`). La sesión trae `grupos` y `grupos_lider`, y el menú los lee de ahí. `usuarios.informacion_laboral.grupo_trabajo` es solo un dato histórico (se muestra de solo lectura); `python -m app.scripts.migrar_grupos_usuarios` (simula por defecto, `--aplicar` escribe) lo copia a `asignaciones_grupo` y debe ejecutarse en cada entorno antes de desplegar.

**SUIT (grupo Permisos):** los 7 trámites y los campos del formulario están en `app/core/catalogos.py` (`TRAMITES_SUIT`, `CAMPOS_SUIT`). La asignación de trámites vive en `suit_asignaciones` (no en `usuarios.permisos_extra`): el administrador asigna cualquier trámite; el líder del grupo `permisos` solo reparte los que él mismo tiene. Cargues siempre editables, por mes; el avance (semáforo) se calcula con `SuitService.progreso`. Lógica en `app/services/suit_service.py`. La pestaña **Seguimiento** (`app/core/ui_suit_seguimiento.py`, datos por `cache_datos.seguimiento_suit`) es de solo lectura y la ve (igual que **Reporte**, con descarga del Excel por año, `app/core/ui_suit_reporte.py`) todo el que ve el SUIT en el menú: admin, miembro activo del grupo `permisos` o rol/permiso con `grupo.permisos.ver` (`SuitService.puede_ver_suit`), tenga o no trámites asignados; un mes está «vencido» cuando ya terminó sin cargue. El formulario solo guarda 6 campos de entrada (`CAMPOS_SUIT`); «Total solicitudes resueltas» y «Número de PQRD recibidas» son totales calculados (`TOTALES_SUIT`, `SuitService.totales`), nunca se guardan: resueltas = en línea + presencial (fila 10 del formato) y PQRD recibidas = resueltas + otras + quejas + reclamos + denuncias (fila 9), por lo que resueltas ≤ PQRD siempre. El semáforo del cargue es rojo/verde según falte o no un mes ya vencido (`SuitService.progreso`). El Excel del formato SUIT se genera editando por dentro la plantilla `app/assets/plantillas/plantilla_suit_original.xlsx` (`app/services/suit_excel_service.py`, sobre `app/core/xlsx_paquete.py`; no usar openpyxl: pierde los gráficos). `python -m app.scripts.migrar_permisos_suit` (simula por defecto, `--aplicar` escribe) pasa las claves `suit.ver_*` antiguas de `permisos_extra` a `suit_asignaciones`; ejecutarlo en cada entorno después de `init_db`.

## Sistema de permisos

Claves de permiso definidas en `app/core/permisos.py`:

- `usuario.*` — ver, crear, editar, desactivar
- `rol.*` — ver, crear, editar, desactivar
- `correspondencia.*` — ver, crear, editar
- `dashboard.ver`, `reporte.ver`
- Otros: `certificacion.*` (ver, aprobar, firmar_*, gestionar_firmantes), `pago.cargar`, `grupo.<grupo>.ver`, `grupo.gestionar_miembros`, `suit.*`

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
