# Inventario de Páginas, Funciones y Permisos — Gestión SRTI-INVIAS

> **Para el administrador:** Este documento describe qué permiso necesita cada persona para acceder a cada sección del sistema. Úsalo como referencia al crear o editar usuarios.

---

## 1. Catálogo completo de permisos

| Clave de permiso | Descripción | Módulo |
|---|---|---|
| `usuario.ver` | Ver listado y detalle de usuarios | Usuarios |
| `usuario.crear` | Crear nuevos usuarios | Usuarios |
| `usuario.editar` | Editar datos de usuarios | Usuarios |
| `usuario.desactivar` | Activar / desactivar usuarios | Usuarios |
| `rol.ver` | Ver listado de roles | Roles |
| `rol.crear` | Crear roles | Roles |
| `rol.editar` | Editar permisos de roles | Roles |
| `rol.desactivar` | Desactivar roles | Roles |
| `dashboard.ver` | Acceso al dashboard de métricas globales | Dashboard |
| `reporte.ver` | Acceso a reportes y exportación (Excel/PDF) | Reportes |
| `correspondencia.ver` | Ver correspondencia asignada al usuario | Correspondencia |
| `correspondencia.crear` | Radicar nueva correspondencia | Correspondencia |
| `correspondencia.editar` | Editar y actualizar radicados existentes | Correspondencia |
| `certificacion.ver` | Ver los certificados propios del usuario | Certificaciones |
| `certificacion.aprobar` | Panel de supervisión: ver y descargar certificados de todos los colaboradores | Certificaciones |
| `certificacion.firmar_corr` | Firmar aprobación de Correspondencia (firmante designado) | Certificaciones |
| `certificacion.firmar_gd` | Firmar aprobación de Gestión Documental (firmante designado) | Certificaciones |
| `certificacion.firmar_secop` | Firmar aprobación de SECOP II (firmante designado) | Certificaciones |
| `certificacion.gestionar_firmantes` | Configurar quién ocupa cada rol de firmante | Certificaciones |
| `certificacion.firmar_financiera` | Firmar aprobación Financiera de actas (firmante designado) | Certificaciones |
| `certificacion.firmar_abogado` | Firmar aprobación Jurídica de actas (firmante designado) | Certificaciones |
| `certificacion.firmar_jefe` | Firmar aprobación del Jefe de actas (firmante designado) | Certificaciones |
| `grupo.gestionar_miembros` | Administrar todos los grupos de trabajo: asignar y retirar miembros (razón obligatoria al retirar) y designar líderes. El **líder** de un grupo (marca `es_lider` en su asignación, sin necesitar este permiso) gestiona solo los miembros de su grupo | Grupos |

> **Nota importante sobre los permisos de firma:** `firmar_corr`, `firmar_gd`, `firmar_secop`, `firmar_financiera`, `firmar_abogado` y `firmar_jefe` **no se asignan por rol**, se otorgan individualmente como `permisos_extra` al usuario cuando el administrador lo designa como firmante (Correspondencia/GD/SECOP desde "Aprobar Certificaciones"; Financiera/Abogado/Jefe desde "Seguimiento - Formatos" o "Sup. Formatos"). Esto permite que un administrador también pueda ser firmante sin que todos los admins tengan ese permiso.

---

## 2. Roles base del sistema

| Rol | Descripción | Permisos incluidos |
|---|---|---|
| `admin` | Administrador del sistema | Todos excepto `firmar_corr`, `firmar_gd`, `firmar_secop`, `firmar_financiera`, `firmar_abogado`, `firmar_jefe` |
| `supervisor` | Supervisor de certificaciones mensuales | `certificacion.ver`, `certificacion.aprobar`, `correspondencia.ver`, `dashboard.ver` |
| `firmante_certificacion` | Firmante designado — solo como base; el permiso específico de firma va en `permisos_extra` | `certificacion.ver`, `dashboard.ver` |
| `coordinador` | Coordinador de área | `correspondencia.ver`, `dashboard.ver`, `reporte.ver` |
| `asignacion` | Asignador de correspondencia | `correspondencia.ver`, `correspondencia.crear`, `correspondencia.editar`, `dashboard.ver` |
| `direccion` | Dirección / gerencia con acceso a reportes | `reporte.ver`, `dashboard.ver` |
| `lider` | Líder de equipo | `correspondencia.ver`, `dashboard.ver` |
| `gestor` | Gestor de correspondencia | `correspondencia.ver`, `dashboard.ver` |

---

## 3. Páginas y permisos requeridos

