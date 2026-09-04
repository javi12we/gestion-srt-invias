# Selector de período (año/mes) para Formatos de contrato y Sup. Formatos

## Contexto

Hoy todo el módulo de certificaciones mensuales opera sobre un único período implícito: `CertificacionService.periodo_certificable()` (`app/services/certificacion_service.py:66`), que devuelve el mes actual o el anterior según el día del mes comparado contra el parámetro configurable `dia_inicio_periodo_certificacion` (`ParametrosService`). Esta función se llama de forma interna y hardcodeada en:

- Las 4 funciones de autofirma: `firmar_y_generar_dependencia` (:107), `firmar_y_generar_cuenta_cobro` (:139), `firmar_y_generar_retencion_primera` (:172), `firmar_y_generar_retencion_segunda` (:205).
- Las 3 funciones de actas: `firmar_y_generar_acta_compromiso` (:238), `firmar_y_generar_acta_recibo_entrega` (:264), `firmar_y_generar_acta_recibo_entrega_cps_real` (:290).
- `obtener_certificacion_periodo_actual` (:104), `obtener_empleados_para_certificar` (:328), `registrar_firma`/`revocar_firma` (:436 y siguiente), `registrar_firma_actas`/`revocar_firma_actas`.
- En la UI: `app/pages/6_certificaciones.py` (contratista, título "Formatos de contrato"), `app/pages_admin/admin_firmantes.py:519` (supervisor, título "Sup. Formatos") y `app/pages_admin/admin_certificaciones.py:243` (solo lectura, título "Seguimiento - Formatos").

No existe ningún `st.selectbox` de año/mes en ninguna de las tres páginas. La pestaña "Historial de formatos" del contratista sí lista todos los períodos pasados, pero sin filtro ni selector — simplemente pinta una tarjeta por cada documento histórico encontrado.

El dato para soportar selección de período ya existe sin cambios de esquema: cada documento de `certificaciones` tiene `año`/`mes` obligatorios (`ESQUEMA_CERTIFICACIONES`, `app/core/esquemas.py:288-393`), con índice compuesto `(año, mes)` (`idx_cert_periodo`) y `(usuario_id, año, mes)` (`idx_cert_usuario_periodo`). La generación de PDF ya es "período-consciente": usa `_contrato_para_periodo(contratos, año_cert, mes_cert)` (:692) para tomar el contrato vigente en el mes del **documento**, no el de hoy — es decir, descargar un PDF histórico ya funciona correctamente hoy. Lo único atado al "hoy" está en las funciones que *crean o firman* documentos.

## Adenda (post-implementación): adelanto de 1 mes

Además de navegar hacia atrás, el selector permite adelantarse **exactamente 1 mes** por delante del período certificable actual (`MESES_ADELANTO_FIRMA = 1` en `certificacion_service.py`), en **ambas páginas** (contratista y supervisor) y para los 8 formatos por igual — mismo mecanismo, mismo selector, sin páginas ni lógica nuevas. Valor fijo en código (no configurable por admin) por decisión explícita del usuario. El límite superior real del selector es entonces "período certificable + 1 mes", no "período certificable".

`leyenda_periodo` gana un tercer caso ("Período futuro — ... (adelanto de firma, aún no ha transcurrido)") para los períodos por delante del actual, y el índice por defecto de ambos `st.selectbox` ya no es `0` sino la posición de `periodo_certificable()` dentro de la lista (el mes de adelanto queda primero en la lista pero **no** preseleccionado, preservando "cero cambios si nadie toca el selector").

## Alcance

- Selector de año/mes en **"Formatos de contrato"** (`app/pages/6_certificaciones.py`, vista contratista): permite generar/gestionar retroactivamente cualquiera de los 8 formatos para un mes pasado, no solo el período certificable actual.
- Selector de año/mes en **"Sup. Formatos"** (`app/pages_admin/admin_firmantes.py`, vista supervisor): permite firmar/aprobar pendientes de meses anteriores, no solo el período certificable actual.
- Aplica a los **8 formatos por igual**: cuenta de cobro, retención primera, retención segunda, dependencia económica, Gestión Corr-GD-SECOP (corr/gd/secop), y las 3 actas (acta_compromiso, acta_recibo_entrega_cps, acta_recibo_entrega_cps_real) con su firma secuencial estricta financiera→abogado→jefe.
- Mensaje/leyenda de período unificado y coherente con el mes efectivamente seleccionado (ver sección dedicada), reemplazando los avisos actuales que asumen que el único período posible es "el actual" o "el mes anterior automático".

