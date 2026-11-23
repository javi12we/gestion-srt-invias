# Tooltips de «Mi perfil»

Inventario de todos los tooltips (iconos ⓘ y `help=` de Streamlit) de la página **Mi perfil** (`app/pages/2_mi_perfil.py`), organizados por pestaña.

**Tipos de tooltip**

- **ⓘ (HTML):** tooltip personalizado con las clases `srti-tooltip-*` (aparece al pasar el cursor o enfocar el icono).
- **help (Streamlit):** el icono `?` nativo de `st.checkbox` / `st.button` con `help=`.

**Archivos de origen**

| Abreviatura | Archivo |
|---|---|
| `perfil` | `app/pages/2_mi_perfil.py` |
| `laboral` | `app/core/ui_laboral.py` |
| `contratos` | `app/core/ui_contratos.py` |

---

## 1. 👤 Perfil

Esta pestaña **no tiene tooltips**. (Solo muestra subtítulos, un `st.caption` y mensajes de validación.)

---

## 2. 💼 Información laboral

Origen: `laboral` (función `inputs_informacion_laboral` y `_inputs_dependientes`).

| # | Campo / sección | Tipo | Título del tooltip | Texto | Origen |
|---|---|---|---|---|---|
| 1 | Grupo de trabajo | ⓘ | GRUPOS DE TRABAJO | Los grupos de trabajo los asigna el administrador o el líder del grupo desde Administración › Grupos de trabajo. Aquí solo se muestran. | `laboral:270` |
| 2 | 🏥 Seguridad social y aportes › Planilla a mes vencido | help | — | Marca esta opción si pagas la planilla a mes vencido. | `laboral:301` |
| 3 | 🏥 Seguridad social y aportes › Ingreso Base de Cotización - Prestaciones sociales (opcional) | ⓘ | GUÍA RÁPIDA: CÁLCULO DEL IBC | Ver detalle abajo. | `laboral:307` |
| 4 | 🧾 Información tributaria › Tipo de régimen | ⓘ | TIPOS DE RÉGIMEN | Ver detalle abajo. | `laboral:406` |
| 5 | 🧾 Información tributaria › ¿Paga IVA? | help | — | Marca esta opción si estás obligado/a a facturar y cobrar IVA en tus contratos. | `laboral:480` |
| 6 | 🧾 Información tributaria › ¿Eres pensionado/a? | help | — | Si estás pensionado/a, los campos de AFP y Caja de Compensación Familiar no aplican y no serán requeridos para descargar los formatos. | `laboral:486` |
| 7 | 👨‍👩‍👧 Dependientes económicos › botón 🗑️ | help | — | Eliminar este dependiente | `laboral:566` |
| 8 | 👨‍👩‍👧 Dependientes económicos › Tipo de dependiente | ⓘ | TIPOS DE DEPENDIENTES | Ver detalle abajo. | `laboral:581` |

### 2.3 GUÍA RÁPIDA: CÁLCULO DEL IBC

El **Ingreso Base de Cotización (IBC)** para contratistas independientes en Colombia se calcula con la regla del **40%** del valor mensualizado del contrato (sin incluir IVA).

1. **Mensualiza el contrato** — Divide el valor total del contrato por el número de meses de ejecución.
   Fórmula: `Valor total ÷ Meses de duración = Ingreso Mensual`
   *Ejemplo: Contrato de $30.000.000 a 6 meses = $5.000.000 mensuales.*
2. **Aplica el 40%** — El IBC mínimo legal sobre el cual debes cotizar es el 40% de ese valor mensual.
   Fórmula: `Ingreso Mensual × 40% = IBC`
   *Ejemplo: $5.000.000 × 40% = $2.000.000 (Este es tu IBC).*
3. **Verifica los topes legales**
   - **Piso mínimo:** No puede ser menor a 1 Salario Mínimo Mensual Legal Vigente (SMMLV). Si el 40% es menor, cotizas sobre 1 SMMLV.
   - **Techo máximo:** No puede superar los 25 SMMLV.
4. **Calcula tus aportes de ley (sobre el IBC)**
   - **Salud (12.5%):** IBC × 12.5% (Ej: $2.000.000 × 12.5% = $250.000)
   - **Pensión (16%):** IBC × 16% (Ej: $2.000.000 × 16% = $320.000)
   - **ARL (Varía según riesgo):** Lo paga el contratista, excepto si es nivel de riesgo IV o V, que lo asume el contratante.

### 2.4 TIPOS DE RÉGIMEN

