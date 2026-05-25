import streamlit as st

PDF_URL = "https://invias-my.sharepoint.com/:b:/g/personal/srti_invias_gov_co/IQCYL5xtar5uRYKiE2Ie67LqAVG7bs4PylUKHShk8DGk2d4?e=dTd9cH"

VIDEO_URL = "https://invias-my.sharepoint.com/:v:/g/personal/srti_invias_gov_co/IQD38W4JO-ypQavnQIaKu7qZAXyv1x_rPNy0FweZtT4DWLQ?e=Tl6SME"

if "preview" not in st.session_state:
    st.session_state.preview = None

st.set_page_config(
    page_title="Instructivos",
    page_icon="app/assets/invias_fav_ico_3.ico",
    layout="wide"
)

st.title("📚 Instructivos")
st.caption("Recursos de capacitación y documentación oficial.")

col_preview, col_controls = st.columns([2, 1])

with col_controls:

    st.subheader("Acciones")

    if st.button("📄 Instructivo Matriz de correspondencia SRTI"):
        st.session_state.preview = "pdf"

    if st.button("▶️ Capacitación Matriz de correspondencia SRTI"):
        st.session_state.preview = "video"

with col_preview:

    if st.session_state.preview == "pdf":

        st.subheader("Vista previa del PDF")

        st.components.v1.html(
            f"""
            <iframe
                src="{PDF_URL}"
                width="100%"
                height="800px"
                style="border:none;border-radius:10px;">
            </iframe>
            """,
            height=800,
        )

        st.link_button("🔗 Abrir PDF", PDF_URL)

    elif st.session_state.preview == "video":

        st.subheader("Capacitación en video")

        st.video(VIDEO_URL)

        st.link_button("🔗 Abrir video", VIDEO_URL)

    else:
        st.info("Selecciona una opción del panel derecho para visualizar el recurso.")

st.markdown(
    """
    <style>
    iframe {
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)