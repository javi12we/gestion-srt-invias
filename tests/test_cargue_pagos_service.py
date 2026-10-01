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
