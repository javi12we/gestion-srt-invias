from datetime import date, datetime, timezone

import pandas as pd
from streamlit.testing.v1 import AppTest

from app.core.balance_contrato import calcular_balance_pagos
from app.core.ui_contratos import _filas_desde_tabla, _tabla_pagos
from app.services.usuario_service import UsuarioService


def _pago(numero, bruto, neto=None, deducciones=0):
    return {
        "numero_pago": numero,
        "fecha_pago": date(2026, 3, 31),
        "valor_bruto_pago": bruto,
        "deducciones_pago": deducciones,
        "valor_neto_pago": bruto - deducciones if neto is None else neto,
    }


def test_pagado_es_la_suma_de_brutos_y_por_pagar_la_diferencia_con_el_valor_del_contrato():
    pagos = [_pago("1", 9_784_320, deducciones=166_667), _pago("2", 9_784_320, deducciones=166_666)]

    assert calcular_balance_pagos(22_932_000, pagos) == (19_568_640, 3_363_360)


def test_sin_pagos_todo_el_contrato_esta_por_pagar():
    assert calcular_balance_pagos(22_932_000, []) == (0, 22_932_000)
    assert calcular_balance_pagos(None, None) == (0, 0)


def test_por_pagar_no_es_negativo_si_los_pagos_superan_el_valor():
    assert calcular_balance_pagos(1_000_000, [_pago("1", 1_500_000)]) == (1_500_000, 0)


def test_guardar_contrato_ignora_los_totales_digitados_y_los_calcula_de_los_pagos():
    contrato = UsuarioService._construir_contrato("3123123", {
        "valor": 22_932_000,
        "valor_total_pagado": 19_568_640,
        "valor_total_por_pagar_contrato": 19_235_307,  # valor viejo digitado a mano
        "pagos": [_pago("1", 10_000_000), _pago("2", 9_568_640), _pago("", 999)],  # sin número: no se guarda
    })

    assert len(contrato["pagos"]) == 2
    assert contrato["valor_total_pagado"] == 19_568_640
    assert contrato["valor_total_por_pagar_contrato"] == 3_363_360


def test_orden_de_inicio_es_texto_libre():
    contrato = UsuarioService._construir_contrato(
        "1", {"fecha_orden_inicio_contrato": "  SRT-2026-00123 del 03/02/2026 "}
    )
    assert contrato["fecha_orden_inicio_contrato"] == "SRT-2026-00123 del 03/02/2026"

    assert "fecha_orden_inicio_contrato" not in UsuarioService._construir_contrato(
        "1", {"fecha_orden_inicio_contrato": "   "}
    )


def test_orden_de_inicio_guardada_como_fecha_se_muestra_como_texto():
    assert UsuarioService.texto_orden_inicio(datetime(2026, 2, 3, tzinfo=timezone.utc)) == "03/02/2026"
    assert UsuarioService.texto_orden_inicio(None) == ""
    assert UsuarioService.texto_orden_inicio("RAD 123") == "RAD 123"


_SCRIPT_BALANCE = '''
from datetime import datetime
import streamlit as st
from app.core.ui_contratos import render_balance_y_pagos

st.session_state.setdefault("c1_show_balance_general", True)
st.session_state.setdefault("_pagos", [
    {"numero_pago": "1", "fecha_pago": datetime(2026, 3, 31), "valor_bruto_pago": 10000000,
     "deducciones_pago": 0, "valor_neto_pago": 10000000},
    {"numero_pago": "2", "fecha_pago": datetime(2026, 4, 30), "valor_bruto_pago": 9568640,
     "deducciones_pago": 333333, "valor_neto_pago": 9235307},
])
contrato = {
    "numero": "1", "valor": 22932000, "pagos": st.session_state["_pagos"],
    "valor_total_pagado": 19568640, "valor_total_por_pagar_contrato": 19235307,
}
st.session_state["_retorno"] = render_balance_y_pagos("c1", contrato, valor_contrato=22932000)
'''


def _valores_balance(at):
    return {t.key: t.value for t in at.text_input if t.key and t.key.endswith("_calc")}


