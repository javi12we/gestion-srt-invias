import streamlit as st

from app.core.sesion import obtener_sesion
# Imports de sesión removidos
from app.services.auth_service import AuthService


st.title("Mi perfil")
sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()

# Tracking de vistas removido

col1, col2 = st.columns(2)

with col1:
    st.subheader("Datos de acceso")
    st.write(f"**Usuario:** {sesion['usuario']}")
    st.write(f"**Nombre:** {sesion.get('nombre_completo') or 'Sin registrar'}")

with col2:
    st.subheader("Acceso asignado")
    st.write(f"**Roles:** {', '.join(sesion.get('roles', [])) or 'Sin roles'}")
    st.write("Los permisos detallados se gestionan internamente según tu rol.")

st.divider()
st.subheader("Cambiar contraseña")

with st.form("form_cambiar_password"):
    pwd_actual = st.text_input("Contraseña actual", type="password")
    pwd_nueva = st.text_input("Contraseña nueva", type="password")
    pwd_confirmar = st.text_input("Confirmar contraseña nueva", type="password")
    enviar = st.form_submit_button("Cambiar contraseña")

if enviar:
    if pwd_nueva != pwd_confirmar:
        st.error("Las contraseñas nuevas no coinciden")
    else:
        auth_service = AuthService()
        exito, mensaje = auth_service.cambiar_password(sesion["id"], pwd_actual, pwd_nueva)
        if exito:
            st.success(mensaje)
        else:
            st.error(mensaje)