# Cargue masivo de pagos de contratos desde Excel de tesorería

## Contexto

Periódicamente llega un Excel de tesorería ("Listado Op Vig") con el total de órdenes de pago de todo INVIAS para una vigencia fiscal. El administrador necesita extraer de ahí únicamente los pagos que corresponden a contratistas registrados en esta app y agregarlos al plan de pagos de su **último contrato activo**, sin editar cada pago a mano desde "Mi Perfil"/admin de usuarios.

Se evaluó el impacto antes de diseñar (ver conversación previa). Hallazgos clave que condicionan este diseño:

- El array `contratos[].pagos[]` ya existe en el esquema (`app/core/esquemas.py:92-112`) con los campos `numero_pago`, `fecha_pago`, `valor_bruto_pago`, `deducciones_pago`, `valor_neto_pago`, y un **tope duro de 20 pagos por contrato** (`maxItems: 20`).
- No existe una colección `contratos` separada: los contratos viven embebidos en `usuarios.contratos[]`. El contrato se reemplaza completo vía `UsuarioRepositorio.editar_contrato_en_usuario` (`$set: {"contratos.$": nuevo_contrato}`, posicional por `contratos.numero`).
- `valor_total_pagado` y `valor_total_por_pagar_contrato` son hoy campos **editados a mano** en `app/core/ui_contratos.py` (number_input libre) — no se calculan de `pagos[]` en ningún lado. El único lugar que los **usa** es el generador del PDF "Balance General CPS" (`app/services/certificacion_service.py:3876-3879` y `:4679-4682`), con la fórmula `saldo_presp_lib_contrato_2 = abs(valor_total - valor_total_pagado)`. Este cargue será el primer punto del sistema que calcula `valor_total_pagado` automáticamente (suma de `valor_bruto_pago`), reusando esa misma fórmula para `valor_total_por_pagar_contrato`.
- El archivo real (`Listado Op Vig 2 sep.xlsx`) tiene 31,804 filas: es el listado de tesorería de todo el instituto (impuestos, servicios públicos, viáticos, honorarios, etc.), no un listado exclusivo de contratistas. La columna de identificación real es `Identificacion` (+ `Tipo Identificacion`), no la columna `Numero Documento` (que es el número del comprobante de pago y tiene 7,459 valores repetidos — no sirve como criterio de deduplicación).
- La selección de "último contrato activo" debe seguir la misma semántica que ya usa `CertificacionService._ultimo_contrato_usuario`: el vigente hoy (`not _contrato_finalizado`) o, si ninguno, el más reciente por `fecha_inicio`.

## Alcance

- Página nueva de administración para cargar un `.xlsx`/`.xlsm`, revisar una vista previa clasificada fila por fila, y confirmar la carga definitiva de los pagos seleccionados.
- Cargue **aditivo únicamente**: nunca se modifica ni se elimina un pago ya existente en BD; solo se agregan pagos nuevos que no colisionen con los existentes.
- Verificación previa y re-verificación al momento de escribir (cupo de 20, duplicados) para tolerar que el estado en BD cambie entre que se generó la vista previa y se confirma la carga.
- Cálculo automático de `valor_total_pagado` y `valor_total_por_pagar_contrato` tras el merge, con la misma fórmula que ya usa el Balance General CPS.
- Registro de auditoría del lote cargado.

## Fuera de alcance

- No se migran ni se tocan pagos cargados manualmente antes de este cambio.
- No se automatiza la detección de qué pagos son "honorarios del contrato" vs. otro concepto (viáticos, etc.) — esa decisión queda en la revisión visual del admin fila por fila en la vista previa (se muestra `Concepto Pago`/`Objeto del Compromiso` para apoyar ese juicio), no se intenta un filtro automático por palabras clave.
- No se cambia el comportamiento de los campos `valor_total_pagado`/`valor_total_por_pagar_contrato` como number_input editable en `ui_contratos.py` — el admin sigue pudiendo sobreescribirlos a mano después del cargue si lo necesita.
- No se soporta otra fila de encabezado distinta a la primera, ni múltiples hojas (el archivo de referencia tiene una sola hoja, "Hoja").

## Mapeo y limpieza del Excel

