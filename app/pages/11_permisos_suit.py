import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

"""Página del sistema SUIT — cargue de PQRD, totalmente separado de Correspondencia.

Por ahora es solo la interfaz (sin persistencia): las colecciones de SUIT
todavía no existen en la base de datos.
"""

from datetime import datetime, timezone

import streamlit as st
from app.core.catalogos import PERMISOS_SUIT_CARGUE
from app.core.ui_titulos import mostrar_titulo_decorado
from app.core.sesion import obtener_sesion
from app.core.zona_horaria import utc_a_bogota

st.set_page_config(
    page_title="SUIT",
    page_icon="app/assets/invias_fav_ico_3.ico",
    layout="wide",
)


_TRIMESTRES = {
    "1": ("1° Trimestre", ["Enero", "Febrero", "Marzo"]),
    "2": ("2° Trimestre", ["Abril", "Mayo", "Junio"]),
    "3": ("3° Trimestre", ["Julio", "Agosto", "Septiembre"]),
    "4": ("4° Trimestre", ["Octubre", "Noviembre", "Diciembre"]),
}

# (id_campo, etiqueta) — sección "resueltas", texto en color normal.
_CAMPOS_RESUELTAS = [
    ("solicitudes_linea", "Número de solicitudes resueltas en línea (Respuestas a las solicitudes del "
                           "trámite tanto favorables como desfavorables en las cuales se usaron medios "
                           "electrónicos para su envío)"),
    ("solicitudes_presencial", "Número de solicitudes resueltas de forma presencial"),
    ("pqrd_recibidas", "Número de PQRD recibidas"),
]

# (id_campo, etiqueta) — sección PQRD, texto en azul oscuro.
_CAMPOS_PQRD = [
    ("otras_pqrd", "Número de otras PQRD relacionadas con el trámite"),
    ("quejas", "Quejas recibidas (PQRD)"),
    ("reclamos", "Reclamos recibidos (PQRD)"),
    ("denuncias", "Denuncias recibidas (PQRD)"),
]


def _render_formulario_cargue(clave_permiso: str) -> None:
    """Formulario de cargue idéntico para los 7 permisos SUIT. Solo interfaz: no persiste nada."""
    st.caption("Aún no existen las colecciones de SUIT en la base de datos: los datos ingresados aquí no se guardan.")

    anio_actual = utc_a_bogota(datetime.now(timezone.utc)).year

    col_anio, col_trim, col_mes = st.columns(3)
    with col_anio:
        st.selectbox(
            "Año",
            options=list(range(anio_actual, anio_actual - 5, -1)),
            key=f"anio_{clave_permiso}",
        )
    with col_trim:
        trimestre = st.selectbox(
            "Trimestre a cargar",
            options=list(_TRIMESTRES.keys()),
            format_func=lambda k: _TRIMESTRES[k][0],
            key=f"trimestre_{clave_permiso}",
        )
    with col_mes:
        st.selectbox(
            "Mes",
            options=_TRIMESTRES[trimestre][1],
            key=f"mes_{clave_permiso}_{trimestre}",
        )

    for campo_id, etiqueta in _CAMPOS_RESUELTAS:
        col_lbl, col_val = st.columns([3, 1])
        with col_lbl:
            st.markdown(etiqueta)
        with col_val:
            st.number_input(
                etiqueta, min_value=0, value=0, step=1, format="%d",
                key=f"{clave_permiso}_{campo_id}", label_visibility="collapsed",
            )

    st.divider()

    for campo_id, etiqueta in _CAMPOS_PQRD:
        col_lbl, col_val = st.columns([3, 1])
        with col_lbl:
            st.markdown(f"<span style='color:#0B3D91;font-weight:600;'>{etiqueta}</span>", unsafe_allow_html=True)
        with col_val:
            st.number_input(
                etiqueta, min_value=0, value=0, step=1, format="%d",
                key=f"{clave_permiso}_{campo_id}", label_visibility="collapsed",
            )

    if st.button("💾 Guardar", type="primary", use_container_width=True, key=f"guardar_{clave_permiso}"):
        st.warning("Esta función aún no está disponible: todavía no existen las colecciones de SUIT en la base de datos.")


def _render_cargue_suit(sesion: dict) -> None:
    mostrar_titulo_decorado("Cargue SUIT Permiso")
    st.caption("Selecciona el tipo de permiso que deseas cargar.")

    es_admin = any(r in {"admin", "administrador"} for r in sesion.get("roles", []))
    permisos_sesion = sesion.get("permisos", [])
    permisos_visibles = (
        PERMISOS_SUIT_CARGUE if es_admin
        else [p for p in PERMISOS_SUIT_CARGUE if p["clave"] in permisos_sesion]
    )

    if not permisos_visibles:
        st.info(
            "No tienes ningún permiso de cargue SUIT asignado. Solicita acceso a un "
            "administrador o a un coordinador/líder del grupo de Permisos."
        )
        return

    col_sub_menu, col_sub_contenido = st.columns([1, 2], gap="large")

    with col_sub_menu:
        with st.container(border=True):
            for i, permiso in enumerate(permisos_visibles, start=1):
                if st.button(f"{i}- {permiso['label_corto']}", type="primary", use_container_width=True, key=f"btn_permiso_suit_{permiso['clave']}"):
                    st.session_state["clave_permiso_suit_activo"] = permiso["clave"]
                    st.rerun()

    with col_sub_contenido:
        clave_activa = st.session_state.get("clave_permiso_suit_activo")
        permiso_activo = next((p for p in permisos_visibles if p["clave"] == clave_activa), None)
        if permiso_activo:
            mostrar_titulo_decorado(permiso_activo["nombre_completo"])
            _render_formulario_cargue(permiso_activo["clave"])
        else:
            st.info("👈 Selecciona un tipo de permiso en el menú para visualizar su contenido.")


def _render_seguimiento() -> None:
    mostrar_titulo_decorado("Seguimiento SUIT")
    st.info("El módulo de Seguimiento SUIT se encuentra actualmente en desarrollo.")


def _render_reporte() -> None:
    mostrar_titulo_decorado("Reporte SUIT")
    st.info("El módulo de Reporte SUIT se encuentra actualmente en desarrollo.")


def render(sesion=None) -> None:
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    mostrar_titulo_decorado("SUIT")
    st.caption("Sistema de cargue de PQRD, independiente del sistema de Correspondencia.")

    col_menu, col_contenido = st.columns([1, 3], gap="large")

    with col_menu:
        with st.container(border=True):
            st.markdown("### SUIT")
            st.caption("El Sistema Unificado de Información de Trámites – SUIT – 2026")
            if st.button("1- Cargue SUIT", type="primary", use_container_width=True):
                st.session_state["tab_suit_activo"] = "cargue"
                st.rerun()
            if st.button("2- Seguimiento", type="primary", use_container_width=True):
                st.session_state["tab_suit_activo"] = "seguimiento"
                st.rerun()
            if st.button("3- Reporte", type="primary", use_container_width=True):
                st.session_state["tab_suit_activo"] = "reporte"
                st.rerun()

    with col_contenido:
        tab_activa = st.session_state.get("tab_suit_activo")
        if tab_activa == "cargue":
            _render_cargue_suit(sesion)
        elif tab_activa == "seguimiento":
            _render_seguimiento()
        elif tab_activa == "reporte":
            _render_reporte()
        else:
            st.info("👈 Selecciona una opción del menú de la izquierda para visualizar su contenido.")


# Punto de entrada cuando Streamlit carga la página directamente
render(obtener_sesion())