def test_pantalla_muestra_el_balance_calculado_y_no_el_guardado():
    at = AppTest.from_string(_SCRIPT_BALANCE, default_timeout=30).run()

    assert not at.exception
    assert _valores_balance(at) == {
        "c1_val_total_por_pagar_calc": "$ 3.363.360",
        "c1_val_tot_pagado_calc": "$ 19.568.640",
    }
    assert "valor_total_pagado" not in at.session_state["_retorno"]


def test_pantalla_se_refresca_si_los_pagos_cambian_en_bd():
    at = AppTest.from_string(_SCRIPT_BALANCE, default_timeout=30).run()
    assert [p["numero_pago"] for p in at.session_state["_retorno"]["pagos"]] == ["1", "2"]

    # Un cargue masivo deja otros pagos en la BD: el borrador viejo se descarta.
    at.session_state["_pagos"] = [
        {"numero_pago": "349074626", "fecha_pago": datetime(2026, 9, 2), "valor_bruto_pago": 3_675_000,
         "deducciones_pago": 24_941, "valor_neto_pago": 3_650_059},
    ]
    at.run()

    assert not at.exception
    assert at.session_state["_retorno"]["pagos"] == [{
        "numero_pago": "349074626",
        "fecha_pago": date(2026, 9, 2),
        "valor_bruto_pago": 3_675_000,
        "deducciones_pago": 24_941,
        "valor_neto_pago": 3_650_059,
    }]
    assert _valores_balance(at)["c1_val_tot_pagado_calc"] == "$ 3.675.000"


def test_tabla_de_pagos_interpreta_valores_pegados_con_formato():
    tabla = pd.DataFrame([
        {"N° Pago": " 78279326 ", "Fecha": pd.Timestamp(2026, 3, 18), "Valor Bruto": "3057600,00",
         "Deducciones": "20.751", "Valor Neto": "3,036,849.00"},
        {"N° Pago": None, "Fecha": pd.NaT, "Valor Bruto": None, "Deducciones": "", "Valor Neto": "abc"},
    ])

    filas, avisos = _filas_desde_tabla(tabla)

    assert filas == [
        {"N° Pago": "78279326", "Fecha": date(2026, 3, 18), "Valor Bruto": 3057600,
         "Deducciones": 20751, "Valor Neto": 3036849},
        {"N° Pago": "", "Fecha": None, "Valor Bruto": 0, "Deducciones": 0, "Valor Neto": 0},
    ]
    assert len(avisos) == 1 and "Pago #2, Valor Neto" in avisos[0]


def test_tabla_de_pagos_muestra_los_valores_con_miles_y_los_relee_igual():
    filas = [{"N° Pago": "1", "Fecha": date(2026, 3, 18), "Valor Bruto": 3057600,
              "Deducciones": 8300, "Valor Neto": 0}]
    tabla = _tabla_pagos(filas)

    assert tabla.loc[0, ["Valor Bruto", "Deducciones", "Valor Neto"]].tolist() == ["$ 3.057.600", "$ 8.300", "$ 0"]
    assert _filas_desde_tabla(tabla) == (filas, [])


def test_tabla_de_pagos_vacia_tiene_las_columnas_esperadas():
    tabla = _tabla_pagos([])

    assert list(tabla.columns) == ["N° Pago", "Fecha", "Valor Bruto", "Deducciones", "Valor Neto"]
    assert str(tabla["Fecha"].dtype).startswith("datetime64")
    assert _filas_desde_tabla(tabla) == ([], [])


def test_sesion_abierta_con_la_version_anterior_del_formulario_no_falla():
    """Una sesión que ya tenía guardada la firma de los pagos (formulario viejo,
    de un campo por pago) pero no la base de la tabla debe sembrarla igual."""
    at = AppTest.from_string(_SCRIPT_BALANCE, default_timeout=30).run()
    firma = at.session_state["c1_pagos_firma"]

    nueva = AppTest.from_string(_SCRIPT_BALANCE, default_timeout=30)
    nueva.session_state["c1_pagos_firma"] = firma
    nueva.session_state["c1_pagos_ids"] = [0, 1]
    nueva.run()

    assert not nueva.exception
    assert len(nueva.session_state["_retorno"]["pagos"]) == 2
