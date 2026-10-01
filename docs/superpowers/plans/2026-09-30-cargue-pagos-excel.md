# Cargue masivo de pagos de contratos desde Excel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar al admin una página para cargar un Excel de tesorería, revisar una clasificación fila por fila (válido / error / ya existente), y confirmar la carga de solo los pagos seleccionados al plan de pagos del último contrato activo de cada usuario, sin tocar Mongo hasta la confirmación explícita.

**Architecture:** Capa `app/services/cargue_pagos_service.py` nueva con funciones puras de limpieza + una clase `CarguePagosService` con dos métodos: `procesar_archivo` (solo lectura, clasifica en memoria) y `confirmar_carga` (único punto de escritura, re-verifica todo contra el estado actual de Mongo antes de escribir). Reutiliza `UsuarioRepositorio.editar_contrato_en_usuario` (ya existe, reemplazo posicional del subdocumento de contrato) y `CertificacionService._contrato_vigente` (classmethod puro, sin instanciar el servicio) para no duplicar la noción de "contrato activo". Página nueva en `app/pages_admin/` + wrapper en `app/pages/`, gateada por un permiso nuevo exclusivo de admin.

**Tech Stack:** Python 3.10, pandas + openpyxl (lectura de Excel), PyMongo (vía repositorio existente), Streamlit, pytest (nuevo en este proyecto).

**Spec:** `docs/superpowers/specs/2026-09-30-cargue-pagos-excel-design.md`

## Global Constraints

- Nunca se escribe en Mongo durante `procesar_archivo` — toda esa función es de solo lectura (consulta `UsuarioRepositorio.listar()`), según el spec.
- Tope duro de 20 pagos por contrato (`maxItems` del esquema): un contrato que lo excedería tras el merge se rechaza completo, nunca parcial.
- Deduplicación interna del Excel: clave `(cedula, fecha_pago, valor_neto_pago)` — nunca `Numero Documento` solo (tiene 7,459 duplicados legítimos en el archivo real).
- Colisión contra pagos ya existentes en BD: clave `(numero_pago, fecha_pago, valor_neto_pago)` dentro del mismo contrato.
- Solo se escriben los 3 campos `pagos`, `valor_total_pagado`, `valor_total_por_pagar_contrato` del contrato — el resto del subdocumento se preserva tal cual se leyó.
- `valor_total_pagado = sum(valor_bruto_pago)`; `valor_total_por_pagar_contrato = abs(valor_contrato - valor_total_pagado)` — misma fórmula que ya usa `certificacion_service.py` para el Balance General CPS.
- Permiso nuevo `pago.cargar`, exclusivo de admin (no se agrega a `_PERMISOS_SOLO_FIRMANTES`, así que el rol `admin` lo recibe automáticamente y ningún otro rol).
- Solo se procesan filas Excel con `Tipo Identificacion == "Cédula de Ciudadanía"`; las de `"NIT"` se ignoran sin generar fila de error.

## Review Focus

- Celda vacía/NaN real (no el texto `"nan"`) en `Fecha de pago` o en los valores monetarios → debe clasificar la fila como dato inválido, nunca lanzar una excepción no controlada que tumbe la página.
- `Valor Neto` o `Valor Bruto` negativo (nota crédito/reintegro en el listado de tesorería) → debe clasificarse como dato inválido en vez de cargarse silenciosamente como un pago normal.
- Excel sin alguna columna requerida (plantilla distinta a la esperada) → `procesar_archivo` debe fallar con un mensaje claro y manejable por la página, no un `KeyError` crudo.
- Confirmar la carga dos veces con la misma selección (doble clic, o re-subir el mismo archivo después) → la segunda vez no debe duplicar pagos ni alterar los totales ya calculados.
- Un lote con dos contratos distintos donde uno falla (p. ej. dejó de estar activo entre la vista previa y la confirmación) y el otro es válido → el válido se carga igual; el fallido se reporta sin abortar el lote completo.

---

## Task 1: Dependencias, pytest y permiso nuevo

**Files:**
- Modify: `requirements.txt`
- Create: `pytest.ini`
- Modify: `app/core/catalogos.py`
- Test: `tests/test_catalogos_pago_cargar.py`

**Interfaces:**
- Produces: permiso `"pago.cargar"` disponible en `PERMISOS_BASE` (lista de dicts `{"clave", "descripcion", "modulo"}` en `app/core/catalogos.py`).

- [ ] **Step 1: Agregar `pytest` y `openpyxl` a `requirements.txt`**

Edita `requirements.txt` y agrega estas dos líneas (openpyxl es necesario para leer `.xlsx`/`.xlsm` con pandas; hoy solo llega al proyecto como dependencia transitiva, no está declarado):

```
openpyxl>=3.1,<4
pytest>=8,<9
```

- [ ] **Step 2: Instalar las dependencias nuevas**

Run: `pip install -r requirements.txt`
Expected: instala `pytest` y `openpyxl` sin errores.

- [ ] **Step 3: Crear `pytest.ini` en la raíz del repo**

```ini
[pytest]
pythonpath = .
testpaths = tests
```

- [ ] **Step 4: Escribir el test que falla**

Crea `tests/test_catalogos_pago_cargar.py`:

```python
from app.core.catalogos import PERMISOS_BASE, ROLES_BASE


def test_permiso_pago_cargar_existe():
    claves = {p["clave"] for p in PERMISOS_BASE}
    assert "pago.cargar" in claves


def test_solo_admin_tiene_pago_cargar_por_defecto():
    admin = next(r for r in ROLES_BASE if r["nombre"] == "admin")
    assert "pago.cargar" in admin["permisos"]

    otros_roles = [r for r in ROLES_BASE if r["nombre"] != "admin"]
    for rol in otros_roles:
        assert "pago.cargar" not in rol["permisos"], f"El rol {rol['nombre']} no debería tener pago.cargar por defecto"
```

- [ ] **Step 5: Correr el test y verificar que falla**

Run: `pytest tests/test_catalogos_pago_cargar.py -v`
Expected: FAIL — `"pago.cargar" in claves` es `False`.