- **No responsables de IVA** — Personas naturales que no cumplen con los topes de ingresos o condiciones de ley para ser responsables de declarar/cobrar IVA (anteriormente régimen simplificado).
- **Responsables de IVA** — Personas jurídicas o naturales que superan los topes legales de ingresos o requisitos y por tanto deben facturar, recaudar y declarar el IVA (anteriormente régimen común).
- **Régimen Simple de Tributación (RST)** — Sistema de tributación opcional que unifica varios impuestos (renta, ICA, IVA si aplica) para facilitar y simplificar el cumplimiento tributario.
- **Régimen Tributario Especial (RTE)** — Aplica a entidades sin ánimo de lucro (fundaciones, asociaciones, corporaciones) que cumplen requisitos de ley y tienen un tratamiento tributario preferencial.

### 2.8 TIPOS DE DEPENDIENTES

- **A.** Hijo(s) que tiene(n) hasta 18 años de edad y depende(n) económicamente del declarante.
- **B.** Hijo(s) entre 18 y 23 años, cuya educación está a cargo del declarante en instituciones formales de educación superior certificadas por el ICFES o la autoridad competente, o en programas técnicos de educación no formal debidamente acreditados.
- **C.** Hijo(s) mayores de 23 años que se encuentren en situación de dependencia por condiciones físicas o psicológicas certificadas por Medicina Legal.
- **D.** Cónyuge o compañero(a) permanente en situación de dependencia por ausencia de ingresos o ingresos anuales inferiores a 260 UVT, certificados por contador público, o por dependencia originada por factores físicos o psicológicos certificados por Medicina Legal.
- **E.** Padres y/o hermanos en situación de dependencia por ausencia de ingresos o ingresos anuales inferiores a 260 UVT, certificados por contador público, o por dependencia originada por factores físicos o psicológicos certificados por Medicina Legal.

---

## 3. ✍️ Firma

Esta pestaña **no tiene tooltips**. Solo muestra un `st.caption` introductorio y avisos (vista previa / «aún no está guardada»), definidos en `laboral:render_seccion_firma`.

---

## 4. 📄 Contratos

Esta pestaña tiene dos bloques: el formulario **➕ Agregar nuevo contrato** y, por cada contrato existente, el formulario de **edición** (con el mismo conjunto de campos, más el balance y consolidado de pagos).

### 4.1 Campos del contrato (formulario «Agregar» y formulario de edición)

Origen: `perfil` (nuevo contrato: líneas 223-425; edición: líneas 512-729). Los textos son idénticos en ambos formularios; solo cambia la etiqueta visible en algunos casos.

| Campo | Etiqueta (Agregar) | Etiqueta (Editar) | Título del tooltip | Texto |
|---|---|---|---|---|
| Número | Numero del contrato * | Numero del contrato | Numero del contrato | Este es el numero de serie del contrato, sin adjetivos ni fechas. |
| Valor total | Valor del contrato (COP) | Valor total de contrato (COP) | Valor del contrato (COP) en «Agregar» / Valor total de contrato (COP) en «Editar» | Es el valor total del contrato sin adiciones ni disminuciones. |
| Valor primer pago | Valor primer pago | Valor primer pago | Valor primer pago | Este valor figurará en sus formatos de primera cuenta. |
| Personalizar última cuenta | Personalizar valor última cuenta | Personalizar valor última cuenta | Personalizar valor última cuenta | Active esta función solo si desea personalizar el valor de su última cuenta del contrato, de lo contrario no lo use. |
| RP | RP / compromiso presupuestal | RP / compromiso presupuestal | RP / compromiso presupuestal | Este dato se puede encontrar dentro del cargue de datos financiero en SECOP II. |
| Fecha RP | Fecha recurso presupuestal | Fecha recurso presupuestal | Fecha recurso presupuestal | Este dato se puede encontrar dentro del cargue de datos financiero en SECOP II. |
| Firma SECOP | Fecha de firma del contrato SECOP | Fecha de firma del contrato SECOP | Fecha de firma del contrato SECOP | Fecha en que se firmó el contrato en la plataforma SECOP. |
| Fecha inicio | Fecha de inicio contrato | Fecha de inicio contrato | Fecha de inicio contrato | El dato se puede encontrar en la cláusula del contrato, estudios previos o en la información general del contrato página de firma. |
| Fecha fin | Fecha de fin de contrato | Fecha de fin de contrato | Fecha de fin de contrato | El dato se puede encontrar en la cláusula del contrato, estudios previos o en la información general del contrato página de firma. |
| Objeto | Objeto del contrato | Objeto | Objeto del contrato | Objeto del contrato identificable en la cláusula del contrato y deberá escribirlo en mayúscula sostenida. |
| Radicado / orden de inicio | Radicado/ Fecha de orden de inicio Contrato | Radicado/ Fecha de orden de inicio Contrato | Radicado/ Fecha de orden de inicio Contrato | Radicado y/o fecha de la orden de inicio del contrato (campo de texto abierto), encontrable en las cláusulas, estudios previos o repositorios del contrato, y necesario para el Acta de entrega. |

