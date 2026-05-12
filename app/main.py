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
from app.services.correspondencia_service import CorrespondenciaService



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
    
    # Obtener métricas reales (siempre personales según lo solicitado)
    servicio_corr = CorrespondenciaService()
    id_filtro = sesion.get("id")
    metricas = servicio_corr.obtener_metricas_dashboard(id_usuario=id_filtro)


    st.title("Gestión de Correspondencia")
    st.subheader(f"Bienvenido(a), {sesion.get('nombre_completo') or sesion['usuario']}.")
    
    st.markdown("**Vista actual:** `Personal (Mis asignaciones)`")


    # Métricas de Valor
    st.write("")
    m1, m2, m3 = st.columns(3)
    
    with m1:
        st.metric(
            label="Pendientes de Trámite", 
            value=metricas["pendientes"],
            help="Radicados que aún no han sido respondidos o archivados."
        )
    with m2:
        # El delta se muestra en rojo si hay urgentes
        st.metric(
            label="Urgentes o Vencidos", 
            value=metricas["urgentes"],
            delta=f"{metricas['urgentes']} críticos" if metricas["urgentes"] > 0 else None,
            delta_color="inverse",
            help="Radicados vencidos o que vencen en los próximos 3 días."
        )
    with m3:
        st.metric(
            label="Radicados Nuevos", 
            value=metricas["recientes"],
            help="Correspondencia ingresada en las últimas 48 horas."
        )

    st.divider()
    
    # Secciones de Acción
    col_acciones, col_guia = st.columns([2, 1])
    
    with col_acciones:
        st.subheader("🎯 Acciones rápidas")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📂 Ir a Correspondencia", use_container_width=True, type="primary"):
                st.switch_page("pages/2_correspondencia.py")
        with c2:
            if st.button("👤 Ver mi Perfil", use_container_width=True):
                st.switch_page("pages/2_mi_perfil.py")
        
        st.write("")
        st.markdown("""
        ### Recomendaciones:
        - **Prioriza lo urgente:** Revisa primero los radicados marcados con tiempo crítico.
        - **Mantén la trazabilidad:** Cada vez que realices un avance, regístralo en el sistema.
        - **Cierra el ciclo:** No olvides marcar como 'Respondido' o 'Archivado' para limpiar tu lista de pendientes.
        """)

    with col_guia:
        st.info("**Tip del día**")
        st.write("Puedes filtrar la correspondencia por fecha de vencimiento en el módulo principal para organizar mejor tu jornada.")
        
        if es_admin:
            st.warning("**Nota de Admin**")
            st.write("Como administrador, tienes acceso a la configuración de usuarios y roles desde el menú lateral.")

    st.divider()
    st.caption(f"Sesión activa como: {sesion['usuario']} | Roles: {', '.join(roles)}")



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