- [ ] **Step 6: Agregar el permiso a `PERMISOS_BASE`**

En `app/core/catalogos.py`, dentro de la lista `PERMISOS_BASE` (junto a las entradas de `"correspondencia.*"`), agrega:

```python
    {"clave": "pago.cargar", "descripcion": "Cargar pagos masivos desde Excel", "modulo": "pagos"},
```

No se toca `_PERMISOS_SOLO_FIRMANTES` ni `ROLES_BASE`: el rol `admin` ya construye su lista de permisos como "todo `PERMISOS_BASE` menos `_PERMISOS_SOLO_FIRMANTES`", así que lo recibe automáticamente.

- [ ] **Step 7: Correr el test y verificar que pasa**

Run: `pytest tests/test_catalogos_pago_cargar.py -v`
Expected: PASS (2 tests).

- [ ] **Step 8: Commit**

```bash
git add requirements.txt pytest.ini app/core/catalogos.py tests/test_catalogos_pago_cargar.py
git commit -m "feat: agregar permiso pago.cargar y configurar pytest"
```

---

## Task 2: Funciones de limpieza del Excel

**Files:**
- Create: `app/services/cargue_pagos_service.py`
- Test: `tests/test_cargue_pagos_service.py`

**Interfaces:**
- Consumes: `UsuarioService._normalizar_numero_documento(numero: str) -> str` (`app/services/usuario_service.py`, lanza `ValueError` si no es puramente numérico); `UsuarioService._fecha_a_datetime(d) -> datetime | None` (acepta `date` o `datetime`, retorna `datetime` con `tzinfo=UTC` a medianoche).
- Produces: `limpiar_cedula(crudo) -> str | None`, `limpiar_numero_pago(crudo) -> str | None`, `limpiar_valor_monetario(crudo) -> int | None`, `limpiar_fecha_pago(crudo) -> datetime | None` — todas en `app/services/cargue_pagos_service.py`, usadas por la Task 3.

- [ ] **Step 1: Escribir los tests que fallan**

Crea `tests/test_cargue_pagos_service.py`:

```python
from datetime import datetime, timezone

from app.services.cargue_pagos_service import (
    limpiar_cedula,
    limpiar_numero_pago,
    limpiar_valor_monetario,
    limpiar_fecha_pago,
)


def test_limpiar_cedula_entero():
    assert limpiar_cedula(79334686) == "79334686"


def test_limpiar_cedula_con_decimal_de_lectura_float():
    assert limpiar_cedula("79334686.0") == "79334686"


def test_limpiar_cedula_con_puntos_y_espacios():
    assert limpiar_cedula(" 79.334.686 ") == "79334686"


def test_limpiar_cedula_invalida_retorna_none():
    assert limpiar_cedula("ABC123") is None
    assert limpiar_cedula(None) is None
    assert limpiar_cedula("") is None


def test_limpiar_numero_pago_entero_a_string():
    assert limpiar_numero_pago(100185826) == "100185826"


def test_limpiar_numero_pago_vacio_es_none():
    assert limpiar_numero_pago(None) is None
    assert limpiar_numero_pago("   ") is None


def test_limpiar_valor_monetario_con_comas_y_decimales():
    assert limpiar_valor_monetario("26,026,880.00") == 26026880


def test_limpiar_valor_monetario_cero():
    assert limpiar_valor_monetario("0.00") == 0


def test_limpiar_valor_monetario_invalido_es_none():
    assert limpiar_valor_monetario("no es un numero") is None
    assert limpiar_valor_monetario(None) is None
    assert limpiar_valor_monetario(float("nan")) is None


def test_limpiar_fecha_pago_con_hora():
    resultado = limpiar_fecha_pago("2026-03-31 03:41:42")
    assert resultado == datetime(2026, 3, 31, tzinfo=timezone.utc)


def test_limpiar_fecha_pago_invalida_es_none():
    assert limpiar_fecha_pago("fecha invalida") is None
    assert limpiar_fecha_pago(None) is None
    assert limpiar_fecha_pago("") is None
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_cargue_pagos_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.cargue_pagos_service'`.

- [ ] **Step 3: Crear el archivo con las funciones de limpieza**

Crea `app/services/cargue_pagos_service.py`:

