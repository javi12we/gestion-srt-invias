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
                background-color: #16120F !important; /* Café muy oscuro sutil */
                border-right: 1px solid rgba(255, 140, 0, 0.15) !important;
            }
            [data-testid="stHeader"] {
                background-color: rgba(22, 18, 15, 0.8) !important;
                border-top: 3px solid #FF8C00 !important;
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

            /* Botones primarios (Accento Naranja Login) */
            .stApp button[kind="primary"],
            .stApp [data-testid="stBaseButton-primary"] {
                background-color: #FF8C00 !important;
                color: #FFFFFF !important;
                border: none !important;
                font-weight: bold !important;
            }

            /* 3. HOVER (Mantener lo funcional) */
            .stApp button:hover {
                border-color: #FF8C00 !important;
                color: #FF8C00 !important;
                background-color: rgba(255, 140, 0, 0.1) !important;
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
                background-color: rgba(255, 140, 0, 0.15) !important;
                color: #FF8C00 !important;
            }

            /* 6. OTROS */
            div[data-testid="stTooltipContent"] {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border: 1px solid #444 !important;
            }
            hr { border-color: #444 !important; }

            /* Navegación lateral (Sidebar Menu) - Integración Login */
            div[data-testid="stSidebarNavItems"] a:hover {
                background-color: rgba(255, 140, 0, 0.1) !important;
                color: #FF8C00 !important;
            }
            div[data-testid="stSidebarNavItems"] a[aria-current="page"] {
                background-color: rgba(255, 140, 0, 0.15) !important;
                border-left: 4px solid #FF8C00 !important;
            }
            div[data-testid="stSidebarNavItems"] a[aria-current="page"] span {
                color: #FF8C00 !important;
                font-weight: bold !important;
            }
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
                background-color: #FFF9F2 !important; /* Naranja muy pálido/cálido */
                border-right: 1px solid rgba(255, 140, 0, 0.15) !important;
            }
            [data-testid="stHeader"] {
                border-top: 3px solid #FF8C00 !important;
            }
            /* Botones en modo claro */
            .stButton>button {
                border-radius: 8px !important;
                transition: all 0.3s ease !important;
            }
            .stButton>button[kind="primary"] {
                background-color: #FF8C00 !important;
                color: #FFFFFF !important;
                border: none !important;
                font-weight: bold !important;
            }
            .stButton>button:hover {
                border-color: #FF8C00 !important;
                color: #FF8C00 !important;
            }
            /* Tooltips en modo claro */
            div[data-testid="stTooltipContent"] {
                background-color: #FFFFFF !important;
                color: #262730 !important;
                border: 1px solid #E9ECEF !important;
                border-radius: 4px !important;
            }
            /* Navegación lateral (Sidebar Menu) - Integración Login */
            div[data-testid="stSidebarNavItems"] a:hover {
                background-color: rgba(255, 140, 0, 0.08) !important;
                color: #FF8C00 !important;
            }
            div[data-testid="stSidebarNavItems"] a[aria-current="page"] {
                background-color: rgba(255, 140, 0, 0.12) !important;
                border-left: 4px solid #FF8C00 !important;
            }
            div[data-testid="stSidebarNavItems"] a[aria-current="page"] span {
                color: #FF8C00 !important;
                font-weight: bold !important;
            }
            </style>
        """, unsafe_allow_html=True)

aplicar_tema()


def pantalla_login() -> None:
    # Aplicar diseño institucional unificado con geometrías y fondo colorido
    st.markdown("""
        <style>
        /* ===== Tipografía General ===== */
        .stApp, .stMarkdown, .stText, p, h1, h2, h3, h4, h5, h6, span, label, li, 
        [data-testid="stWidgetLabel"] p, [data-testid="stMarkdownContainer"] p {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
            color: #FAFAFA !important;
        }

        /* ===== Fondo Principal (Más profundidad, mezcla de naranjas y cafés vivos) ===== */
        .stApp {
            background: linear-gradient(135deg, #E87A1E 0%, #A65012 50%, #3D1E0A 100%) !important;
            overflow: hidden;
            z-index: 1;
        }

        /* ===== Geometrías Adaptables Superpuestas ===== */
        /* Círculo difuso iluminado (blanco pastel / naranja claro) */
        .stApp::before {
            content: ""; position: fixed; width: 650px; height: 650px;
            background: radial-gradient(circle, rgba(255, 230, 180, 0.25) 0%, transparent 60%);
            top: -150px; left: -150px; border-radius: 50%; z-index: 0;
            box-shadow: 800px 500px 0 150px rgba(255, 160, 40, 0.15); /* Clon disperso */
            pointer-events: none;
        }

        /* Cuadrado redondeado rotado (Naranja fuerte) */
        .stApp::after {
            content: ""; position: fixed; width: 450px; height: 450px;
            background: linear-gradient(135deg, rgba(255, 140, 0, 0.4) 0%, rgba(200, 80, 10, 0.1) 100%);
            bottom: 5%; right: -100px; 
            border-radius: 60px; 
            transform: rotate(35deg);
            z-index: 0;
            box-shadow: -800px -300px 0 80px rgba(100, 45, 15, 0.3); /* Clon oscuro a la izquierda */
            pointer-events: none;
        }

        /* ===== Estilizar el Formulario de Login (Oscuro café-naranjado) ===== */
        [data-testid="stForm"] {
            background-color: rgba(35, 20, 12, 0.9) !important; /* Modo oscuro pero con base café/naranja profundo */
            border: 1px solid rgba(255, 150, 50, 0.3) !important; /* Borde naranja vibrante pero sutil */
            border-radius: 20px !important;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6), inset 0 0 20px rgba(255, 140, 0, 0.08) !important;
            backdrop-filter: blur(15px) !important;
            -webkit-backdrop-filter: blur(15px) !important;
            padding: 3rem 2.5rem !important; 
            position: relative;
            z-index: 10;
        }

        /* ===== Entradas de Datos (Inputs más pequeños) ===== */
        div[data-baseweb="input"] {
            background-color: rgba(10, 5, 3, 0.8) !important; /* Fondo aplicado al contenedor para incluir el ojito */
            border: 1px solid rgba(255, 140, 0, 0.3) !important; 
            border-radius: 8px !important;
            overflow: hidden;
        }
        div[data-baseweb="input"]:focus-within {
            border-color: #FF8C00 !important; 
            box-shadow: 0 0 0 1px #FF8C00 !important;
            background-color: rgba(20, 10, 5, 0.95) !important;
        }

        .stApp input {
            background-color: transparent !important; /* Transparente para heredar el contenedor */
            color: #FAFAFA !important;
            border: none !important;
            padding: 0.4rem 0.8rem !important; 
            font-size: 14.5px !important; 
            min-height: 42px !important; 
            box-shadow: none !important;
        }
        .stApp input:focus {
            box-shadow: none !important;
            border: none !important;
            background-color: transparent !important;
        }
        
        /* Corregir el icono del ojito asegurando que su botón interno sea transparente */
        div[data-baseweb="input"] > div,
        div[data-baseweb="input"] button {
            background-color: transparent !important;
            color: #FAFAFA !important; /* Color del ícono del ojo en blanco/gris claro */
        }

        /* Ajuste de márgenes en labels de los inputs */
        div[data-testid="stWidgetLabel"] {
            margin-bottom: -5px !important;
        }
        div[data-testid="stWidgetLabel"] p {
            font-size: 13.5px !important;
            color: #F0E6DD !important; /* Blanco hueso/café muy claro */
        }

        /* ===== Botón de Ingreso (Naranja Vibrante - Solo afecta botones reales de Streamlit) ===== */
        div[data-testid="stForm"] div.stButton > button, 
        button[kind="primary"] {
            background-color: #FF8C00 !important; /* Naranja espectacular y vibrante */
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: bold !important;
            font-size: 16px !important;
            padding: 0.5rem 1rem !important; 
            min-height: 46px !important; 
            transition: all 0.3s ease !important;
            margin-top: 1.5rem !important;
        }
        div[data-testid="stForm"] div.stButton > button:hover, 
        button[kind="primary"]:hover {
            background-color: #E67A00 !important;
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(255, 140, 0, 0.5) !important;
        }
        /* Forzar texto interior del botón a blanco */
        div[data-testid="stForm"] div.stButton > button p, 
        button[kind="primary"] p {
            color: #FFFFFF !important;
        }
        
        /* ===== Ocultar elementos Streamlit ===== */
        [data-testid="stHeader"], [data-testid="stSidebar"] {
            display: none !important;
        }
        #MainMenu, footer, header {
            visibility: hidden;
        }

        /* ===== Ocultar botón de expandir imagen en Streamlit ===== */
        [data-testid="stImage"] button,
        [data-testid="StyledFullScreenButton"] {
            display: none !important;
            visibility: hidden !important;
        }

        /* ===== Contenedor extra para añadir un polígono (Flecha/Triángulo flotante) ===== */
        .block-container::before {
            content: ""; position: fixed; width: 300px; height: 300px;
            background: linear-gradient(135deg, rgba(255, 230, 200, 0.15) 0%, transparent 100%);
            top: 25%; left: 8%;
            clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
            transform: rotate(25deg);
            z-index: 0; pointer-events: none;
        }

        /* ===== Botón de Ayuda (Popover) Forma Píldora ===== */
        div[data-testid="stPopover"] {
            display: flex;
            justify-content: center;
            margin-top: 15px;
        }
        /* Ocultar forzosamente el icono default de flecha de Streamlit (expand_more) que daña el botón */
        div[data-testid="stPopover"] button svg,
        div[data-testid="stPopover"] button [data-testid="stIcon"],
        div[data-testid="stPopover"] button span[data-testid="stIcon"],
        div[data-testid="stPopover"] button span[class*="material-"],
        div[data-testid="stPopover"] button span:not([data-testid="stMarkdownContainer"] *) {
            display: none !important;
            visibility: hidden !important;
        }
        div[data-testid="stPopover"] button {
            background-color: #FF8C00 !important; /* Naranja institucional para combinar con fondo */
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 25px !important; /* Forma de píldora redondeada */
            width: auto !important;
            height: 45px !important;
            padding: 0 20px !important;
            font-size: 16px !important;
            font-weight: bold !important;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4), 0 0 10px rgba(255, 140, 0, 0.3) !important;
            transition: transform 0.3s ease !important;
        }
        div[data-testid="stPopover"] button:hover {
            transform: translateY(-2px) !important;
            background-color: #E67E00 !important;
            box-shadow: 0 6px 15px rgba(0, 0, 0, 0.6), 0 0 15px rgba(255, 140, 0, 0.5) !important;
        }
        /* Texto interior del botón popover a blanco para evitar conflictos */
        div[data-testid="stPopover"] button p,
        div[data-testid="stPopover"] button span {
            color: #FFFFFF !important;
        }
        
        /* ===== Estilos del contenido del Popover (Aislando del modo oscuro/claro) ===== */
        div[data-testid="stPopoverBody"],
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] > div,
        div[role="dialog"] {
            background-color: rgba(10, 5, 3, 0.98) !important; /* Color oscuro de las cajas de texto */
            border: 1px solid #FF8C00 !important; /* Borde naranja */
            border-radius: 12px !important;
            padding: 1.5rem !important;
            box-shadow: 0 10px 30px rgba(0,0,0,0.8) !important;
        }
        /* Forzar texto a blanco independientemente del tema de Streamlit */
        div[data-testid="stPopoverBody"] *,
        div[data-baseweb="popover"] *,
        div[role="dialog"] * {
            color: #FAFAFA !important;
        }

        /* ===== Ajuste contenido principal ===== */
        .block-container {
            position: relative;
            z-index: 10;
            padding-top: 2rem !important;
            padding-bottom: 1rem !important;
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1.8, 1.1, 1.8])
    
    with col2:
        # Agrupamos título y logo DENTRO del formulario para que queden sobre la caja oscura
        with st.form("form_login", clear_on_submit=False):
            # Nuevo logo de la empresa (Agrandado en proporción)
            logo_path = os.path.join("app", "assets", "INVIAS_login_logo.png")
            if os.path.exists(logo_path):
                # Aumentamos el tamaño relativo
                c_logo1, c_logo2, c_logo3 = st.columns([1, 2.8, 1])
                with c_logo2:
                    st.image(logo_path, use_container_width=True)
            
            # Subir el título para acercarlo más al logo
            st.markdown("<h2 style='text-align: center; margin-top: -25px; margin-bottom: 0px;'>Gestiones Digitales SRTI</h2>", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align: center; font-weight: normal; margin-top: 5px; color: #F0E6DD;'>Inicio de sesión</h4>", unsafe_allow_html=True)
            
            st.write("") # Espaciador
            
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            
            st.write("") # Espaciador
            
            # Reducir el ancho específico del botón usando columnas internas
            c_btn1, c_btn2, c_btn3 = st.columns([1, 3, 1])
            with c_btn2:
                enviar = st.form_submit_button("Ingresar", use_container_width=True, type="primary")

        if enviar:
            servicio = AuthService()
            sesion, error = servicio.iniciar_sesion(usuario.strip(), password)
            if error:
                st.error(error)
                return

            iniciar_sesion(sesion)
            st.rerun()

        # ===== Popover de Ayuda/Soporte =====
        with st.popover("🎧 Soporte Técnico"):
            st.markdown("<h4 style='margin-bottom: 0px;'>Centro de Soporte</h4>", unsafe_allow_html=True)
            st.markdown("<p style='font-size: 14px; color: #D3C3B8;'>Si tienes problemas de acceso, comunícate con nosotros.</p>", unsafe_allow_html=True)
            
            st.write("📧 **Correo Electrónico:**")
            st.markdown(
                "<div style='background-color: rgba(20, 10, 5, 0.8); border: 1px solid rgba(255, 140, 0, 0.4); border-radius: 8px; padding: 12px; text-align: center; color: #FF8C00; font-family: monospace; font-size: 16px; letter-spacing: 0.5px;'>jdelgadov@invias.gov.co</div>", 
                unsafe_allow_html=True
            )
            
            st.write("")
            whatsapp_url = "https://wa.me/573169333607?text=Hola,%0A%0ANecesito%20ayuda%20con%20el%20aplicativo%20*Gestiones%20Digitales%20SRTI*.%0A%0AQuedo%20atento%20a%20su%20soporte.%20Gracias."
            st.markdown(f"<a href='{whatsapp_url}' target='_blank' style='display: block; background-color: #25D366; color: white; text-align: center; padding: 10px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 5px; box-shadow: 0 4px 10px rgba(37,211,102,0.3);'>🟢 Escribir a WhatsApp</a>", unsafe_allow_html=True)


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
    
    with st.sidebar:
        # Tarjeta de Perfil de Usuario Premium
        with st.container(border=True):
            nombre = sesion.get("nombre_completo") or "Usuario"
            username = sesion.get("usuario")
            email = sesion.get("email") or ""
            roles_lista = sesion.get("roles", [])
            
            # Icono según rol
            if "admin" in roles_lista:
                avatar = "🛡️"
            elif "direccion" in roles_lista:
                avatar = "👩‍💼"
            else:
                avatar = "👤"
            
            c_avatar, c_info = st.columns([1, 3])
            with c_avatar:
                st.markdown(f"<div style='font-size: 2.3em; text-align: center; margin-top: 3px;'>{avatar}</div>", unsafe_allow_html=True)
            with c_info:
                st.markdown(f"**{nombre}**")
                st.markdown(f"<div style='color: gray; font-size: 0.85em; margin-top: -5px;'>@{username}</div>", unsafe_allow_html=True)
                if email:
                    st.markdown(f"<div style='color: gray; font-size: 0.75em; word-break: break-all; margin-top: 2px;'>{email}</div>", unsafe_allow_html=True)
            
            # Mostrar badges elegantes para cada rol
            roles_html = ""
            for r in roles_lista:
                roles_html += f"<span style='background-color: rgba(0, 128, 255, 0.15); color: #0080ff; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; font-weight: bold; margin-right: 4px; display: inline-block;'>{r.title()}</span>"
            if roles_html:
                st.write("")
                st.markdown(roles_html, unsafe_allow_html=True)

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

