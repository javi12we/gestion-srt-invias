import streamlit as st

from app.core.sesion import cerrar_sesion, iniciar_sesion, obtener_sesion, sesion_activa
from app.services.catalogo_service import CatalogoService
from app.services.mongo_bootstrap_service import MongoBootstrapService
from app.services.auth_service import AuthService
from app.services.sesion_service import SesionService
from app.services.usuario_service import UsuarioService


st.set_page_config(page_title="Gestión de Correspondencia", layout="wide")


def pantalla_login() -> None:
    st.title("Gestión de Correspondencia")
    st.subheader("Inicio de sesión")

    with st.form("form_login", clear_on_submit=False):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        enviar = st.form_submit_button("Ingresar")

    if enviar:
        servicio = AuthService()
        sesion, error = servicio.iniciar_sesion(usuario.strip(), password)
        if error:
            st.error(error)
            return

        iniciar_sesion(sesion)
        st.rerun()


def pantalla_principal() -> None:
    sesion = obtener_sesion()
    servicio_sesiones = SesionService()
    st.sidebar.title("Menú")
    st.sidebar.success(f"Sesión: {sesion['usuario']}")

    # Menú condicional basado en permisos
    st.sidebar.subheader("Módulos")
    col1, col2, col3 = st.sidebar.columns(3)
    
    with col1:
        if "usuario.ver" in sesion.get("permisos", []):
            st.page_link("pages/1_admin_usuarios.py", label="👥 Usuarios")
    
    with col2:
        if "rol.ver" in sesion.get("permisos", []):
            st.page_link("pages/3_admin_roles.py", label="🔐 Roles")
    with col3:
        if "reporte.ver" in sesion.get("permisos", []):
            st.page_link("pages/4_reportes.py", label="📊 Reportes")
    
    st.sidebar.divider()
    st.sidebar.subheader("Personal")
    col3, col4 = st.sidebar.columns(2)
    with col3:
        st.page_link("pages/2_mi_perfil.py", label="👤 Perfil")
    with col4:
        st.page_link("pages/2_correspondencia.py", label="📬 Correspondencia")
    
    st.sidebar.divider()
    if st.sidebar.button("🚪 Cerrar sesión", key="cerrar_sesion"):
        servicio_sesiones.cerrar_sesion(sesion.get("id_sesion"), sesion, "logout")
        cerrar_sesion()
        st.rerun()

    roles = sesion.get("roles", [])
    es_admin = any(rol in {"admin", "administrador"} for rol in roles)

    st.title("Gestión de Correspondencia")
    st.subheader(f"Hola, {sesion.get('nombre_completo') or sesion['usuario']}.")
    st.write(
        "Este espacio te muestra lo esencial para entrar rápido a tu trabajo: "
        "tu perfil, tus accesos principales y los módulos disponibles según tu rol."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Usuario", sesion["usuario"])
    col2.metric("Roles asignados", len(roles))
    col3.metric("Módulos visibles", 2 + int(es_admin))

    st.divider()
    st.subheader("Accesos rápidos")
    rapido1, rapido2 = st.columns(2)
    with rapido1:
        st.info("Perfil personal: revisa tus datos y cambia tu contraseña cuando lo necesites.")
    with rapido2:
        st.info("Correspondencia: entra al módulo operativo para trabajar con tus registros.")

    if es_admin:
        st.divider()
        st.subheader("Administración")
        admin1, admin2 = st.columns(2)
        with admin1:
            st.warning("Usuarios: alta, edición y control de estado de cuentas.")
        with admin2:
            st.warning("Roles: configuración de accesos y permisos del sistema.")

    st.divider()
    st.subheader("Tu acceso")
    st.write(f"**Nombre:** {sesion.get('nombre_completo') or 'Sin registrar'}")
    st.write(f"**Usuario:** {sesion['usuario']}")
    st.write(f"**Roles:** {', '.join(roles) or 'Sin roles'}")

    st.caption("Usa el menú lateral para entrar a los módulos disponibles según tu rol.")


MongoBootstrapService().asegurar_estructura()
CatalogoService().asegurar_catalogos_base()
UsuarioService().asegurar_usuario_admin_inicial()

if not sesion_activa():
    pantalla_login()
else:
    pantalla_principal()