```python
"""Cargue masivo de pagos de contratos desde el Excel de tesorería (balances de pago).

Ver docs/superpowers/specs/2026-09-30-cargue-pagos-excel-design.md para el diseño completo.
"""

import math
from datetime import datetime

from app.services.usuario_service import UsuarioService

MAX_PAGOS_POR_CONTRATO = 20

TIPO_IDENTIFICACION_CEDULA = "Cédula de Ciudadanía"

COLUMNAS_REQUERIDAS = [
    "Tipo Identificacion",
    "Identificacion",
    "Numero Documento",
    "Fecha de pago",
    "Valor Bruto",
    "Valor Deducciones",
    "Valor Neto",
]


def limpiar_cedula(crudo) -> str | None:
    """Normaliza una cédula leída del Excel a solo dígitos, sin puntos/espacios
    ni el '.0' que deja pandas al leer una columna numérica con nulos."""
    if crudo is None:
        return None
    texto = str(crudo).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    texto = texto.replace(".", "").replace(",", "").replace(" ", "")
    if not texto:
        return None
    try:
        return UsuarioService._normalizar_numero_documento(texto)
    except ValueError:
        return None


def limpiar_numero_pago(crudo) -> str | None:
    """El 'Numero Documento' del Excel (identificador del comprobante de pago,
    no la cédula) se guarda tal cual como numero_pago, solo como string limpio."""
    if crudo is None:
        return None
    texto = str(crudo).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto or None


def limpiar_valor_monetario(crudo) -> int | None:
    """Limpia 'Valor Bruto'/'Valor Deducciones'/'Valor Neto': texto con comas de
    miles y dos decimales (ej. '26,026,880.00') a un entero en pesos."""
    if crudo is None:
        return None
    if isinstance(crudo, float) and math.isnan(crudo):
        return None
    texto = str(crudo).strip().replace(",", "")
    if texto == "" or texto.lower() == "nan":
        return None
    try:
        return round(float(texto))
    except ValueError:
        return None


def limpiar_fecha_pago(crudo) -> datetime | None:
    """'Fecha de pago' llega como texto con hora (ej. '2026-03-31 03:41:42');
    se descarta la hora y se normaliza a medianoche UTC con el mismo helper
    que usa el resto de fechas de contrato."""
    if crudo is None:
        return None
    texto = str(crudo).strip()
    if not texto:
        return None
    try:
        fecha = datetime.strptime(texto[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return UsuarioService._fecha_a_datetime(fecha)
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_cargue_pagos_service.py -v`
Expected: PASS (12 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/cargue_pagos_service.py tests/test_cargue_pagos_service.py
git commit -m "feat: funciones de limpieza para el cargue de pagos desde Excel"
```

---

## Task 3: Clasificación de filas — `CarguePagosService.procesar_archivo`

**Files:**
- Modify: `app/services/cargue_pagos_service.py`
- Test: `tests/test_cargue_pagos_service.py`

**Interfaces:**
- Consumes: `UsuarioRepositorio.listar() -> list[dict]` (`app/repositories/usuario_repo.py`, ya existe, retorna usuarios sin `password_hash`); `UsuarioService._contrato_finalizado(contrato, dias_gracia=0) -> bool`; `CertificacionService._contrato_vigente(contratos: list) -> dict` (classmethod, `app/services/certificacion_service.py`, no requiere instanciar el servicio).
- Produces: constantes de categoría (`CAT_VALIDO`, `CAT_DUPLICADO_INTERNO`, `CAT_USUARIO_NO_ENCONTRADO`, `CAT_SIN_CONTRATO_ACTIVO`, `CAT_DATO_INVALIDO`, `CAT_YA_EXISTE`, `CAT_EXCEDE_LIMITE`); `CarguePagosService.__init__(self, repositorio=None)`; `CarguePagosService.procesar_archivo(self, archivo) -> dict` con forma `{"resumen": {categoria: int}, "filas": [fila, ...]}` donde cada `fila` es `{"id": int, "cedula": str|None, "nombre": str|None, "id_usuario": str|None, "numero_contrato": str|None, "categoria": str, "motivo": str, "numero_pago": str|None, "fecha_pago": datetime|None, "valor_bruto_pago": int|None, "deducciones_pago": int|None, "valor_neto_pago": int|None, "concepto": str, "seleccionable": bool}` — usado por la Task 4 (recibe esta misma lista de filas) y por la Task 5 (UI).

- [ ] **Step 1: Escribir los tests que fallan**

Agrega a `tests/test_cargue_pagos_service.py` (nuevos imports arriba del archivo, junto a los existentes):

```python
import io
from datetime import date

import pandas as pd
import pytest

from app.services.cargue_pagos_service import (
    CarguePagosService,
    CAT_VALIDO,
    CAT_DUPLICADO_INTERNO,
    CAT_USUARIO_NO_ENCONTRADO,
    CAT_SIN_CONTRATO_ACTIVO,
    CAT_DATO_INVALIDO,
    CAT_YA_EXISTE,
    CAT_EXCEDE_LIMITE,
)


class _FakeRepo:
    def __init__(self, usuarios):
        self._usuarios = usuarios

    def listar(self):
        return self._usuarios


def _fila_excel(numero_doc=100185826, fecha="2026-03-31 03:41:42", bruto="1,000,000.00",
                 deducciones="0.00", neto="1,000,000.00", tipo_id="Cédula de Ciudadanía",
                 identificacion=79334686, concepto="HONORARIOS FEBRERO"):
    return {
        "Numero Documento": numero_doc,
        "Fecha de Registro": fecha,
        "Fecha de pago": fecha,
        "Estado": "Pagada",
        "Valor Bruto": bruto,
        "Valor Deducciones": deducciones,
        "Valor Neto": neto,
        "Tipo Identificacion": tipo_id,
        "Identificacion": identificacion,
        "Concepto Pago": concepto,
        "Objeto del Compromiso": concepto,
    }


def _excel_bytes(filas: list[dict]) -> io.BytesIO:
    df = pd.DataFrame(filas)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return buffer


def _usuario_con_contrato_activo(numero_documento="79334686", numero_contrato="3123123"):
    return {
        "_id": "u1",
        "numero_documento": numero_documento,
        "nombre_completo": "Carlos Acosta",
        "contratos": [
            {
                "numero": numero_contrato,
                "valor": 50_000_000,
                "fecha_inicio": date(2026, 1, 1),
                "fecha_fin": date(2026, 12, 31),
                "pagos": [],
            }
        ],
    }


def test_fila_valida_se_clasifica_como_valido():
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel()]))

    assert resultado["resumen"][CAT_VALIDO] == 1
    fila = resultado["filas"][0]
    assert fila["categoria"] == CAT_VALIDO
    assert fila["id_usuario"] == "u1"
    assert fila["numero_contrato"] == "3123123"
    assert fila["valor_bruto_pago"] == 1_000_000
    assert fila["seleccionable"] is True


def test_fila_con_nit_se_ignora_sin_generar_error():
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel(tipo_id="NIT", identificacion=800098911)]))

    assert resultado["filas"] == []
    assert sum(resultado["resumen"].values()) == 0


def test_usuario_no_encontrado():
    repo = _FakeRepo([])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel()]))

    assert resultado["filas"][0]["categoria"] == CAT_USUARIO_NO_ENCONTRADO


def test_usuario_sin_contrato_activo():
    usuario = _usuario_con_contrato_activo()
    usuario["contratos"][0]["fecha_fin"] = date(2020, 1, 1)
    repo = _FakeRepo([usuario])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel()]))

    assert resultado["filas"][0]["categoria"] == CAT_SIN_CONTRATO_ACTIVO


def test_fecha_vacia_es_dato_invalido():
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel(fecha=None)]))

    assert resultado["filas"][0]["categoria"] == CAT_DATO_INVALIDO