| Columna origen | Campo destino | Limpieza |
|---|---|---|
| `Tipo Identificacion` | — (filtro) | solo se procesan filas con valor `"Cédula de Ciudadanía"`; las de `"NIT"` se descartan sin generar fila de error (son pagos a municipios/empresas, esperados) |
| `Identificacion` | clave de búsqueda del usuario | strip, quitar separadores de miles/decimales (`.0` de lectura como float), validar que sea solo dígitos (reutiliza `UsuarioService._normalizar_numero_documento`) |
| `Numero Documento` | `numero_pago` | strip, forzar a string |
| `Fecha de pago` | `fecha_pago` | quitar componente de hora, normalizar a `datetime` a medianoche (mismo patrón que `UsuarioService._fecha_a_datetime`) |
| `Valor Bruto` | `valor_bruto_pago` | quitar comas/puntos de miles, a `int` |
| `Valor Deducciones` | `deducciones_pago` | ídem |
| `Valor Neto` | `valor_neto_pago` | ídem |
| `Concepto Pago`, `Objeto del Compromiso` | solo visual en la vista previa | sin limpieza, se muestran tal cual para apoyar la revisión manual |

El resto de las ~45 columnas del archivo se ignoran.

**Optimización de matching:** en vez de consultar Mongo fila por fila contra 31,804 registros, se obtiene primero el conjunto de `numero_documento` de usuarios con al menos un contrato (vía una única consulta `UsuarioRepositorio`), y se filtra el DataFrame contra ese conjunto en memoria antes de clasificar.

## Clasificación de registros (vista previa, sin tocar Mongo)

Por cada fila filtrada:

1. **Duplicado interno** — ya se vio una fila con la misma `(Identificacion, fecha_pago, valor_neto_pago)` en este archivo. Se conserva la primera, las siguientes quedan en esta categoría (criterio conservador: solo colapsa filas idénticas, nunca pagos distintos que comparten `Numero Documento`).
2. **Usuario no encontrado** — la cédula no existe en `usuarios`.
3. **Sin contrato activo** — el usuario existe pero ninguno de sus contratos pasa `not UsuarioService._contrato_finalizado(c)`.
4. **Dato inválido** — `fecha_pago` no parseable, o algún valor monetario no numérico tras la limpieza.
5. **Ya existe en BD** — el contrato activo del usuario ya tiene un pago con el mismo `(numero_pago, fecha_pago, valor_neto_pago)`. Es informativo, no error: se excluye de la selección por defecto para no duplicar.
6. **Excede límite de 20 pagos** — `len(pagos actuales del contrato) + pagos nuevos candidatos de ese mismo contrato (tras deduplicar) > 20`. Se marca **todo el contrato** (todas sus filas candidatas de este lote) en esta categoría, no una selección parcial.
7. **Válido** — pasa todas las anteriores. Preseleccionado en la tabla de revisión.

El resultado de `procesar_archivo` es una lista de filas con: cédula, nombre (si se encontró), número de contrato de destino, categoría, motivo legible, los 5 campos de pago ya limpios, y el texto de concepto/objeto para mostrar.

## Modelo de escritura segura

`CarguePagosService.confirmar_carga(filas_seleccionadas, usuario_que_carga)`:

1. Solo procesa filas que el admin dejó marcadas (checkbox) y que eran categoría "Válido" en la vista previa — cualquier otra categoría nunca llega a esta función aunque el request la incluya (defensa en el servicio, no solo en la UI).
2. Agrupa las filas seleccionadas por `(id_usuario, numero_contrato)`.
3. Por cada grupo, en un bucle con `try/except` individual (un fallo en un contrato no aborta los demás):
   - Vuelve a leer el usuario completo desde `UsuarioRepositorio.buscar_por_id` (estado fresco, no el de la vista previa).
   - Vuelve a verificar que el contrato siga activo y que el cupo de 20 siga sin excederse con el estado actual de `pagos[]`; si ya no cumple (cambió algo desde la vista previa), se omite ese contrato y se reporta como fallido con el motivo.
   - Vuelve a verificar colisión `(numero_pago, fecha_pago, valor_neto_pago)` contra el estado actual (por si alguien cargó algo manualmente en el ínterin); los que ya existen se omiten silenciosamente de ese grupo (no es error).
   - Construye el nuevo array `pagos` = pagos actuales + pagos nuevos no colisionados.
   - Recalcula `valor_total_pagado = sum(p["valor_bruto_pago"] for p in pagos_nuevo_array)` y `valor_total_por_pagar_contrato = abs(int(contrato.get("valor") or 0) - valor_total_pagado)` (misma fórmula que `certificacion_service.py`).
   - Llama a `UsuarioRepositorio.editar_contrato_en_usuario(id_usuario, numero_contrato, contrato_actualizado)` — el método ya existente, sin crear un método de repositorio nuevo. Solo se tocan los 3 campos mencionados; el resto del contrato se preserva tal cual se leyó.
