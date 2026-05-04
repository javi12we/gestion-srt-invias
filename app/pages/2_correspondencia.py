import streamlit as st

from app.core.permisos import tiene_permiso
from app.core.sesion import obtener_sesion


st.title("Correspondencia")
sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()

# Tracking de vistas removido

if not tiene_permiso(sesion.get("permisos", []), "correspondencia.ver") and "admin" not in sesion.get("roles", []):
    st.info("Todavía no has definido permisos para este módulo.")

st.write("Aquí irá el registro, búsqueda y seguimiento de correspondencia.")