def test_valor_neto_negativo_es_dato_invalido():
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel(neto="-50,000.00")]))

    assert resultado["filas"][0]["categoria"] == CAT_DATO_INVALIDO


def test_filas_duplicadas_en_el_mismo_archivo():
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    fila = _fila_excel()
    resultado = servicio.procesar_archivo(_excel_bytes([fila, dict(fila)]))

    categorias = [f["categoria"] for f in resultado["filas"]]
    assert categorias.count(CAT_VALIDO) == 1
    assert categorias.count(CAT_DUPLICADO_INTERNO) == 1


def test_pago_ya_existente_en_bd():
    usuario = _usuario_con_contrato_activo()
    usuario["contratos"][0]["pagos"] = [{
        "numero_pago": "100185826",
        "fecha_pago": datetime(2026, 3, 31, tzinfo=timezone.utc),
        "valor_bruto_pago": 1_000_000,
        "deducciones_pago": 0,
        "valor_neto_pago": 1_000_000,
    }]
    repo = _FakeRepo([usuario])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel()]))

    assert resultado["filas"][0]["categoria"] == CAT_YA_EXISTE


def test_excede_limite_de_20_pagos_rechaza_el_contrato_completo():
    usuario = _usuario_con_contrato_activo()
    usuario["contratos"][0]["pagos"] = [
        {
            "numero_pago": f"existente-{i}",
            "fecha_pago": datetime(2026, 3, 31, tzinfo=timezone.utc),
            "valor_bruto_pago": 100,
            "deducciones_pago": 0,
            "valor_neto_pago": 100,
        }
        for i in range(19)
    ]
    repo = _FakeRepo([usuario])
    servicio = CarguePagosService(repositorio=repo)
    filas = [
        _fila_excel(numero_doc=200000000 + i, fecha=f"2026-0{(i % 9) + 1}-15 00:00:00", neto=f"{1000 + i}.00", bruto=f"{1000 + i}.00")
        for i in range(2)
    ]
    resultado = servicio.procesar_archivo(_excel_bytes(filas))

    categorias = [f["categoria"] for f in resultado["filas"]]
    assert categorias == [CAT_EXCEDE_LIMITE, CAT_EXCEDE_LIMITE]


def test_archivo_sin_columnas_requeridas_lanza_error_claro():
    df = pd.DataFrame([{"Columna random": 1}])
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    servicio = CarguePagosService(repositorio=_FakeRepo([]))
    with pytest.raises(ValueError, match="columnas"):
        servicio.procesar_archivo(buffer)
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_cargue_pagos_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'CarguePagosService'`.

- [ ] **Step 3: Agregar la clasificación a `cargue_pagos_service.py`**

Agrega al final de `app/services/cargue_pagos_service.py` (después de las funciones de limpieza ya escritas en la Task 2):

```python
import pandas as pd

from app.repositories.usuario_repo import UsuarioRepositorio
from app.services.certificacion_service import CertificacionService

CAT_VALIDO = "valido"
CAT_DUPLICADO_INTERNO = "duplicado_interno"
CAT_USUARIO_NO_ENCONTRADO = "usuario_no_encontrado"
CAT_SIN_CONTRATO_ACTIVO = "sin_contrato_activo"
CAT_DATO_INVALIDO = "dato_invalido"
CAT_YA_EXISTE = "ya_existe_en_bd"
CAT_EXCEDE_LIMITE = "excede_limite_pagos"

MOTIVOS = {
    CAT_USUARIO_NO_ENCONTRADO: "No existe ningún usuario con esta cédula",
    CAT_SIN_CONTRATO_ACTIVO: "El usuario no tiene ningún contrato activo",
    CAT_DATO_INVALIDO: "Fecha o valores monetarios inválidos o incompletos",
    CAT_DUPLICADO_INTERNO: "Fila duplicada dentro del mismo archivo (misma cédula, fecha y valor neto)",
    CAT_YA_EXISTE: "Ya existe un pago igual registrado en este contrato",
    CAT_EXCEDE_LIMITE: "El contrato superaría el límite de 20 pagos; no se carga ninguno de este lote",
    CAT_VALIDO: "Listo para cargar",
}


def _ultimo_contrato_activo(contratos: list) -> dict:
    """Mismo criterio que CertificacionService._ultimo_contrato_usuario (método de
    instancia), pero sin instanciar el servicio: usa directamente el classmethod
    puro _contrato_vigente para no forzar una conexión a Mongo en este servicio."""
    contrato = CertificacionService._contrato_vigente(contratos)
    if contrato:
        return contrato
    if not contratos:
        return {}
    return max(contratos, key=lambda c: c.get("fecha_inicio") or datetime.min)