### Sección: Principal

Visible para **todos los usuarios con sesión activa**.

| Página en el menú | Archivo | Permiso mínimo | Funciones principales |
|---|---|---|---|
| Inicio | `main.py` (`pantalla_dashboard`) | Sesión activa | Métricas personales de correspondencia, accesos rápidos |
| Correspondencia | `pages/2_correspondencia.py` | Sesión activa | Gestión de radicados asignados; `correspondencia.crear` para radicar, `correspondencia.editar` para modificar |
| Mi Perfil | `pages/2_mi_perfil.py` | Sesión activa | Datos personales, documento de identidad, contratos activos |
| Instructivos | `pages/3_instructivos.py` | Sesión activa | Documentación de apoyo del equipo |

---

### Sección: Supervisión

"Mis Certificados" y "Verificar Certificado" son visibles para **todos**. El resto aparece según permiso.

| Página en el menú | Archivo | Permiso requerido | Funciones principales |
|---|---|---|---|
| Mis Certificados | `pages/6_certificaciones.py` | Sesión activa | Ver estado del certificado mensual propio, avance de firmas, contrato, descargar y previsualizar PDF |
| Verificar Certificado | `pages/8_verificar_cert.py` | Ninguno (acceso libre) | Validar autenticidad de un certificado por su código hash |
| Aprobar Certificaciones | `pages/9_firmantes_certif.py` | `firmar_corr` **ó** `firmar_gd` **ó** `firmar_secop` — también visible para rol `admin` (en modo lectura) | Panel de firmas por contratista; la firma de Correspondencia muestra un diálogo de confirmación con estadísticas del período a certificar |
| Certificar Colaboradores | `pages/7_admin_certif.py` | `certificacion.aprobar` | Vista del supervisor: estado de todos los colaboradores, indicadores de firmas/contrato/correspondencia, descarga y previsualización de PDFs de certificados |

---

### Sección: Administración

Aparece en el menú solo si el usuario tiene **al menos uno** de los permisos de esta sección.

| Página en el menú | Archivo | Permiso requerido | Funciones principales |
|---|---|---|---|
| Usuarios | `pages/1_admin_usuarios.py` | `usuario.ver` | Ver usuarios; crear (`usuario.crear`), editar (`usuario.editar`), activar/desactivar (`usuario.desactivar`), gestionar contratos y roles |
| Roles | `pages/3_admin_roles.py` | `rol.ver` | Ver roles; crear (`rol.crear`), editar (`rol.editar`), desactivar (`rol.desactivar`) |
| Dashboard | `pages/5_dashboard.py` | `dashboard.ver` | Métricas globales del sistema |
| Reportes y Evidencias | `pages/4_reportes.py` | `reporte.ver` | Exportar reportes de correspondencia en Excel y PDF |
| Grupos de trabajo | `pages/16_admin_grupos.py` | `grupo.gestionar_miembros` **o** ser líder de un grupo | Ver miembros activos; agregar y retirar miembros (con razón); designar líder (solo admin); historial de retiros |

---

## 4. Flujo del módulo de Certificaciones

El proceso de certificación mensual funciona así:

1. **Período habilitado:** Días 25 al fin del mes actual (mes en curso) o días 1 al 24 del mes siguiente (para el mes anterior).
2. **3 firmas requeridas** — cada firmante designado aprueba al contratista desde "Aprobar Certificaciones":
   - **F. Corr** (`firmar_corr`) → muestra un diálogo de confirmación con el número de solicitudes pendientes y vencidas del contratista para ese mes. El firmante acepta la responsabilidad explícitamente.
   - **F. GD** (`firmar_gd`)
   - **F. SECOP** (`firmar_secop`)
3. **Auto-certificación:** Al registrarse la 3ª firma, si el contratista tiene contrato activo registrado en su perfil, el sistema genera el certificado automáticamente. No hay un paso manual de "Certificar" adicional.
4. **Descarga y previsualización:**
   - El contratista accede desde "Mis Certificados" → descarga o previsualiza su PDF.
   - El supervisor accede desde "Certificar Colaboradores" → descarga o previsualiza el PDF de cualquier colaborador.
5. **Hash inmutable:** El código de verificación del certificado se genera una sola vez. Si el certificado se re-descarga, el hash no cambia, garantizando que copias impresas anteriormente sigan siendo válidas en la página "Verificar Certificado".

---

## 5. Guía rápida: ¿Qué permisos dar a cada perfil?

### Contratista / Colaborador regular
No necesita permisos adicionales. Solo iniciar sesión es suficiente para ver sus certificados.

