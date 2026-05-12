import sys
import os

# Asegurar que el directorio raíz del proyecto esté en el PYTHONPATH
# Esto soluciona el "ModuleNotFoundError: No module named 'app'" en Streamlit Cloud
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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


def pantalla_dashboard() -> None:
    sesion = obtener_sesion()
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


def logout():
    sesion = obtener_sesion()
    servicio_sesiones = SesionService()
    if sesion:
        servicio_sesiones.cerrar_sesion(sesion.get("id_sesion"), sesion, "logout")
    cerrar_sesion()
    st.rerun()


@st.cache_resource
def inicializar_aplicacion():
    """Ejecuta las tareas de inicialización de la base de datos una sola vez."""
    MongoBootstrapService().asegurar_estructura()
    CatalogoService().asegurar_catalogos_base()
    UsuarioService().asegurar_usuario_admin_inicial()


# Inicializar la aplicación (usará caché si ya se ejecutó)
inicializar_aplicacion()


if not sesion_activa():
    pantalla_login()
else:
    sesion = obtener_sesion()
    
    # Definición de páginas
    page_dashboard = st.Page(pantalla_dashboard, title="Inicio", icon="🏠", default=True)
    page_perfil = st.Page("pages/2_mi_perfil.py", title="Mi Perfil", icon="👤")
    page_correspondencia = st.Page("pages/2_correspondencia.py", title="Correspondencia", icon="📬")
    
    # Páginas de administración
    admin_pages = []
    if "usuario.ver" in sesion.get("permisos", []):
        admin_pages.append(st.Page("pages/1_admin_usuarios.py", title="Usuarios", icon="👥"))
    if "rol.ver" in sesion.get("permisos", []):
        admin_pages.append(st.Page("pages/3_admin_roles.py", title="Roles", icon="🔐"))
    if "reporte.ver" in sesion.get("permisos", []):
        admin_pages.append(st.Page("pages/4_reportes.py", title="Reportes", icon="📊"))
    
    # Agrupar páginas
    menu_dict = {
        "Principal": [page_dashboard, page_correspondencia, page_perfil],
    }
    
    if admin_pages:
        menu_dict["Administración"] = admin_pages
        
    pg = st.navigation(menu_dict)
    
    # Personalización del sidebar
    st.sidebar.title("Menú")
    st.sidebar.success(f"Sesión: {sesion['usuario']}")
    
    with st.sidebar:
        st.divider()
        if st.button("🚪 Cerrar sesión", key="logout_btn", use_container_width=True):
            logout()
            
    pg.run()

