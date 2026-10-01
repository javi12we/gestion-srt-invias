import pytest
from streamlit.testing.v1 import AppTest

from app.core.ui_pesos import formato_pesos, interpretar_pesos


@pytest.mark.parametrize("texto, esperado", [
    ("1000,00", 1000),          # el caso reportado: no debe volverse 100000
    ("1000.00", 1000),
    ("1000", 1000),
    ("1.000", 1000),
    ("1,000", 1000),
    ("1.000,00", 1000),
    ("1,000.00", 1000),
    ("22.932.000", 22_932_000),
    ("22,932,000.00", 22_932_000),
    ("26,026,880.00", 26_026_880),
    ("$ 3.057.600", 3_057_600),
    (" 3 057 600 COP ", 3_057_600),
    ("1000,5", 1001),           # los decimales se redondean al peso
    ("1000,49", 1000),
    ("1000,", 1000),
    ("1000.0000", 1000),
    ("0,50", 1),
    ("0", 0),
    ("", 0),
    (None, 0),
    (3057600, 3_057_600),
])
def test_interpretar_pesos(texto, esperado):
    assert interpretar_pesos(texto) == esperado


@pytest.mark.parametrize("texto", ["abc", "12a", "-500", "1e5", ",", "1.000,0000"])
def test_interpretar_pesos_rechaza_lo_que_no_es_un_numero(texto):
    assert interpretar_pesos(texto) is None


def test_lo_que_se_muestra_formateado_se_vuelve_a_leer_igual():
    for valor in (0, 500, 8_300, 20_751, 1_223_040, 22_932_000):
        assert interpretar_pesos(formato_pesos(valor)) == valor


_SCRIPT = '''
import streamlit as st
from app.core.ui_pesos import entrada_pesos

# Estado entero que dejó en la sesión el st.number_input que había antes.
st.session_state.setdefault("e_val_1", 22932000)
st.session_state["_valor"] = entrada_pesos("Valor total de contrato (COP)", value=22932000, key="e_val_1")
st.session_state["_adicion"] = entrada_pesos("Adición", value=None, minimo=1, key="adi")
'''


def test_campo_toma_1000_al_pegar_1000_coma_00_y_lo_avisa():
    at = AppTest.from_string(_SCRIPT, default_timeout=30).run()
    assert not at.exception
    assert at.session_state["_valor"] == 22_932_000
    assert at.session_state["_adicion"] == 1

    at.text_input(key="e_val_1_pesos").set_value("1000,00").run()

    assert at.session_state["_valor"] == 1000
    assert [c.value for c in at.caption] == ["Se toma como $ 1.000"]


def test_campo_con_texto_invalido_conserva_el_valor_guardado():
    at = AppTest.from_string(_SCRIPT, default_timeout=30).run()

    at.text_input(key="e_val_1_pesos").set_value("mil pesos").run()

    assert at.session_state["_valor"] == 22_932_000
    assert len(at.error) == 1
