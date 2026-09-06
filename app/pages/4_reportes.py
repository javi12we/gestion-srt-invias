import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import datetime
import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado

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

es_admin = any(r in {"admin", "administrador"} for r in sesion.get("roles", []))


# --- Encabezado ---
col_title, col_btn = st.columns([5, 1])
with col_title:
    mostrar_titulo_decorado("📄 Reportes y Evidencias")
    st.markdown("Generación de reportes de correspondencia oficiales y evidencias estructuradas para el sistema KAWAK.")
with col_btn:
    st.write("") # Espaciador para alineación
    st.write("") 
    if st.button("🔄 Limpiar", width="stretch", key="refresh_reportes"):
        st.session_state.pop("show_pdf_downloads", None)
        st.session_state.pop("show_excel_download", None)
        st.session_state.pop("excel_kawak_buffer", None)
        st.session_state.pop("excel_kawak_name", None)
        st.session_state.pop("show_excel_gen_download", None)
        st.session_state.pop("excel_kawak_gen_buffer", None)
        st.session_state.pop("excel_kawak_gen_name", None)
        st.session_state.pop("show_excel_users_download", None)
        st.session_state.pop("excel_users_buffer", None)
        st.session_state.pop("excel_users_name", None)
        st.session_state.pop("show_consolidado_download", None)
        st.session_state.pop("consolidado_buffer", None)
        st.session_state.pop("consolidado_name", None)
        st.session_state.pop("show_conglomerado_persona_download", None)
        st.session_state.pop("conglomerado_persona_buffer", None)
        st.session_state.pop("conglomerado_persona_name", None)
        st.session_state.pop("pdf_pqrd", None)
        st.session_state.pop("pdf_conglomerado", None)
        st.session_state.pop("pdf_total", None)
        st.session_state.pop("pdf_cargue_cuentas", None)
        st.session_state.pop("show_cargue_cuentas_download", None)
        st.session_state.pop("pdf_preview_data", None)
        st.session_state.pop("pdf_preview_title", None)
        st.rerun()

st.divider()

# --- Interfaz en Cards para Administrador ---
col_c1, col_c2 = st.columns(2)