class CarguePagosService:
    def __init__(self, repositorio=None):
        self.repositorio = repositorio or UsuarioRepositorio()

    def procesar_archivo(self, archivo) -> dict:
        df = pd.read_excel(archivo, header=0, engine="openpyxl")
        faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
        if faltantes:
            raise ValueError(
                "El archivo no tiene las columnas esperadas. Faltan: " + ", ".join(faltantes)
            )

        usuarios = self.repositorio.listar()
        por_cedula = {u["numero_documento"]: u for u in usuarios if u.get("numero_documento")}

        filas = []
        vistos_internos = set()
        candidatos_por_grupo = {}

        for _, registro in df.iterrows():
            if registro.get("Tipo Identificacion") != TIPO_IDENTIFICACION_CEDULA:
                continue

            cedula = limpiar_cedula(registro.get("Identificacion"))
            numero_pago = limpiar_numero_pago(registro.get("Numero Documento"))
            fecha_pago = limpiar_fecha_pago(registro.get("Fecha de pago"))
            valor_bruto = limpiar_valor_monetario(registro.get("Valor Bruto"))
            deducciones = limpiar_valor_monetario(registro.get("Valor Deducciones"))
            valor_neto = limpiar_valor_monetario(registro.get("Valor Neto"))
            concepto = str(registro.get("Concepto Pago") or registro.get("Objeto del Compromiso") or "").strip()

            fila = {
                "id": len(filas),
                "cedula": cedula,
                "nombre": None,
                "id_usuario": None,
                "numero_contrato": None,
                "categoria": None,
                "motivo": None,
                "numero_pago": numero_pago,
                "fecha_pago": fecha_pago,
                "valor_bruto_pago": valor_bruto,
                "deducciones_pago": deducciones,
                "valor_neto_pago": valor_neto,
                "concepto": concepto,
                "seleccionable": False,
            }

            if (
                cedula is None
                or numero_pago is None
                or fecha_pago is None
                or valor_bruto is None
                or deducciones is None
                or valor_neto is None
                or valor_bruto < 0
                or deducciones < 0
                or valor_neto < 0
            ):
                fila["categoria"] = CAT_DATO_INVALIDO
                fila["motivo"] = MOTIVOS[CAT_DATO_INVALIDO]
                filas.append(fila)
                continue

            clave_interna = (cedula, fecha_pago, valor_neto)
            if clave_interna in vistos_internos:
                fila["categoria"] = CAT_DUPLICADO_INTERNO
                fila["motivo"] = MOTIVOS[CAT_DUPLICADO_INTERNO]
                filas.append(fila)
                continue
            vistos_internos.add(clave_interna)

            usuario = por_cedula.get(cedula)
            if not usuario:
                fila["categoria"] = CAT_USUARIO_NO_ENCONTRADO
                fila["motivo"] = MOTIVOS[CAT_USUARIO_NO_ENCONTRADO]
                filas.append(fila)
                continue
            fila["nombre"] = usuario.get("nombre_completo")
            fila["id_usuario"] = str(usuario["_id"])

            contrato = _ultimo_contrato_activo(usuario.get("contratos") or [])
            if not contrato or not contrato.get("numero"):
                fila["categoria"] = CAT_SIN_CONTRATO_ACTIVO
                fila["motivo"] = MOTIVOS[CAT_SIN_CONTRATO_ACTIVO]
                filas.append(fila)
                continue
            fila["numero_contrato"] = contrato["numero"]

            pagos_actuales = contrato.get("pagos") or []
            existentes = {
                (p["numero_pago"], p["fecha_pago"], p["valor_neto_pago"]) for p in pagos_actuales
            }
            if (numero_pago, fecha_pago, valor_neto) in existentes:
                fila["categoria"] = CAT_YA_EXISTE
                fila["motivo"] = MOTIVOS[CAT_YA_EXISTE]
                filas.append(fila)
                continue

            grupo = (fila["id_usuario"], fila["numero_contrato"])
            candidatos_por_grupo.setdefault(grupo, {"cupo_actual": len(pagos_actuales), "filas": []})
            candidatos_por_grupo[grupo]["filas"].append(fila)
            filas.append(fila)

        for grupo, info in candidatos_por_grupo.items():
            total_tras_merge = info["cupo_actual"] + len(info["filas"])
            if total_tras_merge > MAX_PAGOS_POR_CONTRATO:
                for fila in info["filas"]:
                    fila["categoria"] = CAT_EXCEDE_LIMITE
                    fila["motivo"] = MOTIVOS[CAT_EXCEDE_LIMITE]
            else:
                for fila in info["filas"]:
                    fila["categoria"] = CAT_VALIDO
                    fila["motivo"] = MOTIVOS[CAT_VALIDO]
                    fila["seleccionable"] = True

        resumen = {}
        for fila in filas:
            resumen[fila["categoria"]] = resumen.get(fila["categoria"], 0) + 1

        return {"resumen": resumen, "filas": filas}
```

Nota: el `import pandas as pd` y el `from datetime import datetime` ya deben existir arriba del archivo (el segundo viene de la Task 2); agrega solo los imports nuevos (`UsuarioRepositorio`, `CertificacionService`) junto a los existentes, no dupliques `pandas`/`datetime`.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_cargue_pagos_service.py -v`
Expected: PASS (todos, 12 de la Task 2 + 10 nuevos).

- [ ] **Step 5: Commit**

```bash
git add app/services/cargue_pagos_service.py tests/test_cargue_pagos_service.py
git commit -m "feat: clasificacion de filas del excel de pagos (procesar_archivo)"
```

---

## Task 4: Escritura segura — `CarguePagosService.confirmar_carga`

**Files:**
- Modify: `app/services/cargue_pagos_service.py`
- Test: `tests/test_cargue_pagos_service.py`

**Interfaces:**
- Consumes: `UsuarioRepositorio.buscar_por_id(id_usuario) -> dict | None`, `UsuarioRepositorio.editar_contrato_en_usuario(id_usuario, numero_contrato, nuevo_contrato) -> None` (ambos ya existen en `app/repositories/usuario_repo.py`); `AuditoriaService.registrar_accion(usuario, accion, recurso, detalle=None, exito=True) -> None` (ya existe en `app/services/auditoria_service.py`); `UsuarioService._contrato_finalizado(contrato) -> bool`.
- Produces: `CarguePagosService.confirmar_carga(self, filas_seleccionadas: list[dict], usuario_que_carga: str) -> dict` con forma `{"ok": [{"id_usuario", "numero_contrato", "agregados": int}], "fallidos": [{"id_usuario", "numero_contrato", "motivo": str}]}` — usado por la Task 5.

- [ ] **Step 1: Escribir los tests que fallan**

Agrega a `tests/test_cargue_pagos_service.py`:

