import datetime
import streamlit as st

from app.core.autorizacion import validar_permiso, ValidacionAutorizacion
from app.core.sesion import obtener_sesion
from app.services.pdf_report_service import PDFReportService
from app.services.excel_report_service import ExcelReportService

sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()

try:
    validar_permiso(sesion.get("permisos", []), "reporte.ver")
except ValidacionAutorizacion:
    st.error("No tienes permisos para ver este módulo.")
    st.stop()


# --- Encabezado ---
col_title, col_btn = st.columns([5, 1])
with col_title:
    st.title("📄 Reportes y Evidencias")
    st.markdown("Generación de reportes de correspondencia oficiales y evidencias estructuradas para el sistema KAWAK.")
with col_btn:
    st.write("") # Espaciador para alineación
    st.write("") 
    if st.button("🔄 Limpiar", width="stretch", key="refresh_reportes"):
        st.session_state.pop("show_pdf_downloads", None)
        st.session_state.pop("show_excel_download", None)
        st.session_state.pop("excel_kawak_buffer", None)
        st.session_state.pop("excel_kawak_name", None)
        st.session_state.pop("pdf_pqrd", None)
        st.session_state.pop("pdf_conglomerado", None)
        st.session_state.pop("pdf_total", None)
        st.session_state.pop("pdf_preview_data", None)
        st.session_state.pop("pdf_preview_title", None)
        st.rerun()

st.divider()

# --- Interfaz en Cards para Administrador ---
col_c1, col_c2 = st.columns(2)