> Los campos **Tipo de contrato** y **Valor mensual (COP)** no tienen tooltip.

### 4.2 Balance general y consolidado de pagos (solo en contratos existentes)

Origen: `contratos` (función `render_balance_y_pagos`).

| # | Sección / campo | Título del tooltip | Texto | Origen |
|---|---|---|---|---|
| 1 | ⚖️ Balance general y consolidado de pagos | ⚖️ Balance general y consolidado de pagos | Este balance de pagos se realizará antes de finalizar el contrato.<br>Se debe ingresar cada uno de los valores presupuestales del contrato que se encontrarán dentro del repositorio de balances antes de finalizar el contrato. | `contratos:307` |
| 2 | 📦 Inventario del Contrato | 📦 Inventario del Contrato | Esta opción debe marcarse únicamente si al contratista se le asignaron bienes de propiedad de la institución durante la vigencia del contrato.<br>**Ejemplo:** Equipos de cómputo (computador portátil/escritorio), periféricos, herramientas de hardware u otros activos institucionales devueltos o por devolver. | `contratos:327` |
| 3 | 💵 Balance Financiero | 💵 Balance Financiero | El contratista deberá registrar el balance financiero de su contrato para poder generar el documento de balance financiero al finalizar el contrato. | `contratos:365` |
| 4 | Valor Total por Pagar del contrato (COP) | Valor total por pagar | Se calcula automáticamente: Valor total de contrato menos Valor total pagado del contrato. | `contratos:610` |
| 5 | Valor total pagado del contrato (COP) | Valor total pagado del contrato | Se calcula automáticamente: suma de los valores brutos de todos los pagos del consolidado. | `contratos:617` |
| 6 | ⏳ Prórroga del contrato | ⏳ Prórroga del contrato | Es la extensión del plazo de vigencia de un contrato.<br>Se debe indicar si tiene una prórroga y, en caso afirmativo, describirla ingresando el radicado o memorando que la valida junto con su fecha de vencimiento. | `contratos:407` |
| 7 | ➕ Adiciones del contrato | Adiciones | Dinero incluido al contrato por cualquier otro medio extra al contrato que incremente la suma total del contrato. | `contratos:460` |
| 8 | 💳 Consolidado de Pagos | 💳 Consolidado de Pagos | Ver detalle abajo. | `contratos:496` |

#### 4.2.8 💳 Consolidado de Pagos

El consolidado de pagos se encuentra en el balance enviado previamente al contratista, ya sea por correo electrónico o URL, en el cual deberá copiar y pegar o diligenciar los datos correspondientes a este balance.

**Detalles de los campos:**

- **Número de pago:** Es el número interno del pago que emite Gestión Financiera.
- **Fecha de pago:** Es la fecha de realización del pago, se encuentra en la base de datos entregada.
- **Deducciones:** Las deducciones son descuentos o reducciones aplicadas al contrato. Deberá colocar lo que indica el balance enviado para ese pago.
- **Valor neto:** Será el valor del pago correspondiente a ese mes, este valor deberá ser exacto según la información enviada al contratista.

---

## 5. 🔒 Contraseña

Esta pestaña **no tiene tooltips**.

---

## Resumen

| Pestaña | Cantidad de tooltips |
|---|---|
| 👤 Perfil | 0 |
| 💼 Información laboral | 8 (4 ⓘ + 4 help; uno de estos es el botón eliminar dependiente) |
| ✍️ Firma | 0 |
| 📄 Contratos | 11 en el formulario de contrato (se repiten en «Agregar» y en cada contrato existente) + 8 del balance y pagos |
| 🔒 Contraseña | 0 |

## Observaciones

- En el formulario **Agregar nuevo contrato**, el título del tooltip de **Valor total** es «Valor del contrato (COP)»; en el de **edición** es «Valor total de contrato (COP)». Es la única diferencia de texto entre ambos formularios, aparte de las etiquetas.
- En el tooltip de **Objeto**, la etiqueta en edición es «Objeto» pero el título del tooltip es «Objeto del contrato».
- Los textos están duplicados en el código (formulario nuevo vs. edición en `2_mi_perfil.py`); si deseas cambiar un texto hay que editarlo en ambos lugares.
- Los tooltips ⓘ de `laboral` y `contratos` comparten las mismas clases CSS `srti-tooltip-*`, definidas en cada archivo (`laboral:105-260`, `contratos:144-270`).