```python
class _FakeRepoEscritura(_FakeRepo):
    def __init__(self, usuarios):
        super().__init__(usuarios)
        self._por_id = {u["_id"]: u for u in usuarios}
        self.llamadas_editar = []

    def buscar_por_id(self, id_usuario):
        return self._por_id.get(id_usuario)

    def editar_contrato_en_usuario(self, id_usuario, numero_contrato, nuevo_contrato):
        self.llamadas_editar.append((id_usuario, numero_contrato, nuevo_contrato))
        usuario = self._por_id[id_usuario]
        for i, c in enumerate(usuario["contratos"]):
            if c["numero"] == numero_contrato:
                usuario["contratos"][i] = nuevo_contrato


class _FakeAuditoria:
    def __init__(self):
        self.registros = []

    def registrar_accion(self, usuario, accion, recurso, detalle=None, exito=True):
        self.registros.append((usuario, accion, recurso, detalle, exito))


def _fila_valida_para_confirmar(id_usuario="u1", numero_contrato="3123123", numero_pago="100185826",
                                  valor_bruto=1_000_000, valor_neto=1_000_000):
    return {
        "categoria": CAT_VALIDO,
        "id_usuario": id_usuario,
        "numero_contrato": numero_contrato,
        "numero_pago": numero_pago,
        "fecha_pago": datetime_import_helper(),
        "valor_bruto_pago": valor_bruto,
        "deducciones_pago": 0,
        "valor_neto_pago": valor_neto,
    }


def test_confirmar_carga_agrega_pago_y_recalcula_totales():
    usuario = _usuario_con_contrato_activo()
    repo = _FakeRepoEscritura([usuario])
    auditoria = _FakeAuditoria()
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = auditoria

    resultado = servicio.confirmar_carga([_fila_valida_para_confirmar()], usuario_que_carga="admin1")

    assert resultado["ok"] == [{"id_usuario": "u1", "numero_contrato": "3123123", "agregados": 1}]
    assert resultado["fallidos"] == []
    _, _, contrato_guardado = repo.llamadas_editar[0]
    assert contrato_guardado["pagos"][0]["numero_pago"] == "100185826"
    assert contrato_guardado["valor_total_pagado"] == 1_000_000
    assert contrato_guardado["valor_total_por_pagar_contrato"] == 49_000_000  # 50M - 1M
    assert len(auditoria.registros) == 1


def test_confirmar_carga_ignora_filas_que_no_son_validas():
    usuario = _usuario_con_contrato_activo()
    repo = _FakeRepoEscritura([usuario])
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    fila_no_valida = _fila_valida_para_confirmar()
    fila_no_valida["categoria"] = CAT_DATO_INVALIDO

    resultado = servicio.confirmar_carga([fila_no_valida], usuario_que_carga="admin1")

    assert resultado["ok"] == []
    assert repo.llamadas_editar == []


def test_confirmar_carga_es_idempotente_si_se_llama_dos_veces():
    usuario = _usuario_con_contrato_activo()
    repo = _FakeRepoEscritura([usuario])
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    fila = _fila_valida_para_confirmar()
    primera = servicio.confirmar_carga([fila], usuario_que_carga="admin1")
    segunda = servicio.confirmar_carga([fila], usuario_que_carga="admin1")

    assert primera["ok"][0]["agregados"] == 1
    assert segunda["ok"] == []  # ya existe, no se vuelve a agregar ni duplicar
    assert len(repo._por_id["u1"]["contratos"][0]["pagos"]) == 1


def test_confirmar_carga_revalida_cupo_al_momento_de_escribir():
    usuario = _usuario_con_contrato_activo()
    usuario["contratos"][0]["pagos"] = [
        {"numero_pago": f"x{i}", "fecha_pago": datetime_import_helper(), "valor_bruto_pago": 1,
         "deducciones_pago": 0, "valor_neto_pago": 1}
        for i in range(20)
    ]
    repo = _FakeRepoEscritura([usuario])
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    resultado = servicio.confirmar_carga([_fila_valida_para_confirmar()], usuario_que_carga="admin1")

    assert resultado["ok"] == []
    assert len(resultado["fallidos"]) == 1
    assert "20" in resultado["fallidos"][0]["motivo"] or "límite" in resultado["fallidos"][0]["motivo"].lower()


def test_confirmar_carga_aisla_fallos_entre_contratos():
    usuario_ok = _usuario_con_contrato_activo(numero_documento="1", numero_contrato="A")
    usuario_ok["_id"] = "u_ok"
    usuario_sin_contrato = _usuario_con_contrato_activo(numero_documento="2", numero_contrato="B")
    usuario_sin_contrato["_id"] = "u_fail"
    usuario_sin_contrato["contratos"] = []  # ya no tiene el contrato "B" al momento de confirmar

    repo = _FakeRepoEscritura([usuario_ok, usuario_sin_contrato])
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    filas = [
        _fila_valida_para_confirmar(id_usuario="u_ok", numero_contrato="A"),
        _fila_valida_para_confirmar(id_usuario="u_fail", numero_contrato="B"),
    ]
    resultado = servicio.confirmar_carga(filas, usuario_que_carga="admin1")

    assert len(resultado["ok"]) == 1
    assert resultado["ok"][0]["id_usuario"] == "u_ok"
    assert len(resultado["fallidos"]) == 1
    assert resultado["fallidos"][0]["id_usuario"] == "u_fail"
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `pytest tests/test_cargue_pagos_service.py -v`
Expected: FAIL — `AttributeError: 'CarguePagosService' object has no attribute 'confirmar_carga'`.

- [ ] **Step 3: Implementar `confirmar_carga`**

Agrega el import de `AuditoriaService` junto a los demás imports de `app/services/cargue_pagos_service.py`:

```python
from app.services.auditoria_service import AuditoriaService
```

Y dentro de la clase `CarguePagosService` (después de `__init__`, antes o después de `procesar_archivo`):

```python
    def __init__(self, repositorio=None):
        self.repositorio = repositorio or UsuarioRepositorio()
        self.auditoria = AuditoriaService()
