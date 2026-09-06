import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado
from app.core.sesion import obtener_sesion

st.set_page_config(
    page_title="Despacho",
    page_icon="app/assets/invias_fav_ico_3.ico",
    layout="wide",
)

sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()

mostrar_titulo_decorado("Despacho")

st.info("El módulo de Despacho se encuentra actualmente en desarrollo.")
