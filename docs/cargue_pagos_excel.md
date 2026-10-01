# Cargue masivo de pagos desde Excel

Funcionalidad para que un **administrador** cargue el Excel de tesorería ("Listado Op Vig") y agregue automáticamente los pagos que correspondan a contratistas registrados en la app a su **último contrato activo**, sin editarlos uno por uno a mano.

## Dónde está

- **En la app:** menú **Administración → Cargue de Pagos** (solo visible para usuarios con el permiso `pago.cargar`, que hoy solo tiene el rol `admin`).
- **Código:**
  - `app/pages_admin/admin_cargue_pagos.py` — la página.
  - `app/services/cargue_pagos_service.py` — toda la lógica (limpieza, clasificación, escritura).
  - `tests/test_cargue_pagos_service.py` — 33 pruebas automatizadas.
- **Documentación técnica completa** (diseño y plan de implementación, para quien necesite entrar al detalle):
  - `docs/superpowers/specs/2026-09-30-cargue-pagos-excel-design.md`
  - `docs/superpowers/plans/2026-09-30-cargue-pagos-excel.md`

## Cómo se usa

1. Entrar a **Administración → Cargue de Pagos**.
2. Subir el archivo `.xlsx` o `.xlsm` del listado de tesorería.
3. La app lo procesa **en memoria, sin escribir nada todavía** en la base de datos, y muestra un resumen por categoría (válidos, usuario no encontrado, sin contrato activo, duplicados, etc.) más una tabla editable con el detalle de cada registro.
4. En la tabla, los pagos clasificados como **Válido** vienen pre-marcados para cargar; se puede desmarcar cualquiera (por ejemplo, si el concepto del pago indica que es un viático y no un honorario del contrato).
5. Al pulsar **Confirmar carga**, aparece un diálogo de confirmación con el total de pagos y contratos afectados. Solo al confirmar ahí se escribe en la base de datos.
6. El resultado se muestra al terminar: cuántos pagos se cargaron y en qué contratos, y el detalle de cualquier contrato que haya fallado.

## Qué valida automáticamente

Cada fila del Excel se clasifica en una de estas categorías antes de poder cargarse:

| Categoría | Significado |
|---|---|
| ✅ Válido | Usuario encontrado, tiene contrato activo, datos completos — listo para cargar |
| ⚠️ Duplicado en el archivo | La misma fila (cédula + fecha + valor neto) aparece repetida en el Excel |
| ❌ Usuario no encontrado | La cédula no existe en la app (normal: el archivo trae pagos de todo INVIAS, no solo de esta subdirección) |
| ❌ Sin contrato activo | El usuario existe pero no tiene ningún contrato vigente |
| ❌ Dato inválido | Fecha o valores monetarios vacíos, no numéricos o negativos |
| ℹ️ Ya existe en BD | Ese pago ya estaba cargado en el contrato — se omite, no se duplica |
| ❌ Excede límite de 20 pagos | El contrato ya tiene (o quedaría con) más de 20 pagos — el esquema de Mongo no permite más; se rechaza el contrato completo, no una carga parcial |

## Qué NO hace (por diseño, a propósito)

- **Nunca modifica ni borra un pago que ya existe.** Solo agrega pagos nuevos.
- **Nunca carga automáticamente un pago con error.** Todo lo que no sea "Válido" queda excluido salvo que un administrador lo revise manualmente en otra pantalla.
- **No filtra automáticamente pagos que no son del contrato** (por ejemplo, viáticos de un contratista): se muestra el concepto del pago en la tabla para que el admin decida con criterio, en vez de adivinar con una regla automática.
- Al cargar, recalcula automáticamente el **Valor total pagado** y el **Valor total por pagar** del contrato (misma fórmula que ya usa el formato "Balance General CPS"), pero esos dos campos se pueden seguir editando a mano después, como hoy.

## Pendiente de verificar

Todo el desarrollo se hizo y se revisó (incluida una revisión final de toda la funcionalidad) con 33 pruebas automatizadas en verde, pero **ningún ambiente de desarrollo usado tuvo acceso real a la base de datos de Mongo** — así que falta una prueba manual real antes de usarlo con datos de producción:

1. Iniciar sesión como admin y confirmar que el menú **Cargue de Pagos** aparece (y que un usuario sin permiso de admin NO lo ve).
2. Subir un Excel de prueba pequeño (unas pocas filas) con al menos una cédula real de un contratista activo en la base de prueba.
3. Confirmar la carga y revisar en **Mi Perfil** o en el admin de usuarios que el pago quedó reflejado en el contrato, con los totales recalculados correctamente.
4. Volver a subir el mismo archivo: esa fila debe salir como "Ya existe en BD", no duplicarse.
5. Generar el formato **Balance General CPS** de ese contratista y confirmar que los valores del PDF coinciden con lo cargado.

Si todo eso sale bien, la funcionalidad queda lista para uso real.