```

(Reemplaza el `__init__` escrito en la Task 3 por este, que agrega `self.auditoria`.)

```python
    def confirmar_carga(self, filas_seleccionadas: list[dict], usuario_que_carga: str) -> dict:
        candidatas = [f for f in filas_seleccionadas if f["categoria"] == CAT_VALIDO]

        grupos = {}
        for fila in candidatas:
            clave = (fila["id_usuario"], fila["numero_contrato"])
            grupos.setdefault(clave, []).append(fila)

        ok = []
        fallidos = []

        for (id_usuario, numero_contrato), filas_grupo in grupos.items():
            try:
                usuario = self.repositorio.buscar_por_id(id_usuario)
                if not usuario:
                    raise ValueError("El usuario ya no existe.")
                contrato = next(
                    (c for c in usuario.get("contratos") or [] if c.get("numero") == numero_contrato),
                    None,
                )
                if not contrato:
                    raise ValueError("El contrato ya no existe para este usuario.")
                if UsuarioService._contrato_finalizado(contrato):
                    raise ValueError("El contrato ya no está activo.")

                pagos_actuales = contrato.get("pagos") or []
                existentes = {
                    (p["numero_pago"], p["fecha_pago"], p["valor_neto_pago"]) for p in pagos_actuales
                }

                pagos_nuevos = []
                for fila in filas_grupo:
                    clave_pago = (fila["numero_pago"], fila["fecha_pago"], fila["valor_neto_pago"])
                    if clave_pago in existentes:
                        continue
                    pagos_nuevos.append({
                        "numero_pago": fila["numero_pago"],
                        "fecha_pago": fila["fecha_pago"],
                        "valor_bruto_pago": fila["valor_bruto_pago"],
                        "deducciones_pago": fila["deducciones_pago"],
                        "valor_neto_pago": fila["valor_neto_pago"],
                    })
                    existentes.add(clave_pago)

                if not pagos_nuevos:
                    continue  # todos ya existían; nada que hacer, no es un fallo

                pagos_final = pagos_actuales + pagos_nuevos
                if len(pagos_final) > MAX_PAGOS_POR_CONTRATO:
                    raise ValueError(
                        f"El contrato superaría el límite de {MAX_PAGOS_POR_CONTRATO} pagos."
                    )

                valor_total_pagado = sum(p["valor_bruto_pago"] for p in pagos_final)
                valor_contrato = int(contrato.get("valor") or 0)

                contrato_actualizado = dict(contrato)
                contrato_actualizado["pagos"] = pagos_final
                contrato_actualizado["valor_total_pagado"] = valor_total_pagado
                contrato_actualizado["valor_total_por_pagar_contrato"] = abs(
                    valor_contrato - valor_total_pagado
                )

                self.repositorio.editar_contrato_en_usuario(id_usuario, numero_contrato, contrato_actualizado)
                self.auditoria.registrar_accion(
                    usuario=usuario_que_carga,
                    accion="cargue_pagos_excel",
                    recurso=f"usuario:{id_usuario}:contrato:{numero_contrato}",
                    detalle={"pagos_agregados": len(pagos_nuevos)},
                )
                ok.append({
                    "id_usuario": id_usuario,
                    "numero_contrato": numero_contrato,
                    "agregados": len(pagos_nuevos),
                })
            except ValueError as e:
                fallidos.append({
                    "id_usuario": id_usuario,
                    "numero_contrato": numero_contrato,
                    "motivo": str(e),
                })

        return {"ok": ok, "fallidos": fallidos}
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `pytest tests/test_cargue_pagos_service.py -v`
Expected: PASS (todos — Task 2 + Task 3 + los 5 nuevos de esta task).

- [ ] **Step 5: Commit**

```bash
git add app/services/cargue_pagos_service.py tests/test_cargue_pagos_service.py
git commit -m "feat: escritura segura de pagos con revalidacion al confirmar (confirmar_carga)"
```

---

## Task 5: Página de administración y registro en el menú

**Files:**
- Create: `app/pages_admin/admin_cargue_pagos.py`
- Create: `app/pages/16_admin_cargue_pagos.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `CarguePagosService.procesar_archivo(archivo) -> dict`, `CarguePagosService.confirmar_carga(filas_seleccionadas, usuario_que_carga) -> dict` (Tasks 3 y 4); `obtener_sesion()` (`app/core/sesion.py`); `mostrar_titulo_decorado(texto)` (`app/core/ui_titulos.py`).
- Produces: página Streamlit accesible en Administración solo para sesiones con `"pago.cargar"` en `sesion["permisos"]`.

- [ ] **Step 1: Crear la página de administración**

Crea `app/pages_admin/admin_cargue_pagos.py`:

```python
"""Cargue masivo de pagos de contratos desde el Excel de tesorería.

Flujo: subir archivo -> clasificar en memoria (sin tocar Mongo) -> el admin
revisa/ajusta la selección de filas "válido" -> confirma -> se escribe solo
lo seleccionado. Ver docs/superpowers/specs/2026-09-30-cargue-pagos-excel-design.md.
"""

import streamlit as st

from app.core.sesion import obtener_sesion
from app.core.ui_titulos import mostrar_titulo_decorado
from app.services.cargue_pagos_service import CarguePagosService, CAT_VALIDO

_ETIQUETAS_CATEGORIA = {
    "valido": "✅ Válido",
    "duplicado_interno": "⚠️ Duplicado en el archivo",
    "usuario_no_encontrado": "❌ Usuario no encontrado",
    "sin_contrato_activo": "❌ Sin contrato activo",
    "dato_invalido": "❌ Dato inválido",
    "ya_existe_en_bd": "ℹ️ Ya existe en BD",
    "excede_limite_pagos": "❌ Excede límite de 20 pagos",
}


@st.dialog("Confirmar carga de pagos", width="large")
def _dialog_confirmar(servicio: CarguePagosService, filas_marcadas: list, sesion: dict) -> None:
    contratos_afectados = {(f["id_usuario"], f["numero_contrato"]) for f in filas_marcadas}
    st.markdown(f"Se van a cargar **{len(filas_marcadas)} pagos** en **{len(contratos_afectados)} contratos**.")
    st.warning("Esta acción escribe en la base de datos. No se eliminará ni modificará ningún pago existente.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmar carga", type="primary", use_container_width=True):
            usuario_sesion = sesion.get("usuario") or "admin"
            resultado = servicio.confirmar_carga(filas_marcadas, usuario_que_carga=usuario_sesion)
            st.session_state["_cargue_pagos_resultado"] = resultado
            st.session_state.pop("_cargue_pagos_datos", None)
            st.session_state.pop("_cargue_pagos_confirmar", None)
            st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("_cargue_pagos_confirmar", None)
            st.rerun()