## Fuera de alcance

- `app/pages_admin/admin_certificaciones.py` ("Seguimiento - Formatos", solo lectura/monitoreo) no recibe el selector en esta iteración — sigue mostrando el período certificable actual como hoy. Queda anotado como posible follow-up por consistencia, no se implementa ahora.
- No se modifica `periodo_certificable()`, `es_mes_anterior()`, `dia_inicio_periodo_certificacion` ni la ventana de gracia de 60 días para contratos finalizados (`DIAS_GRACIA_DESCARGA_FORMATOS`). Todo eso sigue gobernando exactamente igual si el módulo está "desbloqueado" hoy.
- No se cambian las reglas de bloqueo de descarga (`UsuarioService.faltantes_para_formatos`): siguen evaluando el estado de HOY del usuario (datos personales, contrato activo, firma cargada, información laboral), sin importar qué período esté seleccionado en el módulo.
- No se re-valida ni se migra nada de los documentos históricos ya existentes.
- No se cambia el orden ni la lógica de revocación en cascada de las actas (`ORDEN_FIRMAS_ACTAS`) — esa lógica ya opera por documento individual (usuario+año+mes), es naturalmente segura al aplicarse a un período distinto al actual.
- No se agregan campos nuevos al esquema de `certificaciones` — el modelo de datos ya soporta esto.

## Modelo de datos

Sin cambios de esquema. Se agregan dos métodos de solo lectura en `CertificacionService`:

- `periodos_disponibles_usuario(usuario_id) -> list[tuple[int, int]]`: calcula el rango de períodos seleccionables para un contratista, desde el mes de la `fecha_inicio` más antigua entre sus contratos (respetando prórroga, mismo criterio que `_contrato_para_periodo`) hasta `periodo_certificable()` inclusive, orden descendente (más reciente primero). Si el usuario no tiene contratos, devuelve solo `[periodo_certificable()]`.
- `periodos_disponibles_global() -> list[tuple[int, int]]`: mismo cálculo pero tomando la `fecha_inicio` más antigua entre **todos** los contratos de **todos** los usuarios, para poblar el selector del supervisor (que no está atado a un solo contratista). Se evalúa en el plan de implementación si conviene cachear este resultado (ver `app/core/cache_datos.py`) dado que implica recorrer todos los usuarios.

## Cambios en `CertificacionService`

Los siguientes métodos ganan parámetros opcionales `año: int | None = None, mes: int | None = None`, con `if año is None or mes is None: año, mes = self.periodo_certificable()` como primera línea — **100% retrocompatible**, cualquier llamador que no pase el período obtiene exactamente el comportamiento actual:

- `obtener_certificacion_periodo_actual`
- `firmar_y_generar_dependencia`, `firmar_y_generar_cuenta_cobro`, `firmar_y_generar_retencion_primera`, `firmar_y_generar_retencion_segunda`
- `firmar_y_generar_acta_compromiso`, `firmar_y_generar_acta_recibo_entrega`, `firmar_y_generar_acta_recibo_entrega_cps_real`
- `obtener_empleados_para_certificar` (además, internamente cambia `self._contrato_vigente(contratos)` por `self._contrato_para_periodo(contratos, año, mes)` para que el filtro de "tiene contrato" sea correcto en el período elegido, no en el de hoy)
- `registrar_firma`, `revocar_firma`, `registrar_firma_actas`, `revocar_firma_actas`

La lógica interna de cada uno no cambia (buscar existente vs. crear, reutilizar `hash_verificacion`, disparar `_intentar_auto_certificar`) — solo deja de recalcular el período y usa el que recibe.

## Mensaje de período (leyenda unificada)

Hoy existen mensajes hardcodeados que asumen que el período mostrado es siempre "el actual" o, como mucho, "el mes anterior" dentro de la ventana automática de gracia (ej. `admin_firmantes.py:546-549`, `admin_certificaciones.py:255-262`). Con el selector, un usuario puede elegir manualmente cualquier mes pasado, por lo que esos mensajes dejarían de ser coherentes con lo que realmente se está firmando o generando.

Se reemplazan por una única función compartida, p.ej. `leyenda_periodo(servicio, año, mes) -> str`, usada en ambas páginas, que arma el mensaje según la relación entre el período **seleccionado** y `periodo_certificable()`:

