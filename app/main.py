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



st.set_page_config(
    page_title="Gestión de Correspondencia", 
    layout="wide", 
    page_icon="app/assets/invias_fav_ico_3.ico"
)

# --- LÓGICA DE TEMA (MODO OSCURO/CLARO) ---
if "tema" not in st.session_state:
    st.session_state.tema = "Claro"

def aplicar_tema():
    if st.session_state.tema == "Oscuro":
        st.markdown("""
            <style>
            /* --- ESTILOS MODO OSCURO (REFUERZO NUCLEAR) --- */
            .stApp {
                background-color: #0E1117 !important;
                color: #FAFAFA !important;
            }
            [data-testid="stSidebar"] {
                background-color: #1A1C24 !important;
            }
            [data-testid="stHeader"] {
                background-color: rgba(14, 17, 23, 0.8) !important;
            }

            /* 1. TIPOGRAFÍA Y ETIQUETAS (GLOBAL) */
            .stApp, .stMarkdown, .stText, p, h1, h2, h3, h4, h5, h6, span, label, li, 
            [data-testid="stWidgetLabel"] p, [data-testid="stMarkdownContainer"] p {
                color: #FAFAFA !important;
            }

            /* 2. BOTONES (REFUERZO NUCLEAR DE ESTADO BASE) */
            /* Forzar el estado inicial de TODOS los botones en la App */
            .stApp button, 
            .stApp [data-testid="stBaseButton-secondary"],
            .stApp [data-testid="stBaseButton-primary"],
            .stApp div[data-testid="stPopover"] > button,
            div[data-testid="stColumn"] button {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border: 1px solid #444 !important;
                border-radius: 8px !important;
            }

            /* Forzar que el contenido interno (texto, iconos) sea blanco desde el inicio */
            .stApp button p, .stApp button span, .stApp button div, .stApp button svg {
                color: #FAFAFA !important;
                fill: #FAFAFA !important;
            }

            /* Botones primarios (Accento INVIAS) */
            .stApp button[kind="primary"],
            .stApp [data-testid="stBaseButton-primary"] {
                background-color: #FDB913 !important;
                color: #000000 !important;
                border: none !important;
            }

            /* 3. HOVER (Mantener lo funcional) */
            .stApp button:hover {
                border-color: #FDB913 !important;
                color: #FDB913 !important;
                background-color: #31333F !important;
            }

            /* 4. CONTENEDORES (DIÁLOGOS, POPOVERS Y FORMULARIOS) */
            div[data-testid="stDialog"] > div:first-child {
                background-color: rgba(0, 0, 0, 0.7) !important;
            }
            
            div[role="dialog"], 
            div[data-testid="stDialog"] div[role="dialog"],
            div[data-testid="stPopoverBody"], 
            div[data-testid="stPopoverContent"],
            div[data-testid="stForm"] {
                background-color: #1A1C24 !important;
                color: #FAFAFA !important;
                border: 1px solid #444 !important;
                box-shadow: 0 4px 15px rgba(0,0,0,0.5) !important;
            }

            /* Estilo para los contenedores que explícitamente tienen borde (border=True) sin alterar los contenedores invisibles/transparentes */
            div[data-testid="stVerticalBlockBorderWrapper"] {
                border-color: #444 !important;
            }

            /* 5. ENTRADAS DE DATOS (INPUTS, SELECTS) */
            .stApp input, .stApp textarea, .stApp select,
            .stApp div[data-baseweb="select"],
            .stApp div[data-baseweb="input"],
            .stApp div[data-baseweb="select"] > div {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border-color: #444 !important;
            }

            /* Forzar color de texto en selectboxes y sus opciones seleccionadas */
            .stApp div[data-baseweb="select"] span, 
            .stApp div[data-baseweb="select"] div {
                color: #FAFAFA !important;
            }

            /* --- REFUERZO PARA DESPLEGABLES (MENÚS PORTAL) --- */
            /* Estos elementos suelen estar fuera de .stApp al final del body */
            div[data-baseweb="popover"], 
            div[data-baseweb="menu"], 
            div[data-baseweb="listbox"],
            div[role="listbox"],
            [data-testid="stVirtualDropdown"] {
                background-color: #1A1C24 !important;
                color: #FAFAFA !important;
                border: 1px solid #444 !important;
                box-shadow: 0 4px 15px rgba(0,0,0,0.5) !important;
            }

            div[data-baseweb="popover"] *, 
            div[data-baseweb="menu"] *, 
            div[role="option"],
            div[role="listbox"] * {
                background-color: #1A1C24 !important;
                color: #FAFAFA !important;
            }

            /* Hover en opciones de listas */
            div[role="option"]:hover, 
            li[role="option"]:hover,
            [data-testid="stVirtualDropdown"] li:hover {
                background-color: #31333F !important;
                color: #FDB913 !important;
            }

            /* 6. OTROS */
            div[data-testid="stTooltipContent"] {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border: 1px solid #444 !important;
            }
            hr { border-color: #444 !important; }
            </style>
            </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
            /* Estilos modo claro (limpio) */
            .stApp {
                background-color: #FFFFFF !important;
                color: #262730 !important;
            }
            [data-testid="stSidebar"] {
                background-color: #F8F9FA !important;
            }
            /* Botones en modo claro */
            .stButton>button {
                border-radius: 8px !important;
                transition: all 0.3s ease !important;
            }
            .stButton>button[kind="primary"] {
                background-color: #FDB913 !important;
                color: #000000 !important;
                border: none !important;
            }
            /* Tooltips en modo claro */
            div[data-testid="stTooltipContent"] {
                background-color: #FFFFFF !important;
                color: #262730 !important;
                border: 1px solid #E9ECEF !important;
                border-radius: 4px !important;
            }
            </style>
        """, unsafe_allow_html=True)

aplicar_tema()


def pantalla_login() -> None:
    # Ocultar header y sidebar mediante CSS
    st.markdown("""
        <style>
        [data-testid="stHeader"], [data-testid="stSidebar"] {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Crear un diseño centrado usando columnas
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        # Espacio superior para separar del borde
        st.write("")
        st.write("")
        st.write("")
        
        # Logo de la empresa (opcional)
        logo_path = os.path.join("app", "assets", "logo_invias.png")
        if os.path.exists(logo_path):
            # Centrar el logo usando columnas internas o markdown
            c_logo1, c_logo2, c_logo3 = st.columns([1, 2, 1])
            with c_logo2:
                st.image(logo_path, use_container_width=True)
        
        st.markdown("<h1 style='text-align: center;'>Gestión de Correspondencia</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; font-weight: normal;'>Inicio de sesión</h3>", unsafe_allow_html=True)

        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            enviar = st.form_submit_button("Ingresar", use_container_width=True, type="primary")

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
        admin_pages.append(st.Page("pages/5_dashboard.py", title="Dashboard", icon="📊"))
        admin_pages.append(st.Page("pages/4_reportes.py", title="Reportes y Evidencias", icon="📄"))
    
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
        es_oscuro = st.toggle("Modo Oscuro 🌙", value=(st.session_state.tema == "Oscuro"))
        nuevo_tema = "Oscuro" if es_oscuro else "Claro"
        if nuevo_tema != st.session_state.tema:
            st.session_state.tema = nuevo_tema
            st.rerun()
        st.divider()
        if st.button("🚪 Cerrar sesión", key="logout_btn", use_container_width=True):
            logout()
            
    pg.run()

