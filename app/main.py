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
from app.services.politica_service import PoliticaService
from app.core.ui_titulos import mostrar_titulo_decorado

st.set_page_config(
    page_title="Gestión de Correspondencia", 
    layout="wide", 
    page_icon="app/assets/invias_fav_ico_3.ico"
)

def aplicar_tema():
    dark_mode = st.session_state.get("dark_mode", False)
    st.markdown("""
        <style>

        /* =====================================================
           BORDE NARANJA GLOBAL SUPERIOR
        ===================================================== */

        .stApp {

            border-top: 2px solid #FF8C00;
        }

        /* =====================================================
           SIDEBAR BASE
        ===================================================== */

        [data-testid="stSidebar"] {

            background:

                radial-gradient(
                    circle at 90% 8%,
                    rgba(255,140,0,0.08) 0%,
                    transparent 18%
                ),

                linear-gradient(
                    180deg,
                    #26160D 0%,
                    #1A1008 100%
                ) !important;

            border-right: 1px solid rgba(255,140,0,0.35) !important;

            box-shadow:
                inset -1px 0 0 rgba(255,140,0,0.10);

            overflow: hidden;
        }

        /* =====================================================
           HEADER SUPERIOR
        ===================================================== */

        [data-testid="stHeader"] {

            background: rgba(35,20,12,0.96) !important;

            border-bottom: 1px solid rgba(255,140,0,0.55) !important;

            box-shadow:
                0 1px 0 rgba(255,140,0,0.15);
        }

        /* =====================================================
           CONTENIDO PRINCIPAL
        ===================================================== */

        .main .block-container {

            border-top: 1px solid rgba(255,140,0,0.18);

            padding-top: 2rem !important;
        }

        .main {

            box-shadow:
                inset 0 1px 0 rgba(255,140,0,0.10);
        }

        /* =====================================================
           TEXTO GENERAL
        ===================================================== */

        [data-testid="stSidebar"] * {

            color: #F4F4F4 !important;
        }

        /* =====================================================
           CONTENEDOR DEL MENÚ
           MÁS NARANJA / CÁLIDO
        ===================================================== */

        div[data-testid="stSidebarNav"] {

            background:

                radial-gradient(
                    circle at top right,
                    rgba(255,170,0,0.055) 0%,
                    transparent 28%
                ),

                radial-gradient(
                    circle at bottom left,
                    rgba(255,140,0,0.040) 0%,
                    transparent 30%
                ),

                linear-gradient(
                    180deg,
                    rgba(68,32,10,0.96) 0%,
                    rgba(48,22,8,0.98) 100%
                ) !important;

            border: 1px solid rgba(255,140,0,0.14);

            border-radius: 16px;

            padding: 8px 7px;

            margin-top: 8px;

            box-shadow:
                inset 0 0 18px rgba(255,140,0,0.03),
                0 0 18px rgba(255,140,0,0.025);

            position: relative;

            overflow: hidden;
        }

        /* =====================================================
           ITEMS MENÚ
        ===================================================== */

        div[data-testid="stSidebarNav"] ul {

            gap: 0px !important;

            padding-top: 0px !important;

            padding-bottom: 0px !important;

            position: relative;
        }

        /* ITEM */

        div[data-testid="stSidebarNav"] a {

            border-radius: 7px !important;

            transition: all 0.12s ease !important;

            background: transparent !important;

            min-height: 27px !important;

            height: 27px !important;

            padding-top: 0px !important;
            padding-bottom: 0px !important;

            padding-left: 7px !important;
            padding-right: 6px !important;

            margin-bottom: 1px !important;

            display: flex !important;

            align-items: center !important;

            border-left: none !important;

            box-shadow: none !important;
        }

        /* CONTENEDOR INTERNO */

        div[data-testid="stSidebarNav"] a > div {

            padding-top: 0px !important;
            padding-bottom: 0px !important;

            gap: 6px !important;

            align-items: center !important;
        }

        /* ICONOS */

        div[data-testid="stSidebarNav"] a svg {

            width: 13px !important;
            height: 13px !important;

            min-width: 13px !important;
        }

        /* =====================================================
           TEXTO OPCIONES
        ===================================================== */

        div[data-testid="stSidebarNav"] a span {

            color: #F4F4F4 !important;

            font-weight: 300 !important;

            font-size: 13.5px !important;

            letter-spacing: 0px !important;

            line-height: 1 !important;

            opacity: 0.95 !important;
        }

        /* HOVER */

        div[data-testid="stSidebarNav"] a:hover {

            background: rgba(255,255,255,0.03) !important;

            transform: translateX(1px);
        }

        /* =====================================================
           ITEM ACTIVO
        ===================================================== */

        div[data-testid="stSidebarNav"] a[aria-current="page"] {

            background:
                rgba(255,140,0,0.08) !important;

            border-left: none !important;

            box-shadow: none !important;
        }

        /* TEXTO ITEM ACTIVO */

        div[data-testid="stSidebarNav"] a[aria-current="page"] span {

            color: #FFFFFF !important;

            font-weight: 400 !important;
        }

        /* Ocultar "Mi Perfil" del menú: se accede desde el botón de la tarjeta.
           La página sigue registrada en st.navigation (ruta /mi_perfil) para que
           st.page_link funcione. */

        div[data-testid="stSidebarNav"] li:has(a[href$="/mi_perfil"]) {

            display: none !important;
        }

        /* =====================================================
           SOLO TÍTULOS DE SECCIÓN
        ===================================================== */

        div[data-testid="stSidebarNav"] > div > div > p {

            color: #FF9800 !important;

            font-weight: 700 !important;

            font-size: 12px !important;

            margin-top: 7px !important;

            margin-bottom: 6px !important;

            opacity: 1 !important;

            letter-spacing: 0.3px;
        }

        /* =====================================================
           SEPARADORES
        ===================================================== */

        [data-testid="stSidebar"] hr {

            border: none !important;

            border-top: 1px solid rgba(255,140,0,0.10) !important;
        }

        /* =====================================================
           TARJETA PERFIL
        ===================================================== */

        .st-key-perfil_card {

            background:

                radial-gradient(
                    circle at top right,
                    rgba(255,170,0,0.08) 0%,
                    transparent 40%
                ),

                linear-gradient(
                    135deg,
                    #552A0B 0%,
                    #442008 50%,
                    #321606 100%
                ) !important;

            border: 2px solid #FF9800 !important;

            border-radius: 18px !important;

            box-shadow:
                0 6px 18px rgba(0,0,0,0.40),
                inset 0 0 14px rgba(255,170,0,0.03);

            overflow: hidden !important;

            position: relative;

            padding: 18px !important;

            margin-bottom: 15px;
        }

        /* Glow tarjeta */

        .st-key-perfil_card::before {

            content: "";

            position: absolute;

            top: -60px;
            right: -60px;

            width: 160px;
            height: 160px;

            border-radius: 50%;

            background:
                radial-gradient(
                    circle,
                    rgba(255,180,0,0.15) 0%,
                    transparent 70%
                );

            pointer-events: none;
        }

        /* Enlace "Ver mi perfil" (page_link) dentro de la tarjeta */

        .st-key-perfil_card a {
            display: flex !important;
            align-items: center;
            justify-content: center;
            gap: 6px;
            width: fit-content !important;
            margin: 12px auto 0 auto !important;
            padding: 5px 14px !important;
            border-radius: 9px !important;
            background: rgba(255,152,0,0.12) !important;
            border: 1px solid rgba(255,152,0,0.35) !important;
            transition: background 0.15s ease;
            position: relative;
            z-index: 1;
        }

        .st-key-perfil_card a:hover {
            background: rgba(255,152,0,0.24) !important;
        }

        .st-key-perfil_card a p,
        .st-key-perfil_card a span {
            color: #FFB74D !important;
            font-weight: 600 !important;
            font-size: 12.5px !important;
        }

        /* =====================================================
           BADGES / ROLES
        ===================================================== */

        [data-testid="stSidebar"] span[style*="border-radius: 12px"] {

            background:
                linear-gradient(
                    180deg,
                    rgba(120,60,0,0.72) 0%,
                    rgba(90,40,0,0.90) 100%
                ) !important;

            color: #FFD27A !important;

            border: 1px solid rgba(255,170,0,0.45) !important;

            box-shadow:
                inset 0 0 8px rgba(255,180,0,0.05),
                0 0 10px rgba(255,140,0,0.08);

            font-weight: 500 !important;

            padding: 2px 8px !important;
        }

        /* =====================================================
           BOTÓN
        ===================================================== */

        [data-testid="stSidebar"] button {

            background: #FF9800 !important;

            color: white !important;

            border: none !important;

            border-radius: 999px !important;

            font-weight: 500 !important;

            min-height: 40px !important;

            box-shadow:
                0 5px 14px rgba(255,145,0,0.16);
        }

        [data-testid="stSidebar"] button:hover {

            background: #F08C00 !important;

            transform: translateY(-1px);
        }

        /* =====================================================
           FORMAS DECORATIVAS PREMIUM
        ===================================================== */

        /* CÍRCULO SUPERIOR DERECHO GRANDE */

        [data-testid="stSidebar"]::before {

            content: "";

            position: fixed;

            top: -140px;
            right: -140px;

            width: 340px;
            height: 340px;

            border-radius: 50%;

            border: 38px solid rgba(255,140,0,0.045);

            pointer-events: none;
        }

        /* ROMBO INFERIOR IZQUIERDO */

        [data-testid="stSidebar"]::after {

            content: "";

            position: fixed;

            bottom: 60px;
            left: -110px;

            width: 210px;
            height: 210px;

            transform: rotate(45deg);

            background:
                linear-gradient(
                    135deg,
                    rgba(255,140,0,0.028),
                    transparent
                );

            border: 1px solid rgba(255,140,0,0.040);

            border-radius: 34px;

            pointer-events: none;
        }

        /* POLÍGONO SUPERIOR DERECHO */

        [data-testid="stSidebar"] > div:first-child::before {

            content: "";

            position: absolute;

            top: 120px;
            right: -55px;

            width: 160px;
            height: 160px;

            clip-path: polygon(
                25% 6%,
                75% 6%,
                100% 50%,
                75% 94%,
                25% 94%,
                0% 50%
            );

            background:
                linear-gradient(
                    135deg,
                    rgba(255,170,0,0.028),
                    transparent
                );

            border: 1px solid rgba(255,140,0,0.030);

            transform: rotate(14deg);

            pointer-events: none;
        }

        /* POLÍGONO CENTRAL IZQUIERDO */

        [data-testid="stSidebar"] > div:first-child::after {

            content: "";

            position: absolute;

            left: -60px;

            top: 42%;

            width: 170px;
            height: 170px;

            clip-path: polygon(
                50% 0%,
                100% 38%,
                82% 100%,
                18% 100%,
                0% 38%
            );

            background:
                linear-gradient(
                    135deg,
                    rgba(255,140,0,0.018),
                    transparent
                );

            border: 1px solid rgba(255,140,0,0.022);

            transform: rotate(-10deg);

            pointer-events: none;
        }

        /* FIGURA CIRCULAR SUPERIOR MENU */

        div[data-testid="stSidebarNav"]::after {

            content: "";

            position: absolute;

            top: -45px;
            left: -35px;

            width: 130px;
            height: 130px;

            border-radius: 50%;

            border: 18px solid rgba(255,170,0,0.028);

            pointer-events: none;
        }

        /* HEXÁGONO CENTRAL MENU */

        div[data-testid="stSidebarNav"]::before {

            content: "";

            position: absolute;

            right: -55px;
            top: 36%;

            width: 150px;
            height: 150px;

            background:
                linear-gradient(
                    135deg,
                    rgba(255,140,0,0.022),
                    transparent
                );

            clip-path: polygon(
                25% 6%,
                75% 6%,
                100% 50%,
                75% 94%,
                25% 94%,
                0% 50%
            );

            border: 1px solid rgba(255,140,0,0.028);

            pointer-events: none;

            transform: rotate(12deg);
        }

        /* TRIÁNGULO SUPERIOR */

        div[data-testid="stSidebarNav"] ul::before {

            content: "";

            position: absolute;

            top: 120px;
            left: -70px;

            width: 140px;
            height: 140px;

            background:
                linear-gradient(
                    135deg,
                    rgba(255,180,0,0.018),
                    transparent
                );

            clip-path: polygon(
                50% 0%,
                0% 100%,
                100% 100%
            );

            transform: rotate(-14deg);

            pointer-events: none;
        }

        /* ROMBO CENTRAL MENU */

        div[data-testid="stSidebarNav"] ul::after {

            content: "";

            position: absolute;

            bottom: 120px;
            right: -60px;

            width: 120px;
            height: 120px;

            border-radius: 24px;

            transform: rotate(45deg);

            border: 1px solid rgba(255,140,0,0.022);

            background:
                linear-gradient(
                    135deg,
                    rgba(255,140,0,0.015),
                    transparent
                );

            pointer-events: none;
        }

        /* LINEAS DIFUSAS */

        [data-testid="stSidebarNav"] span::after {

            content: "";

            position: absolute;

            bottom: -180px;
            right: -130px;

            width: 260px;
            height: 260px;

            border-radius: 48px;

            border: 1px solid rgba(255,140,0,0.015);

            transform: rotate(45deg);

            pointer-events: none;
        }

        /* GLOW DIFUSO IZQUIERDO */

        .logo-static-container::before {

            content: "";

            position: absolute;

            left: -90px;

            bottom: -60px;

            width: 200px;
            height: 200px;

            border-radius: 50%;

            background:
                radial-gradient(
                    circle,
                    rgba(255,160,0,0.035) 0%,
                    transparent 70%
                );

            pointer-events: none;
        }

        /* GLOW SUPERIOR SUAVE */

        .logo-static-container::after {

            content: "";

            position: absolute;

            top: -50px;

            right: -70px;

            width: 160px;
            height: 160px;

            border-radius: 50%;

            background:
                radial-gradient(
                    circle,
                    rgba(255,180,0,0.025) 0%,
                    transparent 72%
                );

            pointer-events: none;
        }

        /* =====================================================
           TOGGLE MODO OSCURO EN SIDEBAR
        ===================================================== */

        [data-testid="stSidebar"] [data-testid="stCheckbox"] {
            padding: 4px 0 2px 0;
        }

        [data-testid="stSidebar"] [data-testid="stCheckbox"] label {
            font-size: 12.5px !important;
            color: rgba(244,244,244,0.78) !important;
            letter-spacing: 0.2px;
            font-weight: 400 !important;
            gap: 8px;
            cursor: pointer;
        }

        [data-testid="stSidebar"] [data-testid="stCheckbox"] label:hover {
            color: #F4F4F4 !important;
            opacity: 1 !important;
        }

        [data-testid="stSidebar"] [data-testid="stCheckbox"] label p {
            font-size: 12.5px !important;
            color: rgba(244,244,244,0.78) !important;
            font-weight: 400 !important;
        }

        </style>
    """, unsafe_allow_html=True)

    if dark_mode:
        st.markdown("""
            <style>
            /* =====================================================
               MODO OSCURO — SOLO ÁREA DE CONTENIDO PRINCIPAL
               La barra lateral NO se ve afectada gracias a sus
               propios estilos con !important
            ===================================================== */

            /* Fondos */
            .stApp {
                background-color: #1A1A2A !important;
            }

            .main, [data-testid="stMain"] {
                background-color: #1A1A2A !important;
            }

            .main .block-container,
            [data-testid="block-container"] {
                background-color: #1A1A2A !important;
            }

            /* ── TEXTO NUCLEAR: igual que hace el sidebar con su propio selector ── */
            :is(.main, [data-testid="stMain"]) * {
                color: #FFFFFF !important;
            }

            /* Texto secundario / labels (sobrescriben el blanco puro) */
            :is(.main, [data-testid="stMain"]) [data-testid="stWidgetLabel"] *,
            :is(.main, [data-testid="stMain"]) [data-testid="stMetricLabel"] * {
                color: #D8D8F0 !important;
            }

            /* Captions */
            :is(.main, [data-testid="stMain"]) [data-testid="stCaptionContainer"] *,
            :is(.main, [data-testid="stMain"]) small {
                color: #B0B0CC !important;
            }

            /* Métricas — valores grandes en blanco puro y resaltados */
            :is(.main, [data-testid="stMain"]) [data-testid="stMetricValue"] * {
                color: #FFFFFF !important;
                font-weight: 700 !important;
            }

            /* Contenedores con borde */
            :is(.main, [data-testid="stMain"]) [data-testid="stVerticalBlockBorderWrapper"] {
                background-color: #22223A !important;
                border-color: rgba(255,140,0,0.30) !important;
            }

            /* Formularios */
            :is(.main, [data-testid="stMain"]) [data-testid="stForm"] {
                background-color: #22223A !important;
                border-color: rgba(255,140,0,0.30) !important;
            }

            /* Inputs de texto */
            :is(.main, [data-testid="stMain"]) input[type="text"],
            :is(.main, [data-testid="stMain"]) input[type="password"],
            :is(.main, [data-testid="stMain"]) input[type="number"],
            :is(.main, [data-testid="stMain"]) textarea {
                background-color: #2C2C4A !important;
                color: #FFFFFF !important;
                border-color: rgba(255,255,255,0.25) !important;
            }

            :is(.main, [data-testid="stMain"]) input::placeholder,
            :is(.main, [data-testid="stMain"]) textarea::placeholder {
                color: #7070A0 !important;
            }

            /* Expanders */
            :is(.main, [data-testid="stMain"]) [data-testid="stExpander"] {
                background-color: #22223A !important;
                border-color: rgba(255,255,255,0.12) !important;
            }

            :is(.main, [data-testid="stMain"]) [data-testid="stExpander"] summary p,
            :is(.main, [data-testid="stMain"]) [data-testid="stExpander"] summary span {
                color: #FFFFFF !important;
            }

            /* Info / Warning / Error / Success */
            :is(.main, [data-testid="stMain"]) [data-testid="stAlert"] {
                background-color: #22223A !important;
            }

            :is(.main, [data-testid="stMain"]) [data-testid="stAlert"] p,
            :is(.main, [data-testid="stMain"]) [data-testid="stAlert"] span {
                color: #FFFFFF !important;
            }

            /* DataFrames / Data Editor */
            :is(.main, [data-testid="stMain"], section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stDataFrameResizable"],
            :is(.main, [data-testid="stMain"], section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stDataFrame"],
            :is(.main, [data-testid="stMain"], section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stDataEditor"] {
                background-color: #22223A !important;
                border: 1px solid rgba(255,140,0,0.38) !important;
                border-radius: 10px !important;
                overflow: hidden !important;
                box-shadow: inset 0 0 0 1px rgba(255,140,0,0.16), 0 6px 16px rgba(0,0,0,0.28) !important;
            }

            :is(.main, [data-testid="stMain"], section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stDataFrame"],
            :is(.main, [data-testid="stMain"], section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stDataEditor"] {
                --gdg-accent-color: #FF9800;
                --gdg-accent-fg: #FFFFFF;
                --gdg-accent-light: rgba(255,152,0,0.22);
                --gdg-text-dark: #F0F0FF;
                --gdg-text-medium: #C9C9E8;
                --gdg-text-light: #9D9DC0;
                --gdg-text-header: #FFFFFF;
                --gdg-bg-cell: #22223A;
                --gdg-bg-cell-medium: #2C2C4A;
                --gdg-bg-header: #2C2C4A;
                --gdg-bg-header-hovered: #363658;
                --gdg-bg-header-has: #3D3D63;
                --gdg-bg-bubble: #2C2C4A;
                --gdg-bg-bubble-selected: #3D3D63;
                --gdg-bg-search-result: rgba(255,152,0,0.18);
                --gdg-border-color: rgba(255,255,255,0.14);
                --gdg-horizontal-border-color: rgba(255,255,255,0.11);
                --gdg-link-color: #FFB74D;
            }

            :is(.main, [data-testid="stMain"], section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stDataFrame"] canvas,
            :is(.main, [data-testid="stMain"], section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stDataEditor"] canvas {
                background-color: #22223A !important;
            }

            /* Tablas HTML */
            :is(.main, [data-testid="stMain"], section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) table {
                background-color: #22223A !important;
            }

            :is(.main, [data-testid="stMain"], section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) th {
                background-color: #2C2C4A !important;
                color: #FFFFFF !important;
                border-color: rgba(255,255,255,0.12) !important;
            }

            :is(.main, [data-testid="stMain"], section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) td {
                color: #F0F0FF !important;
                border-color: rgba(255,255,255,0.08) !important;
            }

            /* Separadores */
            :is(.main, [data-testid="stMain"]) hr {
                border-color: rgba(255,255,255,0.12) !important;
            }

            /* Selectbox / dropdown */
            :is(.main, [data-testid="stMain"]) [data-baseweb="select"] > div:first-child {
                background-color: #2C2C4A !important;
                border-color: rgba(255,255,255,0.25) !important;
                color: #FFFFFF !important;
            }

            /* Tabs */
            :is(.main, [data-testid="stMain"]) [data-baseweb="tab-panel"] {
                background-color: #22223A !important;
            }

            :is(.main, [data-testid="stMain"]) [data-baseweb="tab"] {
                color: #B0B0D0 !important;
            }

            :is(.main, [data-testid="stMain"]) [data-baseweb="tab"][aria-selected="true"] {
                color: #FF9800 !important;
            }

            /* Botones secundarios en el área principal (ej. "Ver mi Perfil", "Actualizar") */
            :is(.main, [data-testid="stMain"]) button[kind="secondary"],
            :is(.main, [data-testid="stMain"]) [data-testid="stBaseButton-secondary"] {
                background-color: #2C2C4A !important;
                color: #FFFFFF !important;
                border-color: rgba(255,255,255,0.22) !important;
            }

            :is(.main, [data-testid="stMain"]) button[kind="secondary"]:hover,
            :is(.main, [data-testid="stMain"]) [data-testid="stBaseButton-secondary"]:hover {
                background-color: #363658 !important;
                border-color: rgba(255,140,0,0.5) !important;
            }

            /* Tooltips */
            :is(.main, [data-testid="stMain"]) [data-testid="stTooltipIcon"] {
                color: #7070A0 !important;
            }

            /* Dialogs (st.dialog) montados fuera de .main */
            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) {
                background-color: #1A1A2A !important;
                color: #FFFFFF !important;
            }

            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) * {
                color: #FFFFFF !important;
            }

            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stWidgetLabel"] *,
            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stMetricLabel"] * {
                color: #D8D8F0 !important;
            }

            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stCaptionContainer"] *,
            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) small {
                color: #B0B0CC !important;
            }

            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stVerticalBlockBorderWrapper"],
            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stForm"] {
                background-color: #22223A !important;
                border-color: rgba(255,140,0,0.30) !important;
            }

            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) input[type="text"],
            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) input[type="password"],
            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) input[type="number"],
            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) textarea {
                background-color: #2C2C4A !important;
                color: #FFFFFF !important;
                border-color: rgba(255,255,255,0.25) !important;
            }

            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) input::placeholder,
            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) textarea::placeholder {
                color: #7070A0 !important;
            }

            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-baseweb="select"] > div:first-child {
                background-color: #2C2C4A !important;
                border-color: rgba(255,255,255,0.25) !important;
                color: #FFFFFF !important;
            }

            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) button[kind="secondary"],
            :is(section[data-testid="stDialog"], [data-testid="stDialog"], [role="dialog"]) [data-testid="stBaseButton-secondary"] {
                background-color: #2C2C4A !important;
                color: #FFFFFF !important;
                border-color: rgba(255,255,255,0.22) !important;
            }

            /* Header */
            [data-testid="stHeader"] {
                background: rgba(26,26,42,0.97) !important;
            }

            </style>
        """, unsafe_allow_html=True)


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
            max-width: 420px !important;
            margin: 0 auto !important;
        }

        /* ===== Centrar alertas de error ===== */
        [data-testid="stAlert"] {
            max-width: 420px !important;
            margin: 1rem auto !important;
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
            /* Fondo oscuro propio (no 'transparent'): garantiza contraste aunque el selector
               div[data-baseweb="input"] no coincida con el DOM de la versión de Streamlit desplegada.
               Evita el caso texto-blanco-sobre-fondo-blanco en Streamlit Cloud. */
            background-color: rgba(10, 5, 3, 0.9) !important;
            color: #FAFAFA !important;
            -webkit-text-fill-color: #FAFAFA !important; /* Fuerza color del texto incluso en autofill */
            border: none !important;
            padding: 0.4rem 0.8rem !important; 
            font-size: 14.5px !important; 
            min-height: 42px !important; 
            box-shadow: none !important;
        }
        .stApp input:focus {
            box-shadow: none !important;
            border: none !important;
            background-color: rgba(20, 10, 5, 0.95) !important;
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
        /* Ocultar forzosamente el icono default de flecha de Streamlit (expand_more/expand_less) que daña el botón */
        div[data-testid="stPopover"] button svg,
        div[data-testid="stPopover"] button [data-testid="stIcon"],
        div[data-testid="stPopover"] button span[data-testid="stIcon"],
        div[data-testid="stPopover"] button span[class*="material-"],
        div[data-testid="stPopover"] button span:not(:has([data-testid="stMarkdownContainer"])):not([data-testid="stMarkdownContainer"]):not([data-testid="stMarkdownContainer"] *) {
            display: none !important;
            visibility: hidden !important;
        }
        div[data-testid="stPopover"] button {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
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

    # En lugar de usar columnas con proporciones fijas que se aplastan en pantallas pequeñas,
    # usamos un contenedor centralizado a través de las propiedades max-width de CSS.
    with st.container():
        # Agrupamos título y logo DENTRO del formulario para que queden sobre la caja oscura
        with st.form("form_login", clear_on_submit=False):
            # Nuevo logo de la empresa (Agrandado en proporción)
            logo_path = os.path.join("app", "assets", "INVIAS_login_logo.png")
            if os.path.exists(logo_path):
                # Aumentamos el tamaño relativo
                c_logo1, c_logo2, c_logo3 = st.columns([1, 2.8, 1])
                with c_logo2:
                    st.image(logo_path, width="stretch")
            
            # Subir el título para acercarlo más al logo
            st.markdown("<h2 style='text-align: center; margin-top: -25px; margin-bottom: 0px;'>Gestiones correspondencia SRTI</h2>", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align: center; font-weight: normal; margin-top: 5px; color: #F0E6DD;'>Inicio de sesión</h4>", unsafe_allow_html=True)
            
            st.write("") # Espaciador
            
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            
            st.write("") # Espaciador
            
            # Reducir el ancho específico del botón usando columnas internas
            c_btn1, c_btn2, c_btn3 = st.columns([1, 3, 1])
            with c_btn2:
                enviar = st.form_submit_button("Ingresar", width="stretch", type="primary")

        if enviar:
            servicio = AuthService()
            sesion, error = servicio.iniciar_sesion(usuario.strip(), password)
            if error:
                st.error(error)
            else:
                iniciar_sesion(sesion)
                necesita, politica = PoliticaService().usuario_necesita_aceptar(sesion["id"])
                if necesita:
                    st.session_state["politica_pendiente"] = True
                    st.session_state["politica_vigente"] = politica
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


def pantalla_politica_datos() -> None:
    """Muestra la política de tratamiento de datos como pantalla bloqueante."""

    import os

    from app.core.recursos import imagen_b64

    politica = st.session_state.get("politica_vigente") or {}
    sesion = obtener_sesion()

    # Codificar el logo en base64 para embeberlo en el HTML
    logo_b64 = imagen_b64(os.path.join("app", "assets", "INVIAS_login_logo.png"))
            
    html_logo = f'<img src="data:image/png;base64,{logo_b64}" style="height: 45px; object-fit: contain;">' if logo_b64 else '<div style="font-size: 2.2rem; line-height:1;">🛡️</div>'

    # ── CSS: Estilos de la página bloqueante ────────────────
    st.markdown("""
    <style>
    /* Ocultar menú y barra superior */
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    
    /* ===== Fondo Principal idéntico al Login ===== */
    .stApp {
        background: linear-gradient(135deg, #E87A1E 0%, #A65012 50%, #3D1E0A 100%) !important;
        overflow: auto;
        z-index: 1;
    }

    /* ===== Geometrías Adaptables Superpuestas ===== */
    .stApp::before {
        content: ""; position: fixed; width: 650px; height: 650px;
        background: radial-gradient(circle, rgba(255, 230, 180, 0.25) 0%, transparent 60%);
        top: -150px; left: -150px; border-radius: 50%; z-index: 0;
        box-shadow: 800px 500px 0 150px rgba(255, 160, 40, 0.15);
        pointer-events: none;
    }

    .stApp::after {
        content: ""; position: fixed; width: 450px; height: 450px;
        background: linear-gradient(135deg, rgba(255, 140, 0, 0.4) 0%, rgba(200, 80, 10, 0.1) 100%);
        bottom: 5%; right: -100px; 
        border-radius: 60px; 
        transform: rotate(35deg);
        z-index: 0;
        box-shadow: -800px -300px 0 80px rgba(100, 45, 15, 0.3);
        pointer-events: none;
    }
    
    /* ── Contenedor principal (Tarjeta Blanca) ── */
    .block-container {
        max-width: 800px !important;
        background-color: #FFFFFF !important;
        border-radius: 16px !important;
        padding: 3rem !important;
        margin-top: 4vh !important;
        margin-bottom: 4vh !important;
        box-shadow: 0 15px 40px rgba(0,0,0,0.4) !important;
        position: relative;
        z-index: 10;
    }

    /* ── Scrollbar naranja ───────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: rgba(255,140,0,0.45);
        border-radius: 10px;
    }

    /* ── Checkbox ─────────────────────────────────────────── */
    [data-testid="stCheckbox"] label p {
        font-size: 14px !important;
        color: #000000 !important; /* Letra negra como se solicitó */
        font-weight: 600 !important;
    }

    /* ── Botón Aceptar — naranja institucional ───────────────────────────── */
    [data-testid="stBaseButton-primary"] {
        background: linear-gradient(90deg, #FF8C00 0%, #E67A00 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        min-height: 46px !important;
        box-shadow: 0 6px 20px rgba(255,140,0,0.35) !important;
        transition: all 0.25s ease !important;
    }
    [data-testid="stBaseButton-primary"]:hover:not([disabled]) {
        background: linear-gradient(90deg, #FF9D1A 0%, #F08000 100%) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 10px 28px rgba(255,140,0,0.50) !important;
    }
    [data-testid="stBaseButton-primary"]:disabled {
        background: rgba(200,200,200,0.55) !important;
        color: rgba(100,100,100,0.6) !important;
        box-shadow: none !important;
        transform: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Encabezado visual personalizado ──────────
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, #FF8C00 0%, #E67A00 60%, #CC6A00 100%);
        margin: -3rem -3rem 2rem -3rem;
        padding: 20px 28px 18px;
        border-radius: 16px 16px 0 0;
        display: flex;
        align-items: center;
        gap: 14px;
        box-shadow: 0 4px 15px rgba(255,140,0,0.2);
    ">
        {html_logo}
        <div>
            <div style="font-size:11px; font-weight:600; letter-spacing:2px;
                        color:rgba(255,255,255,0.85); text-transform:uppercase;">
                INVIAS &middot; SRTI
            </div>
            <div style="font-size:18px; font-weight:700; color:#FFFFFF; line-height:1.2;">
                Tratamiento de Datos Personales
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.write("")

    # ── Texto de la política (desde BD) ──────────────────────────────────────
    contenido_html = politica.get("contenido", "")
    version_num = politica.get("numero_version", "")
    if version_num:
        st.caption(f"Versión {version_num}")
    if contenido_html:
        st.markdown(contenido_html, unsafe_allow_html=True)
    else:
        st.warning("No se pudo cargar el contenido de la política.")

    st.divider()

    # ── Confirmación y botón ──────────────────────────────────────────────────
    confirmo = st.checkbox(
        "✅ He leído y comprendo la Política de Tratamiento de Datos Personales",
        key="politica_confirmo_lectura",
    )

    aceptar = st.button(
        "🔓 Aceptar y Continuar",
        key="politica_btn_aceptar",
        type="primary",
        disabled=not confirmo,
        use_container_width=True,
    )

    if aceptar and confirmo:
        try:
            headers = st.context.headers
            ip = (
                headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or headers.get("X-Real-IP", "")
                or "no_disponible"
            )
            user_agent = headers.get("User-Agent", "no_disponible")
        except Exception:
            ip, user_agent = "no_disponible", "no_disponible"

        try:
            PoliticaService().registrar_aceptacion(
                usuario_id=sesion["id"],
                politica=politica,
                ip=ip,
                user_agent=user_agent,
                sesion_id=sesion.get("id_sesion"),
                nombre_completo=sesion.get("nombre_completo"),
                email=sesion.get("email"),
            )
        except Exception as e:
            st.error(f"Error al registrar la aceptación: {e}")
            st.stop()

        st.session_state["politica_pendiente"] = False
        st.session_state.pop("politica_vigente", None)
        st.rerun()


def pantalla_dashboard() -> None:
    sesion = obtener_sesion()
    roles = sesion.get("roles", [])
    es_admin = any(rol in {"admin", "administrador"} for rol in roles)
    
    # Obtener métricas reales (siempre personales según lo solicitado)
    from app.core.cache_datos import metricas_inicio
    metricas = metricas_inicio(sesion.get("id"))

    # 2. Título "Inicio" decorado
    mostrar_titulo_decorado("Inicio")

    # 3. Dividir la página en 2 columnas (Izquierda y Derecha)
    col_left, col_right = st.columns([2, 1], gap="large")

    with col_left:
        st.subheader(f"Bienvenido(a), {sesion.get('nombre_completo') or sesion['usuario']}.")
        
        st.markdown(
            "<div style='color: #6D4C41; font-weight: bold; margin-bottom: 10px; font-size: 15px;'>"
            "Herramienta interna de la Subdirección SRTI para la gestión de correspondencia desde 2026, administración de usuarios y automatización de formatos para contratistas."
            "</div>", unsafe_allow_html=True
        )
        st.write("")

        # Recuadro "Mi correspondencia"
        with st.container(border=True):
            st.markdown("""
            <span id='mi-corr-box'></span>
            <h3 style='color: #FF8C00; margin-top: 0; padding-top: 0; position: relative; z-index: 2;'>Mi correspondencia</h3>
            <style>
                div[data-testid="stVerticalBlockBorderWrapper"]:has(#mi-corr-box) {
                    background: 
                        radial-gradient(circle at 10% 20%, rgba(255, 140, 0, 0.04) 0%, transparent 40%),
                        radial-gradient(circle at 90% 80%, rgba(255, 152, 0, 0.04) 0%, transparent 40%),
                        linear-gradient(135deg, rgba(255,140,0,0.015) 0%, rgba(255,140,0,0.005) 100%) !important;
                    border: 1px solid rgba(255, 140, 0, 0.25) !important;
                    position: relative;
                    overflow: hidden;
                }
                
                div[data-testid="stVerticalBlockBorderWrapper"]:has(#mi-corr-box)::before {
                    content: "";
                    position: absolute;
                    top: -40px;
                    right: -20px;
                    width: 120px;
                    height: 120px;
                    background: linear-gradient(135deg, rgba(255,140,0,0.05), transparent);
                    clip-path: polygon(25% 6%, 75% 6%, 100% 50%, 75% 94%, 25% 94%, 0% 50%);
                    transform: rotate(15deg);
                    pointer-events: none;
                    z-index: 0;
                }
                
                div[data-testid="stVerticalBlockBorderWrapper"]:has(#mi-corr-box)::after {
                    content: "";
                    position: absolute;
                    bottom: -30px;
                    left: -20px;
                    width: 90px;
                    height: 90px;
                    background: linear-gradient(135deg, rgba(255,140,0,0.04), transparent);
                    clip-path: polygon(50% 0%, 100% 38%, 82% 100%, 18% 100%, 0% 38%);
                    transform: rotate(-10deg);
                    pointer-events: none;
                    z-index: 0;
                }
                
                /* Ensure content stays above background shapes */
                div[data-testid="stVerticalBlockBorderWrapper"]:has(#mi-corr-box) > div {
                    position: relative;
                    z-index: 2;
                }
            </style>
            """, unsafe_allow_html=True)
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
        st.subheader("🎯 Acciones rápidas")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📂 Ir a Correspondencia", width="stretch", type="primary"):
                st.switch_page("pages/2_correspondencia.py")
        with c2:
            # CSS robusto para el botón verde sin romper la alineación vertical
            st.markdown("""
            <style>
                /* Ocultar el contenedor que Streamlit crea para este bloque st.markdown */
                div.element-container:has(style#btn-style) {
                    display: none !important;
                    margin: 0 !important;
                    padding: 0 !important;
                    height: 0 !important;
                }
                
                /* Aplicar estilo ÚNICAMENTE al botón adyacente para no afectar los tooltips */
                div.element-container:has(style#btn-style) + div.element-container button {
                    background-color: #28a745 !important;
                    color: white !important;
                    border-color: #28a745 !important;
                }
                div.element-container:has(style#btn-style) + div.element-container button:hover {
                    background-color: #218838 !important;
                    border-color: #1e7e34 !important;
                }
                div.element-container:has(style#btn-style) + div.element-container button p {
                    color: white !important;
                }
            </style>
            <style id="btn-style"></style>
            """, unsafe_allow_html=True)
            
            if st.button("👤 Ver mi Perfil", width="stretch"):
                st.switch_page("pages/2_mi_perfil.py")

    with col_right:
        # Título decorado "Anuncios"
        st.markdown("""
        <div style="background: linear-gradient(135deg, #FF8C00, #FF9800); color: white; padding: 12px 15px; border-radius: 8px; margin-bottom: 15px;">
            <h3 style="margin: 0; font-size: 18px; display: flex; align-items: center; gap: 8px;">
                📢 Anuncios
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background-color: #e8f4fd; padding: 16px; border-radius: 8px; border-left: 5px solid #2b8cbe; margin-bottom: 15px;">
            <span style="color: #1c5e82;">⚠️ Se está actualizando la sección de contratos para la gestión y descarga de formatos. Por favor revisar en 'Mi perfil' que los datos personales y de contrato <span style="font-weight: bold; text-decoration: underline;">(en caso de contratistas)</span> estén al día y correctamente ingresados. ⚠️</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        
        # Título decorado "Recomendaciones"
        st.markdown("""
        <div style="background: linear-gradient(135deg, #FF8C00, #FF9800); color: white; padding: 12px 15px; border-radius: 8px; margin-bottom: 15px;">
            <h3 style="margin: 0; font-size: 18px; display: flex; align-items: center; gap: 8px;">
                💡 Recomendaciones
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        - La correspondencia atrasada del trámite se calculará de la siguiente forma: **10 días hábiles desde la fecha de radicado sin contar fines de semana ni festivos colombianos.**
        - Se recomienda utilizar el filtro por estado <span style="color: #FF8C00; font-weight: bold;">"En trámite"</span>.
        - Los formatos generados por el sistema para los contratistas solo serán funcionales y válidos si el usuario diligencia todos los datos personales y de contrato en <span style="color: #FF8C00; font-weight: bold;">Mi perfil</span>.
        - Cualquier correspondencia mal asignada o que no pertenezca al usuario deberá ser reasignada a "Javier Alexander Delgado" en la ventana de reasignación de la correspondencia.
        """, unsafe_allow_html=True)

        if es_admin:
            st.write("")
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
    aplicar_tema()

    # Mostrar pantalla de política si aún no fue aceptado en esta sesión
    if st.session_state.get("politica_pendiente", False):
        pantalla_politica_datos()
        st.stop()

    # Definición de páginas
    page_dashboard = st.Page(pantalla_dashboard, title="Inicio", icon="🏠", default=True)
    page_perfil = st.Page("pages/2_mi_perfil.py", title="Mi Perfil", icon="👤", url_path="mi_perfil")
    page_correspondencia = st.Page("pages/2_correspondencia.py", title="Correspondencia", icon="📬")
    page_instructivos = st.Page("pages/3_instructivos.py", title="Instructivos", icon="📚")
    page_grupo_despacho = st.Page("pages/12_grupo_despacho.py", title="Despacho", icon="🏛️")
    page_grupo_permisos = st.Page("pages/11_permisos_suit.py", title="SUIT", icon="🔑")
    page_grupo_normativa = st.Page("pages/13_grupo_normativa_tecnica.py", title="Normativa Técnica", icon="📜")
    page_grupo_innovacion = st.Page("pages/14_grupo_innovacion_tecnica.py", title="Innovación Técnica", icon="💡")
    page_gestores_permisos = st.Page("pages/15_gestores_permisos.py", title="Gestores Perm.", icon="🛠️")

    permisos_sesion = sesion.get("permisos", [])

    # Páginas de administración
    admin_pages = []
    if "usuario.ver" in permisos_sesion:
        admin_pages.append(st.Page("pages/1_admin_usuarios.py", title="Usuarios", icon="👥"))
    if "rol.ver" in permisos_sesion:
        admin_pages.append(st.Page("pages/3_admin_roles.py", title="Roles", icon="🔐"))
    if "dashboard.ver" in permisos_sesion:
        admin_pages.append(st.Page("pages/5_dashboard.py", title="Dashboard", icon="📊"))
    if "reporte.ver" in permisos_sesion:
        admin_pages.append(st.Page("pages/4_reportes.py", title="Reportes y Evidencias", icon="📄"))
    # Páginas de Gestión de contratos / Formatos
    _perms_firma = {
        "certificacion.firmar_corr", "certificacion.firmar_gd", "certificacion.firmar_secop",
        "certificacion.firmar_financiera", "certificacion.firmar_abogado", "certificacion.firmar_jefe",
    }
    es_admin_main = any(r in {"admin", "administrador"} for r in sesion.get("roles", []))
    es_firmante_o_supervisor = bool(_perms_firma & set(permisos_sesion)) or es_admin_main or "certificacion.aprobar" in permisos_sesion

    if es_admin_main:
        admin_pages.append(st.Page("pages/10_admin_parametros.py", title="Parámetros", icon="⚙️"))

    supervision_pages = [
        st.Page("pages/6_certificaciones.py", title="Formatos de contrato", icon="📄"),
    ]
    if es_firmante_o_supervisor:
        supervision_pages.append(st.Page("pages/9_firmantes_certif.py", title="Sup. Formatos", icon="✍️"))
    if "certificacion.aprobar" in permisos_sesion:
        supervision_pages.append(st.Page("pages/7_admin_certif.py", title="Seguimiento - Formatos", icon="📊"))

    # Cada grupo de trabajo es su propia categoría de primer nivel. Es visible si el
    # usuario es admin, si su grupo_trabajo coincide, o si tiene el permiso grupo.X.ver
    # asignado (por rol o permiso_extra) independientemente de su grupo_trabajo.
    categorias_por_grupo = {
        "despacho": ("Despacho", page_grupo_despacho, "grupo.despacho.ver"),
        "permisos": ("Permisos", page_grupo_permisos, "grupo.permisos.ver"),
        "normativa_tecnica": ("Normativa Técnica", page_grupo_normativa, "grupo.normativa_tecnica.ver"),
        "innovacion_tecnica": ("Innovación Técnica", page_grupo_innovacion, "grupo.innovacion_tecnica.ver"),
    }
    grupo_usuario = sesion.get("grupo_trabajo") or ""
    if es_admin_main:
        grupos_visibles = list(categorias_por_grupo.keys())
    else:
        grupos_visibles = [
            clave for clave, (_, _, permiso_ver) in categorias_por_grupo.items()
            if clave == grupo_usuario or permiso_ver in permisos_sesion
        ]

    menu_dict = {
        "Principal": [page_dashboard, page_correspondencia, page_perfil, page_instructivos],
        "Gestión contratos": supervision_pages,
    }
    for clave in ["despacho", "permisos", "normativa_tecnica", "innovacion_tecnica"]:
        if clave in grupos_visibles:
            nombre_categoria, pagina, _ = categorias_por_grupo[clave]
            menu_dict[nombre_categoria] = [pagina]

    # "Gestores Perm." es una segunda página dentro de la categoría Permisos, visible
    # solo para admin o para coordinador/líder del propio grupo de trabajo Permisos.
    es_lider_o_coordinador = any(r in {"coordinador", "lider"} for r in sesion.get("roles", []))
    if "Permisos" in menu_dict and (es_admin_main or (es_lider_o_coordinador and grupo_usuario == "permisos")):
        menu_dict["Permisos"].append(page_gestores_permisos)

    if admin_pages:
        menu_dict["Administración"] = admin_pages
        
    pg = st.navigation(menu_dict)
    
    # Personalización del sidebar
    st.sidebar.title("Menú")
    
    with st.sidebar:
        # Tarjeta de Perfil de Usuario Premium (HTML puro para garantizar el diseño exacto)
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
            
        roles_html = ""
        for r in roles_lista:
            roles_html += f"<span style='background-color: rgba(0, 128, 255, 0.15); color: #0080ff; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; font-weight: bold; display: inline-block;'>{r.title()}</span>"
            
        email_html = f"<div style='color: gray; font-size: 0.75em; word-break: break-all; margin-top: 2px;'>{email}</div>" if email else ""
        
        html_tarjeta = f"""
        <div style="display: flex; flex-direction: column; gap: 14px; box-sizing: border-box; width: 100%;">
            <div style="display: flex; align-items: center; gap: 14px;">
                <div style="font-size: 2.6em; display: flex; align-items: center; justify-content: center; min-width: 50px;">{avatar}</div>
                <div style="display: flex; flex-direction: column; justify-content: center; overflow: hidden; line-height: 1.3;">
                    <div style="font-weight: 600; color: #F4F4F4; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{nombre}</div>
                    <div style="color: #A0A0A0; font-size: 13px;">@{username}</div>
                    {email_html}
                </div>
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                {roles_html}
            </div>
        </div>
        """
        # Tarjeta = contenedor con borde (clase st-key-perfil_card) para que el
        # enlace "Ver mi perfil" quede DENTRO de la caja, con navegación cliente
        # (st.page_link no recarga la página, así no se pierde la sesión).
        with st.container(key="perfil_card"):
            st.markdown(html_tarjeta, unsafe_allow_html=True)
            st.page_link("pages/2_mi_perfil.py", label="Ver mi perfil", icon="👤", use_container_width=False)
        if st.button("🚪 Cerrar sesión", key="logout_btn", width="stretch"):
            logout()

        st.divider()
        st.toggle("🌙 Modo oscuro", key="dark_mode")

        from app.core.recursos import imagen_b64
        logo_b64 = imagen_b64(os.path.join("app", "assets", "INVIAS_login_logo.png"))
        if logo_b64:
            st.markdown(
                f'<div class="logo-static-container">'
                f'<img src="data:image/png;base64,{logo_b64}" alt="INVIAS Logo" />'
                f'</div>',
                unsafe_allow_html=True
            )
            
    # Limpiar estados de diálogos si se cambia de página
    current_page_title = pg.title
    last_page = st.session_state.get("_last_active_page")
    if last_page and last_page != current_page_title:
        st.session_state.pop("_confirmar_firma", None)
    st.session_state["_last_active_page"] = current_page_title

    pg.run()

