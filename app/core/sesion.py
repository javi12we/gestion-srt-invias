import streamlit as st


CLAVE_SESION = "usuario_autenticado"


def iniciar_sesion(usuario: dict) -> None:
    st.session_state[CLAVE_SESION] = usuario


def obtener_sesion():
    return st.session_state.get(CLAVE_SESION)


def cerrar_sesion() -> None:
    st.session_state.pop(CLAVE_SESION, None)


def sesion_activa() -> bool:
    return obtener_sesion() is not None
