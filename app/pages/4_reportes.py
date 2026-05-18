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

is_admin = "admin" in sesion.get("roles", [])

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
        st.rerun()

st.divider()

if not is_admin:
    st.info("ℹ️ **Acceso Restringido:** La generación y descarga de evidencias KAWAK y reportes consolidados en PDF está reservada exclusivamente para los **Administradores** del sistema. Si necesitas acceder a estos archivos físicos, por favor contacta al administrador encargado.")
else:
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
                
                st.download_button(
                    label="⬇️ Descargar Reporte PQRD (PDF)",
                    data=st.session_state.get("pdf_pqrd", b""),
                    file_name=f"Reporte_VUVR_PQRD_{fecha_hoy}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                
                st.download_button(
                    label="⬇️ Descargar Reporte Conglomerado (PDF)",
                    data=st.session_state.get("pdf_conglomerado", b""),
                    file_name=f"Reporte_Correspondencia_{fecha_hoy}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

    st.write("")
    st.caption("💡 **Consejo:** Una vez descargados los archivos, puedes pulsar el botón 'Limpiar' en la parte superior para liberar los recursos cacheados de la sesión.")
