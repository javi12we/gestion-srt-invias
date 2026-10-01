import io
from datetime import datetime, timezone

import pandas as pd
import pytest

from app.services.cargue_pagos_service import (
    limpiar_cedula,
    limpiar_numero_pago,
    limpiar_valor_monetario,
    limpiar_fecha_pago,
    CarguePagosService,
    CAT_VALIDO,
    CAT_DUPLICADO_INTERNO,
    CAT_USUARIO_NO_ENCONTRADO,
    CAT_SIN_CONTRATO_ACTIVO,
    CAT_DATO_INVALIDO,
    CAT_YA_EXISTE,
    CAT_EXCEDE_LIMITE,
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
                "fecha_inicio": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "fecha_fin": datetime(2026, 12, 31, tzinfo=timezone.utc),
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
    usuario["contratos"][0]["fecha_fin"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
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
