import streamlit as st
from pathlib import Path

# URLs for resources
PDF_URL = "https://invias-my.sharepoint.com/:b:/g/personal/srti_invias_gov_co/IQCYL5xtar5uRYKiE2Ie67LqAVG7bs4PylUKHShk8DGk2d4?e=dTd9cH"
VIDEO_URL = "https://invias-my.sharepoint.com/:v:/g/personal/srti_invias_gov_co/IQD38W4JO-ypQavnQIaKu7qZAXyv1x_rPNy0FweZtT4DWLQ?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=Tl6SME"

def get_drive_embed(url: str) -> str:
    """Convert a normal Google Drive share link to an embed URL for preview."""
    import re
    m = re.search(r"/d/([^/]+)/", url)
    file_id = m.group(1) if m else ""
    return f"https://drive.google.com/file/d/{file_id}/preview"

# Track which preview is currently active
if "preview" not in st.session_state:
    st.session_state.preview = None  # values: "pdf", "video", None

st.set_page_config(page_title="Instructivos", page_icon="app/assets/invias_fav_ico_3.ico", layout="wide")

st.title("📚 Instructivos")
st.caption("Recursos de capacitación y documentación oficial.")

# Layout: left side shows preview, right side holds buttons
col_preview, col_controls = st.columns([2, 1])

with col_controls:
    st.subheader("Acciones")
    if st.button("📄 Instructivo Matriz de correspondencia SRTI", key="btn_pdf"):
        st.session_state.preview = "pdf"
    if st.button("▶️ Capacitación Matriz de correspondencia SRTI", key="btn_video"):
        st.session_state.preview = "video"
    

with col_preview:
    if st.session_state.preview == "pdf":
        embed_url = get_drive_embed(PDF_URL)
        st.subheader("Vista previa del PDF")
        st.components.v1.html(
            f"<iframe src='{embed_url}' width='100%' height='800px' style='border:none;'></iframe>",
            height=800,
        )
    elif st.session_state.preview == "video":
        st.subheader("Capacitación en video")
        st.video(VIDEO_URL)
    else:
        st.info("Selecciona una opción del panel derecho para visualizar el recurso.")

# Small CSS transition for smoother switches
st.markdown(
    """
    <style>
    .stApp .css-1v0mbdj {{
        transition: all 0.4s ease-in-out;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)
