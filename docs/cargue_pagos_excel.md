# Cargue masivo de pagos desde Excel

Funcionalidad para cargar el Excel de tesorería ("Listado Op Vig") y registrar automáticamente los pagos de los contratistas de la app en **el contrato que el propio Excel indica**, sin editarlos uno por uno a mano.

## Dónde está

- **En la app:** menú **Config Formatos → botón "3- Balance General CPS" → sección "💰 Cargue de pagos desde Excel de tesorería"**. La sección solo aparece para usuarios con el permiso `pago.cargar` (hoy solo el rol `admin`), además del permiso `certificacion.aprobar` que ya exige Config Formatos.
- **Código:**
  - `app/pages_admin/admin_cargue_pagos.py` — la sección (`render_seccion`), que `app/pages_admin/admin_certificaciones.py` muestra dentro del formato 3.
  - `app/services/cargue_pagos_service.py` — toda la lógica (limpieza, clasificación, escritura).
  - `tests/test_cargue_pagos_service.py` — pruebas automatizadas.
- **Diseño y plan originales** (históricos: describen la primera versión, que era solo aditiva, cargaba al contrato activo y vivía en el menú Administración):
  - `docs/superpowers/specs/2026-09-30-cargue-pagos-excel-design.md`
  - `docs/superpowers/plans/2026-09-30-cargue-pagos-excel.md`

## Cómo se usa

1. Entrar a **Config Formatos**, pulsar **3- Balance General CPS** y abrir la sección **Cargue de pagos desde Excel de tesorería**.
2. Subir el archivo `.xlsx` o `.xlsm` del listado de tesorería.
3. La app lo procesa **en memoria, sin escribir nada todavía** en la base de datos, y muestra un contador por categoría más una tabla con los pagos que se pueden cargar.
4. En la tabla, los pagos **Nuevo** y **Sobrescribe existente** vienen pre-marcados; se puede desmarcar cualquiera (por ejemplo, si el concepto indica que es un viático o si el estado del comprobante es "Anulada"). Los demás registros se ven con el interruptor "Ver registros con error o informativos".
5. Al pulsar **Confirmar carga**, aparece un diálogo con cuántos pagos se agregan, cuántos se sobrescriben y cuántos contratos se afectan. Solo al confirmar ahí se escribe en la base de datos.
6. El resultado se muestra al terminar: pagos agregados, pagos sobrescritos y el detalle de cualquier contrato que haya fallado.

## Cómo se ubica el contrato

El pago se asigna cruzando dos datos de la fila:

- **`Identificacion`** (con `Tipo Identificacion` = "Cédula de Ciudadanía") → el usuario.
- **`Num Doc Soporte Compromiso`** (columna AW) → el contrato, en la forma `número/año` (ej. `2570/2026`). También se aceptan `número-año`, ceros a la izquierda (`0805/2026`), prefijos (`SA 0699/2026`) y un año con dígitos de más (`2289/20255`).

El número se compara con el número de contrato registrado en la app y el año con el de sus fechas (firma SECOP, fecha de inicio u orden de inicio). **El estado del contrato es indiferente:** vigente, finalizado o en período de gracia, los pagos se cargan igual. Si el usuario no tiene registrado ese contrato, la fila queda como "Contrato no encontrado" y no se carga en ningún otro.

## Qué identifica un pago

Un pago es un **comprobante de tesorería** (`Numero Documento`, guardado como `numero_pago`) dentro de un contrato:

- Si el comprobante **no está** en el contrato → pago **nuevo**.
- Si **ya está** y algún dato cambió (fecha, valor bruto, deducciones o neto) → se **sobrescribe** con lo que trae el Excel.
- Si ya está y todo es igual → **sin cambios**, no se toca.
- Si el mismo comprobante se repite en el archivo para el mismo contrato (el listado trae una fila por cada línea presupuestal) → solo cuenta la primera, las demás son **duplicado en el archivo**.