with col_c1:
    if es_admin:
        with st.container(border=True):
            st.markdown("### 📗 Evidencia KAWAK (Excel)")
            st.write(
                "Genera el libro de Excel consolidado que cumple con los campos exactos, "
                "estructuras y codificaciones solicitadas por la plataforma KAWAK para la carga "
                "de evidencias de gestión de correspondencia."
            )
            # Selector de período para KAWAK
            anio_actual = datetime.date.today().year
            col_sel_y, col_sel_q = st.columns(2)
            with col_sel_y:
                anio_kawak = st.selectbox(
                    "Año",
                    options=[anio_actual - 1, anio_actual, anio_actual + 1],
                    index=1,
                    key="anio_kawak_sel"
                )
            with col_sel_q:
                trim_kawak = st.selectbox(
                    "Trimestre",
                    options=[1, 2, 3, 4],
                    format_func=lambda x: f"T{x}",
                    index=(datetime.date.today().month - 1) // 3,
                    key="trim_kawak_sel"
                )
            
            st.write("") # Relleno visual
            
            if st.button("Generar Excel KAWAK", width="stretch", key="gen_excel", type="primary"):
                with st.spinner("Procesando datos y estructurando hoja Excel..."):
                    try:
                        excel_service = ExcelReportService()
                        buffer, nombre = excel_service.generar_excel_kawak(anio_kawak, trim_kawak)
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

    # Conglomerado PQRD - Grupos Trimestral
    with st.container(border=True):
        st.markdown("### 📘 Conglomerado PQRD - Grupos Trimestral (Excel)")
        st.write(
            "Genera el reporte trimestral consolidado de PQRD que cumple con los campos y "
            "codificaciones de la plataforma para todos los grupos de trabajo."
        )
        # Selector de período para KAWAK General
        anio_actual_g = datetime.date.today().year
        col_sel_y_g, col_sel_q_g = st.columns(2)
        with col_sel_y_g:
            anio_kawak_g = st.selectbox(
                "Año",
                options=[anio_actual_g - 1, anio_actual_g, anio_actual_g + 1],
                index=1,
                key="anio_kawak_gen_sel"
            )
        with col_sel_q_g:
            trim_kawak_g = st.selectbox(
                "Trimestre",
                options=[1, 2, 3, 4],
                format_func=lambda x: f"T{x}",
                index=(datetime.date.today().month - 1) // 3,
                key="trim_kawak_gen_sel"
            )
        
        st.write("") # Relleno visual
        
        if st.button("Generar Conglomerado PQRD", width="stretch", key="gen_excel_gen", type="primary"):
            with st.spinner("Procesando datos y estructurando reporte conglomerado..."):
                try:
                    excel_service = ExcelReportService()
                    buffer_g, nombre_g = excel_service.generar_excel_kawak_general(anio_kawak_g, trim_kawak_g)
                    st.session_state["excel_kawak_gen_buffer"] = buffer_g
                    st.session_state["excel_kawak_gen_name"] = nombre_g
                    st.session_state["show_excel_gen_download"] = True
                    st.success("¡Reporte Conglomerado generado con éxito!")
                except Exception as e:
                    st.error(f"Error generando reporte: {e}")
        
        if st.session_state.get("show_excel_gen_download", False):
            st.write("")
            st.download_button(
                label="⬇️ Descargar Conglomerado PQRD (Excel)",
                data=st.session_state.get("excel_kawak_gen_buffer", b""),
                file_name=st.session_state.get("excel_kawak_gen_name", "Conglomerado_PQRD_Trimestral.xlsx"),
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

# --- Fila 2: Reporte Consolidado y Cargue de Cuentas ---
st.write("")
col_r2_1, col_r2_2 = st.columns(2)

with col_r2_1:
  if es_admin:
    with st.container(border=True):
        st.markdown("### 📊 Consolidado Correspondencia Anual (Excel)")
        st.write(
            "Genera el libro de Excel consolidado con la correspondencia total del año seleccionado. "
            "Contiene las mismas columnas y el resumen por Clase, sin filtros restrictivos."
        )
        
        # Selector de año para Consolidado Anual
        anio_actual_c = datetime.date.today().year
        anio_consolidado = st.selectbox(
            "Seleccione el año del consolidado",
            options=[anio_actual_c - 1, anio_actual_c, anio_actual_c + 1],
            index=1,
            key="anio_consolidado_sel"
        )
        
        if st.button("Generar Consolidado Anual", width="stretch", key="gen_consolidado", type="primary"):
            with st.spinner("Procesando correspondencia total del año..."):
                try:
                    excel_service = ExcelReportService()
                    buffer, nombre = excel_service.generar_excel_consolidado_anual(anio_consolidado)
                    st.session_state["consolidado_buffer"] = buffer
                    st.session_state["consolidado_name"] = nombre
                    st.session_state["show_consolidado_download"] = True
                    st.success("¡Consolidado Anual generado con éxito!")
                except Exception as e:
                    st.error(f"Error generando Consolidado: {e}")

        if st.session_state.get("show_consolidado_download", False):
            st.write("")
            st.download_button(
                label="⬇️ Descargar Consolidado Anual (Excel)",
                data=st.session_state.get("consolidado_buffer", b""),
                file_name=st.session_state.get("consolidado_name", "Consolidado_Correspondencia.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
                key="dl_consolidado"
            )

with col_r2_2:
    with st.container(border=True):
        st.markdown("### 📊 Reporte Cargue de Cuentas (SECOP - GD - CORRESPONDENCIA)")
        st.write(
            "Genera un reporte consolidado en PDF con orientación horizontal que contiene la trazabilidad "
            "mensual del cargue de cuentas para todos los usuarios con contrato activo."
        )
        
        # Selector de año
        anio_actual = datetime.datetime.now().year
        anio_reporte = st.selectbox("Seleccione el año del reporte", options=[anio_actual - 1, anio_actual, anio_actual + 1], index=1, key="anio_reporte_cargue")
        
        if st.button("Generar Reporte Cargue de Cuentas", width="stretch", key="gen_cargue_cuentas", type="primary"):
            with st.spinner("Generando reporte condicional..."):
                try:
                    pdf_service = PDFReportService()
                    st.session_state["pdf_cargue_cuentas"] = pdf_service.generar_pdf_cargue_cuentas(anio_reporte)
                    st.session_state["show_cargue_cuentas_download"] = True
                    st.success("¡Reporte Cargue de Cuentas generado con éxito!")
                except Exception as e:
                    st.error(f"Error generando Reporte Cargue de Cuentas: {e}")
                    
        if st.session_state.get("show_cargue_cuentas_download", False):
            st.write("")
            col_cc_prev, col_cc_dl = st.columns([1, 1])
            with col_cc_prev:
                if st.button("🔍 Previsualizar Reporte", width="stretch", key="prev_cargue_cuentas"):
                    st.session_state["pdf_preview_data"] = st.session_state.get("pdf_cargue_cuentas").getvalue() if hasattr(st.session_state.get("pdf_cargue_cuentas"), "getvalue") else st.session_state.get("pdf_cargue_cuentas", b"")
                    st.session_state["pdf_preview_title"] = f"Reporte Cargue de Cuentas {anio_reporte}"
                    st.rerun()
            with col_cc_dl:
                st.download_button(
                    label="⬇️ Descargar Reporte PDF",
                    data=st.session_state.get("pdf_cargue_cuentas", b""),
                    file_name=f"Reporte_Cargue_Cuentas_{anio_reporte}_{datetime.datetime.now().strftime('%Y-%m-%d')}.pdf",
                    mime="application/pdf",
                    width="stretch",
                    key="dl_cargue_cuentas"
                )


# --- Fila 3: Reporte de Usuarios Registrados ---
st.write("")
col_r3_1, col_r3_2 = st.columns(2)

with col_r3_1:
    with st.container(border=True):
        st.markdown("### 👥 Reporte de Usuarios Registrados (Excel)")
        st.write(
            "Genera un libro de Excel con la información de todos los usuarios registrados en el sistema, "
            "sus roles, documentos y su estado de vigencia contractual actual (activo/inactivo)."
        )
        st.write("") # Relleno visual
        
        if st.button("Generar Reporte de Usuarios", width="stretch", key="gen_users_excel", type="primary"):
            with st.spinner("Procesando usuarios registrados y vigencia contractual..."):
                try:
                    excel_service = ExcelReportService()
                    buffer_u, nombre_u = excel_service.generar_excel_usuarios()
                    st.session_state["excel_users_buffer"] = buffer_u
                    st.session_state["excel_users_name"] = nombre_u
                    st.session_state["show_excel_users_download"] = True
                    st.success("¡Reporte de usuarios generado con éxito!")
                except Exception as e:
                    st.error(f"Error generando reporte de usuarios: {e}")
                    
        if st.session_state.get("show_excel_users_download", False):
            st.write("")
            st.download_button(
                label="⬇️ Descargar Reporte de Usuarios (Excel)",
                data=st.session_state.get("excel_users_buffer", b"\x00"),
                file_name=st.session_state.get("excel_users_name", "Reporte_Usuarios.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
                key="dl_users"
            )

with col_r3_2:
    if es_admin:
        with st.container(border=True):
            st.markdown("### 🗂️ Conglomerado por Persona (Excel)")
            st.write(
                "Genera un libro de Excel con la correspondencia total del año seleccionado, "
                "con una hoja por cada responsable y sus tablas de resumen por Clase, Tipo y "
                "Responsable. Cada hoja trae el filtro de Excel activado en 'En trámite', "
                "que se puede quitar para ver toda la correspondencia de esa persona."
            )

            # Selector de año para Conglomerado por Persona
            anio_actual_p = datetime.date.today().year
            anio_conglomerado_persona = st.selectbox(
                "Seleccione el año del conglomerado",
                options=[anio_actual_p - 1, anio_actual_p, anio_actual_p + 1],
                index=1,
                key="anio_conglomerado_persona_sel"
            )

            if st.button("Generar Conglomerado por Persona", width="stretch", key="gen_conglomerado_persona", type="primary"):
                with st.spinner("Procesando correspondencia por responsable..."):
                    try:
                        excel_service = ExcelReportService()
                        buffer_p, nombre_p = excel_service.generar_excel_conglomerado_persona(anio_conglomerado_persona)
                        st.session_state["conglomerado_persona_buffer"] = buffer_p
                        st.session_state["conglomerado_persona_name"] = nombre_p
                        st.session_state["show_conglomerado_persona_download"] = True
                        st.success("¡Conglomerado por Persona generado con éxito!")
                    except Exception as e:
                        st.error(f"Error generando Conglomerado por Persona: {e}")

            if st.session_state.get("show_conglomerado_persona_download", False):
                st.write("")
                st.download_button(
                    label="⬇️ Descargar Conglomerado por Persona (Excel)",
                    data=st.session_state.get("conglomerado_persona_buffer", b""),
                    file_name=st.session_state.get("conglomerado_persona_name", "Conglomerado_Correspondencia_Por_Persona.xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    key="dl_conglomerado_persona"
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
