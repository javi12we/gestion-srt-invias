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
    if st.button("🔄 Limpiar", use_container_width=True, key="refresh_reportes"):
        st.session_state.pop("show_pdf_downloads", None)
        st.session_state.pop("show_excel_download", None)
        st.session_state.pop("excel_kawak_buffer", None)
        st.session_state.pop("excel_kawak_name", None)
        st.session_state.pop("pdf_pqrd", None)
        st.session_state.pop("pdf_conglomerado", None)
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
        
        if st.button("Generar Excel KAWAK", use_container_width=True, key="gen_excel", type="primary"):
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
                use_container_width=True
            )

with col_c2:
    with st.container(border=True):
        st.markdown("### 📄 Reportes Oficiales en PDF")
        st.write(
            "Genera y compila los documentos en PDF oficiales y estructurados listos para firma "
            "o archivo: el Reporte de PQRD (Peticiones, Quejas y Reclamos) y el Reporte Conglomerado "
            "general de correspondencia."
        )
        st.write("") # Relleno visual
        
        if st.button("Generar Reportes PDF", use_container_width=True, key="gen_pdf", type="primary"):
            with st.spinner("Generando documentos PDF..."):
                try:
                    pdf_service = PDFReportService()
                    st.session_state["pdf_pqrd"] = pdf_service.generar_pdf_pqrd()
                    st.session_state["pdf_conglomerado"] = pdf_service.generar_pdf_conglomerado()
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
                if st.button("🔍 Previsualizar PQRD", use_container_width=True, key="prev_pqrd"):
                    st.session_state["pdf_preview_data"] = st.session_state.get("pdf_pqrd").getvalue() if hasattr(st.session_state.get("pdf_pqrd"), "getvalue") else st.session_state.get("pdf_pqrd", b"")
                    st.session_state["pdf_preview_title"] = "Reporte VUVR PQRD"
                    st.rerun()
            with col_pqrd_dl:
                st.download_button(
                    label="⬇️ Descargar PDF",
                    data=st.session_state.get("pdf_pqrd", b""),
                    file_name=f"Reporte_VUVR_PQRD_{fecha_hoy}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_pqrd"
                )
            
            # --- Reporte Conglomerado ---
            st.markdown("##### 📌 Reporte Conglomerado")
            col_cong_preview, col_cong_dl = st.columns([1, 1])
            with col_cong_preview:
                if st.button("🔍 Previsualizar Conglomerado", use_container_width=True, key="prev_cong"):
                    st.session_state["pdf_preview_data"] = st.session_state.get("pdf_conglomerado").getvalue() if hasattr(st.session_state.get("pdf_conglomerado"), "getvalue") else st.session_state.get("pdf_conglomerado", b"")
                    st.session_state["pdf_preview_title"] = "Reporte Conglomerado SRTI"
                    st.rerun()
            with col_cong_dl:
                st.download_button(
                    label="⬇️ Descargar PDF",
                    data=st.session_state.get("pdf_conglomerado", b""),
                    file_name=f"Reporte_Correspondencia_{fecha_hoy}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_cong"
                )

# --- Visualizador de PDF Incrustado ---
if st.session_state.get("pdf_preview_data") is not None:
    st.write("")
    st.divider()
    st.markdown(f"### 🔍 Previsualización: {st.session_state.get('pdf_preview_title')}")
    
    import base64
    try:
        pdf_bytes = st.session_state.get("pdf_preview_data")
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600px" type="application/pdf" style="border: none; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">'
        
        col_view, col_close = st.columns([5, 1])
        with col_view:
            st.info("💡 **Consejo:** Puedes usar los controles nativos del navegador dentro del visor para imprimir, hacer zoom o guardar el documento directamente.")
            st.warning("⚠️ **Aviso de Previsualización:** Si no puedes ver el documento a continuación, es posible que tu navegador esté bloqueando la previsualización de PDFs (o necesites permitirlo en la configuración del sitio). En ese caso, utiliza el botón de descarga directa de arriba.")
        with col_close:
            st.write("")
            if st.button("❌ Cerrar Vista", use_container_width=True, key="close_preview"):
                st.session_state["pdf_preview_data"] = None
                st.session_state["pdf_preview_title"] = ""
                st.rerun()
                
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"No se pudo renderizar la vista previa del PDF: {e}")

st.write("")
st.caption("💡 **Consejo:** Una vez descargados los archivos, puedes pulsar el botón 'Limpiar' en la parte superior para liberar los recursos cacheados de la sesión.")