with col_c1:
    with st.container(border=True):
        st.markdown("### 📗 Evidencia KAWAK (Excel)")
        st.write(
            "Genera el libro de Excel consolidado que cumple con los campos exactos, "
            "estructuras y codificaciones solicitadas por la plataforma KAWAK para la carga "
            "de evidencias de gestión de correspondencia."
        )
        st.write("") # Relleno visual
        
        if st.button("Generar Excel KAWAK", width="stretch", key="gen_excel", type="primary"):
            with st.spinner("Procesando datos y estructurando hoja Excel..."):
                try:
                    excel_service = ExcelReportService()
                    buffer, nombre = excel_service.generar_excel_kawak()
                    st.session_state["excel_kawak_buffer"] = buffer
                    st.session_state["excel_kawak_name"] = nombre
                    st.session_state["show_excel_download"] = True
                    st.success("¡Excel generado con éxito!")
                except Exception as e:
                    st.error(f"Error generando Excel: {e}")
        
        if st.session_state.get("show_excel_download", False):
            st.write("")
            st.download_button(
                label="⬇️ Descargar Evidencia KAWAK (Excel)",
                data=st.session_state.get("excel_kawak_buffer", b""),
                file_name=st.session_state.get("excel_kawak_name", "Reporte_KAWAK.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch"
            )

with col_c2:
    with st.container(border=True):
        st.markdown("### 📄 Reportes Correspondencia PDF")
        st.write(
            "Genera y compila los documentos en PDF oficiales y estructurados listos para firma "
            "o archivo: el Reporte de PQRD, el Reporte Conglomerado general y el Reporte Total sin trámite."
        )
        st.write("") # Relleno visual
        
        if st.button("Generar Reportes PDF", width="stretch", key="gen_pdf", type="primary"):
            with st.spinner("Generando documentos PDF..."):
                try:
                    pdf_service = PDFReportService()
                    st.session_state["pdf_pqrd"] = pdf_service.generar_pdf_pqrd()
                    st.session_state["pdf_conglomerado"] = pdf_service.generar_pdf_conglomerado()
                    st.session_state["pdf_total"] = pdf_service.generar_pdf_total_sin_tramite()
                    st.session_state["show_pdf_downloads"] = True
                    st.success("¡Documentos PDF generados con éxito!")
                except Exception as e:
                    st.error(f"Error generando PDF: {e}")
        
        if st.session_state.get("show_pdf_downloads", False):
            st.write("")
            fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d")
            
            # --- Reporte PQRD ---
            st.markdown("##### 📌 Reporte PQRD")
            col_pqrd_preview, col_pqrd_dl = st.columns([1, 1])
            with col_pqrd_preview:
                if st.button("🔍 Previsualizar PQRD", width="stretch", key="prev_pqrd"):
                    st.session_state["pdf_preview_data"] = st.session_state.get("pdf_pqrd").getvalue() if hasattr(st.session_state.get("pdf_pqrd"), "getvalue") else st.session_state.get("pdf_pqrd", b"")
                    st.session_state["pdf_preview_title"] = "Reporte VUVR PQRD"
                    st.rerun()
            with col_pqrd_dl:
                st.download_button(
                    label="⬇️ Descargar PDF",
                    data=st.session_state.get("pdf_pqrd", b""),
                    file_name=f"Reporte_VUVR_PQRD_{fecha_hoy}.pdf",
                    mime="application/pdf",
                    width="stretch",
                    key="dl_pqrd"
                )
            
            # --- Reporte Conglomerado ---
            st.markdown("##### 📌 Reporte Conglomerado")
            col_cong_preview, col_cong_dl = st.columns([1, 1])
            with col_cong_preview:
                if st.button("🔍 Previsualizar Conglomerado", width="stretch", key="prev_cong"):
                    st.session_state["pdf_preview_data"] = st.session_state.get("pdf_conglomerado").getvalue() if hasattr(st.session_state.get("pdf_conglomerado"), "getvalue") else st.session_state.get("pdf_conglomerado", b"")
                    st.session_state["pdf_preview_title"] = "Reporte Conglomerado SRTI"
                    st.rerun()
            with col_cong_dl:
                st.download_button(
                    label="⬇️ Descargar PDF",
                    data=st.session_state.get("pdf_conglomerado", b""),
                    file_name=f"Reporte_Correspondencia_{fecha_hoy}.pdf",
                    mime="application/pdf",
                    width="stretch",
                    key="dl_cong"
                )
            
            # --- Reporte Total sin tramite ---
            st.markdown("##### 📌 Reporte Total sin trámite")
            col_total_preview, col_total_dl = st.columns([1, 1])
            with col_total_preview:
                if st.button("🔍 Previsualizar Total", width="stretch", key="prev_total"):
                    st.session_state["pdf_preview_data"] = st.session_state.get("pdf_total").getvalue() if hasattr(st.session_state.get("pdf_total"), "getvalue") else st.session_state.get("pdf_total", b"")
                    st.session_state["pdf_preview_title"] = "Reporte Total sin trámite"
                    st.rerun()
            with col_total_dl:
                st.download_button(
                    label="⬇️ Descargar PDF",
                    data=st.session_state.get("pdf_total", b""),
                    file_name=f"Reporte_Total_Correspondencia_{fecha_hoy}.pdf",
                    mime="application/pdf",
                    width="stretch",
                    key="dl_total"
                )

# --- Visualizador de PDF Incrustado ---
if st.session_state.get("pdf_preview_data") is not None:
    st.write("")
    st.divider()
    st.markdown(f"### 🔍 Previsualización: {st.session_state.get('pdf_preview_title')}")
    
    from streamlit_pdf_viewer import pdf_viewer
    try:
        pdf_bytes = st.session_state.get("pdf_preview_data")
        
        col_view, col_close = st.columns([5, 1])
        with col_view:
            st.info("💡 **Consejo:** El visor de PDF ahora utiliza una renderización nativa compatible con todos los navegadores, incluido Chrome en producción.")
        with col_close:
            st.write("")
            if st.button("❌ Cerrar Vista", width="stretch", key="close_preview"):
                st.session_state["pdf_preview_data"] = None
                st.session_state["pdf_preview_title"] = ""
                st.rerun()
                
        # Mostrar el visor
        pdf_viewer(input=pdf_bytes, width=800, height=600)
    except Exception as e:
        st.error(f"No se pudo renderizar la vista previa del PDF: {e}")

st.write("")
st.caption("💡 **Consejo:** Una vez descargados los archivos, puedes pulsar el botón 'Limpiar' en la parte superior para liberar los recursos cacheados de la sesión.")