4. Devuelve un resumen `{"ok": [...], "fallidos": [...]}` con detalle por contrato, para que la UI lo muestre tras confirmar.

No se usa `bulk_write` de PyMongo: el volumen esperado por lote (usuarios reales de la app que además coinciden con el Excel de tesorería) es pequeño, y un bucle con `try/except` por contrato ya da aislamiento de fallos sin la complejidad adicional de `arrayFilters`/bulk ops.

## Permisos y navegación

- Permiso nuevo en `app/core/catalogos.py`: `pago.cargar — "Cargar pagos masivos desde Excel"`, módulo `pagos`. Se agrega a `PERMISOS_BASE`; al no incluirse en `_PERMISOS_SOLO_FIRMANTES`, el rol `admin` lo recibe automáticamente (su lista de permisos se construye como "todo `PERMISOS_BASE` menos `_PERMISOS_SOLO_FIRMANTES`") y ningún otro rol existente (Financiera/Abogado/Jefe/etc.) lo obtiene salvo que se le asigne explícitamente.
- Página nueva `app/pages_admin/admin_cargue_pagos.py` + wrapper `app/pages/16_admin_cargue_pagos.py` (siguiente número libre en `app/pages/`), registrada en `main.py` bajo "Administración" junto a Usuarios/Roles/Parámetros, gateada por `"pago.cargar" in permisos_sesion`.

## UI — `app/pages_admin/admin_cargue_pagos.py`

1. `st.file_uploader` para `.xlsx`/`.xlsm`.
2. Al cargar el archivo, se invoca `CarguePagosService.procesar_archivo` (sin tocar Mongo) y se muestran métricas (`st.metric`) por categoría: válidos, usuario no encontrado, sin contrato activo, duplicados internos, ya existentes, excede cupo, dato inválido.
3. Tabla de detalle (`st.data_editor` con columna de checkbox) con una fila por registro: cédula, nombre, número de contrato, categoría, motivo, fecha de pago, valor bruto/deducciones/neto, concepto/objeto. Las filas "Válido" vienen pre-marcadas; el resto, sin checkbox habilitado (no se pueden seleccionar categorías de error).
4. Botón "Confirmar carga" → `@st.dialog` de confirmación mostrando cuántos pagos se van a insertar y a cuántos contratos distintos afecta (mismo patrón que `admin_parametros.py`).
5. Al confirmar, se llama `confirmar_carga` y se muestra el resumen de éxitos/fallidos devuelto, con `st.success`/`st.error` por contrato fallido y su motivo.

## Auditoría

Se reutiliza `AuditoriaService.registrar_accion` (ya usado en `usuario_service.py`) una vez por contrato actualizado: `accion="cargue_pagos_excel"`, `recurso=f"usuario:{id_usuario}:contrato:{numero_contrato}"`, `detalle={"archivo": nombre_archivo, "pagos_agregados": n, "cargado_por": usuario_que_carga}`.

## Testing

El proyecto está en etapa MVP sin suite automatizada (ver CLAUDE.md). Verificación manual sugerida en el plan de implementación:

- Cargar el Excel real de referencia y confirmar que las métricas de clasificación tienen sentido (la mayoría "usuario no encontrado", un número pequeño "válido").
- Un usuario con cédula que coincide pero sin contrato activo → cae en "sin contrato activo", no se ofrece para selección.
- Dos filas idénticas en el Excel → solo una queda como "válido", la otra como "duplicado interno".
- Cargar el mismo archivo dos veces seguidas → la segunda vez todo cae en "ya existe en BD", no se duplica nada.
- Contrato cuyos pagos nuevos + actuales superarían 20 → todas sus filas candidatas quedan en "excede límite de 20 pagos", no se cargan parcialmente.
- Desmarcar manualmente una fila "válida" en la tabla (p. ej. porque el concepto dice "viáticos") → no se carga ese pago aunque la cédula haya coincidido.
- Tras confirmar, abrir el contrato en "Mi Perfil"/admin de usuarios y verificar que `pagos[]`, `valor_total_pagado` y `valor_total_por_pagar_contrato` se ven correctos, y que el PDF "Balance General CPS" generado después refleja esos mismos valores.
- Verificar que el permiso `pago.cargar` controla el acceso a la página (un rol sin ese permiso no la ve en el menú ni puede acceder directo por URL).