def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()
    if "pago.cargar" not in sesion.get("permisos", []):
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    mostrar_titulo_decorado("Cargue de pagos desde Excel")
    st.caption(
        "Sube el Excel de tesorería (.xlsx/.xlsm). El archivo se valida y clasifica "
        "en memoria; nada se guarda hasta que confirmes explícitamente la carga."
    )

    resultado_previo = st.session_state.pop("_cargue_pagos_resultado", None)
    if resultado_previo:
        if resultado_previo["ok"]:
            total_agregados = sum(r["agregados"] for r in resultado_previo["ok"])
            st.success(f"✅ Se cargaron {total_agregados} pagos en {len(resultado_previo['ok'])} contratos.")
        for fallo in resultado_previo["fallidos"]:
            st.error(f"❌ Contrato {fallo['numero_contrato']}: {fallo['motivo']}")

    archivo = st.file_uploader("Archivo de pagos", type=["xlsx", "xlsm"], key="_cargue_pagos_uploader")

    servicio = CarguePagosService()

    if archivo is not None:
        clave_archivo = f"{archivo.name}_{archivo.size}"
        if st.session_state.get("_cargue_pagos_archivo_clave") != clave_archivo:
            try:
                datos = servicio.procesar_archivo(archivo)
            except ValueError as e:
                st.error(f"No se pudo procesar el archivo: {e}")
                st.stop()
            st.session_state["_cargue_pagos_datos"] = datos
            st.session_state["_cargue_pagos_archivo_clave"] = clave_archivo

    datos = st.session_state.get("_cargue_pagos_datos")
    if not datos:
        return

    resumen = datos["resumen"]
    cols = st.columns(len(_ETIQUETAS_CATEGORIA))
    for col, (cat, etiqueta) in zip(cols, _ETIQUETAS_CATEGORIA.items()):
        col.metric(etiqueta, resumen.get(cat, 0))

    st.divider()
    st.markdown("**Detalle de registros** — solo puedes marcar los que están en estado Válido.")

    filas_validas = [f for f in datos["filas"] if f["categoria"] == CAT_VALIDO]
    filas_otras = [f for f in datos["filas"] if f["categoria"] != CAT_VALIDO]

    seleccion = {}
    for fila in filas_validas:
        etiqueta = (
            f"{fila['nombre']} (CC {fila['cedula']}) · contrato {fila['numero_contrato']} · "
            f"{fila['numero_pago']} · ${fila['valor_neto_pago']:,} · {fila['concepto'][:60]}"
        )
        seleccion[fila["id"]] = st.checkbox(etiqueta, value=True, key=f"_cargue_pagos_fila_{fila['id']}")

    if filas_otras:
        with st.expander(f"Registros con error o informativos ({len(filas_otras)})"):
            for fila in filas_otras:
                st.text(
                    f"[{_ETIQUETAS_CATEGORIA[fila['categoria']]}] CC {fila['cedula']} · "
                    f"{fila['motivo']}"
                )

    filas_marcadas = [f for f in filas_validas if seleccion.get(f["id"])]

    st.divider()
    if st.button(f"Confirmar carga ({len(filas_marcadas)} pagos seleccionados)", type="primary", disabled=not filas_marcadas):
        st.session_state["_cargue_pagos_confirmar"] = filas_marcadas

    if st.session_state.get("_cargue_pagos_confirmar"):
        _dialog_confirmar(servicio, st.session_state["_cargue_pagos_confirmar"], sesion)
```

- [ ] **Step 2: Crear el wrapper en `app/pages/`**

Mira `app/pages/10_admin_parametros.py` como referencia exacta de patrón y crea `app/pages/16_admin_cargue_pagos.py`:

```python
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.pages_admin import admin_cargue_pagos
from app.core.sesion import obtener_sesion

admin_cargue_pagos.render(obtener_sesion())
```

- [ ] **Step 3: Registrar la página en `app/main.py`**

Busca el bloque donde se agrega `pages/10_admin_parametros.py` (alrededor de la línea 1794-1795, dentro de `if es_admin_main:`) y agrega justo debajo, en el mismo bloque:

```python
    if "pago.cargar" in permisos_sesion:
        admin_pages.append(st.Page("pages/16_admin_cargue_pagos.py", title="Cargue de Pagos", icon="💰"))
```

- [ ] **Step 4: Verificación manual**

No hay infraestructura de pruebas automatizadas para páginas Streamlit en este proyecto (ver CLAUDE.md); se verifica a mano:

1. Run: `streamlit run app/main.py`
2. Inicia sesión como un usuario con rol `admin`. Confirma que "Cargue de Pagos" aparece en Administración.
3. Inicia sesión como un usuario sin el permiso `pago.cargar` (p. ej. rol `supervisor`). Confirma que la página NO aparece en el menú.
4. En "Cargue de Pagos", sube un Excel pequeño de prueba (3-4 filas) construido a mano con las columnas de `COLUMNAS_REQUERIDAS` más `Tipo Identificacion`/`Identificacion`/`Concepto Pago`, incluyendo: una fila con cédula de un usuario real de tu base de prueba con contrato activo (debe salir "Válido"), una fila con una cédula inventada (debe salir "Usuario no encontrado"), y una fila con `Tipo Identificacion = NIT` (no debe aparecer en el detalle).
5. Marca la fila válida, pulsa "Confirmar carga", confirma en el diálogo. Verifica el mensaje de éxito.
6. Abre ese usuario en "Mi Perfil" o en el admin de usuarios: confirma que el pago aparece en el plan de pagos del contrato, y que `valor_total_pagado`/`valor_total_por_pagar_contrato` quedaron actualizados.
7. Vuelve a subir el mismo archivo de prueba: la fila que ya cargaste debe salir ahora en "Ya existe en BD", no otra vez en "Válido".

- [ ] **Step 5: Commit**

```bash
git add app/pages_admin/admin_cargue_pagos.py app/pages/16_admin_cargue_pagos.py app/main.py
git commit -m "feat: pagina de administracion para cargue masivo de pagos desde Excel"
```