Dos comprobantes distintos con la misma fecha y el mismo valor **no** son duplicados: son pagos diferentes.

## Categorías

| Categoría | Significado | ¿Se puede cargar? |
|---|---|---|
| ✅ Nuevo | El comprobante no existe en el contrato | Sí |
| 🔄 Sobrescribe existente | El comprobante ya existe con datos distintos | Sí |
| ℹ️ Sin cambios | El comprobante ya existe con los mismos datos | No hace falta |
| ⚠️ Duplicado en el archivo | Comprobante repetido en el Excel para el mismo contrato | No |
| ❌ Usuario no encontrado | La cédula no existe en la app (normal: el archivo trae pagos de todo INVIAS) | No |
| ❌ Contrato no encontrado | El usuario no tiene el contrato `número/año` del Excel, o la celda no trae ese formato | No |
| ❌ Dato inválido | Cédula, comprobante, fecha o valores vacíos, no numéricos o negativos | No |
| ❌ Excede límite de 20 pagos | El contrato quedaría con más de 20 pagos (tope del esquema de Mongo); no se agrega ningún pago nuevo de ese contrato, pero sí se pueden sobrescribir los existentes | No |

Las filas cuyo tipo de identificación no es "Cédula de Ciudadanía" (NIT, etc.) se ignoran sin aparecer en ninguna categoría.

## Orden de los pagos

La columna **`Fecha de pago`** define el orden. Al confirmar, todos los pagos del contrato (los que ya estaban y los cargados) quedan ordenados por fecha de pago ascendente; los del mismo día conservan el orden de su hora de pago. La fecha se guarda sin hora.

## Qué más hace al cargar

- Recalcula el **Valor total pagado** (suma de los valores brutos de todos los pagos) y el **Valor total por pagar** (Valor total de contrato menos Valor total pagado). Es la misma fórmula (`app/core/balance_contrato.py`) que se aplica al guardar un contrato a mano y al generar el formato "Balance General CPS"; esos dos campos ya no se digitan, en pantalla son de solo lectura.
- Registra en auditoría la acción `cargue_pagos_excel` por contrato, con el archivo y cuántos pagos se agregaron y sobrescribieron.
- Vuelve a leer el contrato justo antes de escribir, así que si alguien lo cambió entre la vista previa y la confirmación se respeta el estado real.
- Si un contrato falla, se reporta y los demás se cargan igual.

## Qué NO hace

- **Nunca elimina un pago.** Un pago digitado a mano con un número distinto al comprobante de tesorería se conserva tal cual, al lado de los cargados.
- **Nunca carga automáticamente una fila con error.**
- **No filtra por concepto ni por estado del comprobante:** la tabla muestra el concepto y el estado ("Pagada", "Autorizada", "Anulada"…) para que quien carga decida.
- **No consolida comprobantes:** un contrato pagado con varios comprobantes por mes (uno por rubro) puede superar los 20 pagos y quedar en "Excede límite".

## Pendiente de verificar

La lógica está cubierta por pruebas automatizadas y se probó con el Excel real de tesorería contra usuarios simulados, pero **falta una prueba manual contra la base de datos real** antes de usarlo en producción:

1. Entrar como admin a **Config Formatos → 3- Balance General CPS** y confirmar que aparece la sección (y que un usuario sin `pago.cargar` no la ve).
2. Subir el Excel y revisar que los contratistas esperados salen como "Nuevo" en el contrato correcto.
3. Confirmar la carga y revisar en **Mi Perfil** o en el admin de usuarios que los pagos quedaron en orden de fecha y con los totales recalculados.
4. Volver a subir el mismo archivo: todo debe salir como "Sin cambios".
5. Cambiar a mano el valor de un pago cargado, volver a subir el archivo y confirmar que sale como "Sobrescribe existente" y recupera el valor del Excel.
6. Generar el formato **Balance General CPS** de ese contratista y confirmar que los valores del PDF coinciden con lo cargado.
