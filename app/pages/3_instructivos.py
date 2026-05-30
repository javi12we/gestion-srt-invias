import streamlit as st

from app.config import configuracion

st.set_page_config(
    page_title="Instructivos",
    page_icon="app/assets/invias_fav_ico_3.ico",
    layout="wide"
)

if "recurso_activo" not in st.session_state:
    st.session_state.recurso_activo = None


def _embed_url(share_url: str) -> str:
    """Convierte URL /view de Google Drive a /preview para embedding en iframe."""
    return share_url.split("?")[0].replace("/view", "/preview")


RECURSOS = {
    "pdf": {
        "label": "📄 Instructivo Matriz de correspondencia SRTI",
        "share_url": configuracion.instructivo_pdf_url,
        "embed_height": 850,
    },
    "video": {
        "label": "▶️ Capacitación Matriz de correspondencia SRTI",
        "share_url": configuracion.instructivo_video_url,
        "embed_height": 540,
    },
}

st.title("📚 Instructivos")
st.caption("Recursos de capacitación y documentación oficial.")

col_controles, col_vista = st.columns([1, 3])

with col_controles:
    st.subheader("Recursos")

    for key, recurso in RECURSOS.items():
        if st.button(recurso["label"], width="stretch", key=f"btn_{key}"):
            st.session_state.recurso_activo = key

    if st.session_state.recurso_activo is not None:
        st.divider()
        if st.button("✖ Cerrar vista previa", width="stretch"):
            st.session_state.recurso_activo = None

with col_vista:
    activo = st.session_state.recurso_activo

    if activo is None:
        st.info("Selecciona un recurso del panel izquierdo para visualizarlo aquí.")

    else:
        recurso = RECURSOS[activo]
        share_url = recurso["share_url"]

        st.subheader(recurso["label"])

        if not share_url:
            st.warning("URL no configurada. Agrega la variable correspondiente en el archivo `.env`.")
        else:
            embed_url = _embed_url(share_url)
            st.components.v1.html(
                f"""
                <iframe
                    src="{embed_url}"
                    width="100%"
                    height="{recurso['embed_height']}px"
                    style="border:none; border-radius:8px;"
                    allowfullscreen>
                </iframe>
                """,
                height=recurso["embed_height"] + 10,
            )
            st.link_button("🔗 Abrir en Google Drive", share_url)