**Rol sugerido:** `gestor` o `lider`

### Firmante designado
Asignar el rol `firmante_certificacion` y luego, desde "Aprobar Certificaciones" → configurar firmantes, designarlo en el tipo correspondiente (el sistema agrega el `permisos_extra` automáticamente):

| Tipo de firma | `permisos_extra` que se otorga |
|---|---|
| Correspondencia | `certificacion.firmar_corr` |
| Gestión Documental | `certificacion.firmar_gd` |
| SECOP II | `certificacion.firmar_secop` |

> Un administrador puede también ser firmante: se le asigna el permiso de firma como `permisos_extra` desde la misma pantalla de configuración.

### Supervisor de certificaciones
**Rol:** `supervisor`
Permisos incluidos: `certificacion.ver`, `certificacion.aprobar`, `correspondencia.ver`, `dashboard.ver`

### Coordinador de área
**Rol:** `coordinador`
Permisos incluidos: `correspondencia.ver`, `dashboard.ver`, `reporte.ver`

### Quien radica y asigna correspondencia
**Rol:** `asignacion`
Permisos incluidos: `correspondencia.ver`, `correspondencia.crear`, `correspondencia.editar`

### Dirección / Gerencia
**Rol:** `direccion`
Permisos incluidos: `reporte.ver`, `dashboard.ver`

### Administrador del sistema
**Rol:** `admin`
Tiene todos los permisos del sistema excepto los de firma de certificaciones (que se asignan individualmente por diseño).

---

## 6. Firmas secuenciales de Actas (Financiera / Abogado / Jefe)

Aplican a 3 formatos generados por el propio contratista desde "Formatos de contrato" (botón "✍️ Firmar y Generar Formato"): **Acta de compromiso**, **Balance General CPS** y **Acta de recibo y entrega CPS**. A diferencia del formato de Correspondencia/GD/SECOP, estos NO quedan aprobados de inmediato: nacen en estado `pendiente` y requieren aprobación de los roles designados, **en orden estricto**:

- **Acta de compromiso:** solo **Jefe**.
- **Balance General CPS** y **Acta de recibo y entrega CPS:** **Financiera → Abogado → Jefe**, en ese orden — un rol solo puede firmar si el anterior ya lo hizo.

Si un firmante revoca su aprobación después de que alguien firmó detrás de él, las firmas posteriores se revocan también en cascada y el documento vuelve a `pendiente`; el firmante afectado ve un aviso explicando por qué.

| Tipo de firma (actas) | `permisos_extra` que se otorga |
|---|---|
| Financiera | `certificacion.firmar_financiera` |
| Abogado | `certificacion.firmar_abogado` |
| Jefe | `certificacion.firmar_jefe` |

Se configuran desde el expander "⚙️ Configurar firmantes de Actas" en **Seguimiento - Formatos** (`pages/7_admin_certif.py`), y se aprueban desde los botones 2/3/4 de **Sup. Formatos** (`pages/9_firmantes_certif.py`).

---

## 7. Acciones puntuales y el permiso que las habilita

| Acción | Permiso requerido |
|---|---|
| Ver estado de mi certificado del mes | Sesión activa (cualquier usuario) |
| Ver avance de firmas y contrato propio | Sesión activa |
| Descargar mi propio PDF de certificado | Sesión activa (solo si el certificado está aprobado) |
| Verificar un certificado por código hash | Ninguno — página pública |
| Aprobar como firmante de Correspondencia | `certificacion.firmar_corr` |
| Aprobar como firmante de Gestión Documental | `certificacion.firmar_gd` |
| Aprobar como firmante de SECOP II | `certificacion.firmar_secop` |
| Revocar una firma propia | El mismo permiso de firma correspondiente |
| Configurar quiénes son los firmantes designados | `certificacion.gestionar_firmantes` |
| Ver panel de todos los colaboradores (supervisor) | `certificacion.aprobar` |
| Descargar PDF de un colaborador (supervisor) | `certificacion.aprobar` |
| Crear un usuario | `usuario.crear` |
| Editar un usuario (datos, roles, contratos) | `usuario.editar` |
| Activar o desactivar un usuario | `usuario.desactivar` |
| Ver el listado de usuarios | `usuario.ver` |
| Crear / editar roles | `rol.crear` / `rol.editar` |
| Ver métricas globales | `dashboard.ver` |
| Exportar reportes | `reporte.ver` |
| Radicar nueva correspondencia | `correspondencia.crear` |
| Editar radicados | `correspondencia.editar` |