1. Si `(año, mes) == periodo_certificable()` y `es_mes_anterior()` es verdadero → `"📅 Mes anterior: **{nombre_mes} {año}** (ventana disponible hasta el día {dia_cierre} de este mes)"`.
2. Si `(año, mes) == periodo_certificable()` y `es_mes_anterior()` es falso → `"📅 Período actual: **{nombre_mes} {año}**"`.
3. Si `(año, mes)` es anterior a `periodo_certificable()` (selección manual retroactiva) → `"📅 Período pasado: **{nombre_mes} {año}** — gestión retroactiva, fuera de la ventana automática"`.

De esta forma el mensaje siempre describe el mes que efectivamente se va a firmar/generar/descargar, sin importar si llegó ahí por el cálculo automático o por selección manual en el dropdown.

## UI — vista del contratista (`app/pages/6_certificaciones.py`)

- Selector nuevo al inicio de la página (antes del menú de 8 formatos), un único `st.selectbox` combinado "{Mes} {Año}" poblado con `periodos_disponibles_usuario(usuario_id)`, ordenado descendente, con `periodo_certificable()` preseleccionado por defecto.
- El valor elegido se guarda en `st.session_state["cert_periodo_seleccionado"]` y se pasa como `(año, mes)` a cada `_render_opcion_*` y a cada llamada de servicio, reemplazando su dependencia implícita de "hoy".
- Se muestra la leyenda unificada (sección anterior) justo debajo del selector.
- El botón "Historial de formatos" se mantiene igual (lista completa sin filtro) — es un caso de uso distinto (ver todo lo generado) al del selector (elegir sobre qué mes trabajar ahora).
- Las reglas de bloqueo (`_aviso_bloqueado`, condicionado por `faltantes_para_formatos`) se evalúan igual que hoy, independientemente del período elegido en el selector.

## UI — vista del supervisor (`app/pages_admin/admin_firmantes.py`, "Sup. Formatos")

- Mismo patrón de selector al inicio de la página, poblado con `periodos_disponibles_global()`, con `periodo_certificable()` preseleccionado por defecto.
- El período elegido controla tanto el panel de corr/gd/secop como `_render_panel_actas` — la lista de contratistas, sus estados de firma y los botones de aprobar/revocar se calculan todos sobre el período seleccionado en vez de sobre `periodo_certificable()`.
- Se muestra la misma leyenda unificada. El diálogo de confirmación (`_dialog_confirmar_firma`) recibe el período seleccionado en vez de recalcularlo.
- Para actas: el orden financiera→abogado→jefe y la revocación en cascada se evalúan sobre el documento del período seleccionado — no cambia la lógica, solo qué documento se consulta.

## Compatibilidad con datos existentes

No aplica migración: los documentos existentes ya tienen `año`/`mes`. Ningún dato histórico cambia de forma; solo se habilita una nueva vía de lectura/escritura sobre períodos que antes eran inalcanzables desde la UI (aunque técnicamente ya existían en la base de datos, ej. vía "Historial").

## Testing

Sin suite automatizada (MVP, ver CLAUDE.md). Checklist de verificación manual para el plan de implementación:

- Con el selector sin tocar, generar/descargar cada uno de los 8 formatos como contratista y firmar/aprobar como supervisor → debe comportarse exactamente igual que hoy (regresión).
- Elegir un mes pasado en "Formatos de contrato" y generar un formato que nunca se había generado ese mes → se crea el documento correcto para `(usuario, año, mes)`, con el contrato vigente de esa época en el PDF.
- Elegir un mes pasado en "Sup. Formatos" y firmar corr/gd/secop → auto-certificación dispara correctamente para ese período, no afecta el período actual.
- Elegir un mes pasado y firmar un acta fuera de orden → sigue bloqueado igual que en el período actual; completar el orden correctamente → aprueba y genera hash.
- Revocar una firma de un acta en un mes pasado con firmas posteriores ya registradas → cascada y `eventos` se registran igual que en el flujo actual.
- Verificar que ningún selector lista meses futuros al `periodo_certificable()` actual.
- Usuario sin historial de contratos → selector del contratista muestra solo el período certificable actual (sin opciones adicionales).
- Verificar los 3 casos de la leyenda de período (actual, mes anterior automático, pasado manual) en ambas páginas.
