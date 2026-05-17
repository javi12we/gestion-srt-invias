import pandas as pd
import streamlit as st

from app.core.autorizacion import validar_permiso, ValidacionAutorizacion
from app.core.sesion import obtener_sesion
from app.core.streamlit_compat import show_dataframe
from app.services.reporte_service import ReporteService

from app.services.pdf_report_service import PDFReportService
import datetime

sesion = obtener_sesion()

col_title1, col_title2, col_title3 = st.columns([3, 1, 1])
with col_title1:
    st.title("Reportes")

is_admin = False
if sesion:
    is_admin = "admin" in sesion.get("roles", [])

with col_title2:
    if is_admin:
        if st.button("📄 Reporte PDF", use_container_width=True, key="gen_pdf"):
            with st.spinner("Generando PDFs..."):
                try:
                    pdf_service = PDFReportService()
                    st.session_state["pdf_pqrd"] = pdf_service.generar_pdf_pqrd()
                    st.session_state["pdf_conglomerado"] = pdf_service.generar_pdf_conglomerado()
                    st.session_state["show_pdf_downloads"] = True
                except Exception as e:
                    st.error(f"Error generando PDF: {e}")

with col_title3:
    if st.button("🔄 Actualizar", use_container_width=True, key="refresh_reportes"):
        st.session_state.pop("show_pdf_downloads", None)
        st.rerun()

if st.session_state.get("show_pdf_downloads", False):
    st.info("✅ Reportes generados con éxito. Descárgalos aquí:")
    col_d1, col_d2 = st.columns(2)
    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d")
    with col_d1:
        st.download_button(
            label="⬇️ Descargar Reporte PQRD",
            data=st.session_state.get("pdf_pqrd", b""),
            file_name=f"Reporte_VUVR_PQRD_{fecha_hoy}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    with col_d2:
        st.download_button(
            label="⬇️ Descargar Reporte Conglomerado",
            data=st.session_state.get("pdf_conglomerado", b""),
            file_name=f"Reporte_Correspondencia_{fecha_hoy}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()

try:
    validar_permiso(sesion.get("permisos", []), "reporte.ver")
except ValidacionAutorizacion:
    st.error("No tienes permisos para ver este módulo.")
    st.stop()

reporte_service = ReporteService()
resumen = reporte_service.resumen_operativo()
dist_estado = reporte_service.distribucion_por_estado()
carga_usuarios = reporte_service.carga_por_usuario()
vencimientos = reporte_service.analisis_vencimiento()
tendencia_d = reporte_service.tendencia_diaria(dias=30)
tiempos_resp = reporte_service.analisis_tiempos_respuesta()

# --- 1. Resumen Ejecutivo ---
st.markdown("### 📈 Indicadores de Gestión")
m1, m2, m3, m4 = st.columns(4)

vencidos = resumen["vencidos_criticos"]
m1.metric("Trámites Activos", resumen["tramites_activos"])
m2.metric(
    "Vencidos Críticos", 
    vencidos, 
    delta=f"{vencidos} hoy" if vencidos > 0 else None, 
    delta_color="inverse"
)
m3.metric("Finalizados", resumen["tramites_finalizados"])
m4.metric("% Cumplimiento", f"{resumen['porcentaje_cumplimiento']}%")


st.divider()

# --- 2. Distribución y Carga ---
col_izq, col_der = st.columns([1, 1])

with col_izq:
    st.subheader("📌 Estado de la Correspondencia")
    if not dist_estado.empty:
        st.bar_chart(dist_estado.set_index("estado"), color="#0056b3")
    else:
        st.info("Sin datos para mostrar.")

with col_der:
    st.subheader("👥 Carga por Responsable")
    if not carga_usuarios.empty:
        # Usamos tabla para evitar el desorden visual con muchos usuarios
        st.dataframe(
            carga_usuarios.rename(columns={"usuario": "Responsable", "cantidad": "Radicados Pendientes"}), 
            hide_index=True, 
            use_container_width=True
        )
    else:
        st.info("No hay trámites activos asignados.")

st.divider()

# --- 3. Eficiencia y Tendencias ---
col_eff, col_trend = st.columns(2)

with col_eff:
    st.subheader("⏱️ Tiempo de Respuesta (Días)")
    if not tiempos_resp.empty:
        # Gráfico de eficiencia en verde
        st.bar_chart(tiempos_resp.set_index("Tipo"), color="#28a745")
    else:
        st.info("Histórico insuficiente para promediar tiempos.")

with col_trend:
    st.subheader("📅 Tendencia Diaria (Radicados)")
    if not tendencia_d.empty:
        st.area_chart(tendencia_d.set_index("fecha"), color="#17a2b8")
    else:
        st.info("Sin registros en los últimos 30 días.")

st.divider()

# --- 4. Semáforo de Vencimientos ---
st.subheader("🚨 Semáforo de Vencimientos (Activos)")
if not vencimientos.empty:
    import altair as alt
    
    # Crear el gráfico con Altair para control total de colores
    chart = alt.Chart(vencimientos).mark_bar().encode(
        x=alt.X('categoria:N', title="Estado de Vencimiento", sort=['Vencidos', 'Urgentes (0-5d)', 'A Tiempo (>5d)']),
        y=alt.Y('cantidad:Q', title="Cantidad de Radicados"),
        color=alt.Color('categoria:N', scale=alt.Scale(
            domain=['Vencidos', 'Urgentes (0-5d)', 'A Tiempo (>5d)'],
            range=['#dc3545', '#ffc107', '#28a745'] # Rojo, Amarillo, Verde
        ), legend=None),
        tooltip=['categoria', 'cantidad']
    ).properties(height=350)
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Sin trámites activos.")



st.write("")
st.info("💡 **Nota:** El tiempo de respuesta se calcula desde la fecha de radicación hasta la fecha de la última acción de cierre (respuesta o archivo).")


