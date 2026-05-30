import pandas as pd
import streamlit as st

from app.core.autorizacion import validar_permiso, ValidacionAutorizacion
from app.core.sesion import obtener_sesion
from app.services.reporte_service import ReporteService

sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()

try:
    validar_permiso(sesion.get("permisos", []), "dashboard.ver")
except ValidacionAutorizacion:
    st.error("No tienes permisos para ver este módulo.")
    st.stop()

# --- Encabezado ---
col_title, col_btn = st.columns([5, 1])
with col_title:
    st.title("📊 Dashboard de Gestión")
    st.markdown("Métricas clave y gráficos de rendimiento operativo para el control de correspondencia.")
with col_btn:
    st.write("") # Espaciador para alineación vertical
    st.write("") 
    if st.button("🔄 Actualizar", width="stretch", key="refresh_dashboard"):
        st.rerun()

st.divider()

# --- Carga de Servicios ---
try:
    reporte_service = ReporteService()
    resumen = reporte_service.resumen_operativo()
    dist_estado = reporte_service.distribucion_por_estado()
    carga_usuarios = reporte_service.carga_por_usuario()
    vencimientos = reporte_service.analisis_vencimiento()
    tendencia_d = reporte_service.tendencia_diaria(dias=30)
    tiempos_resp = reporte_service.analisis_tiempos_respuesta()
except Exception as e:
    st.error(f"Error al cargar las métricas: {e}")
    st.stop()

# --- 1. Resumen Ejecutivo (KPIs) ---
st.markdown("### 📈 Indicadores Clave de Rendimiento (KPIs)")
m1, m2, m3, m4 = st.columns(4)

vencidos = resumen.get("vencidos_criticos", 0)
m1.metric("Trámites Activos", resumen.get("tramites_activos", 0))
m2.metric(
    "Vencidos Críticos", 
    vencidos, 
    delta=f"{vencidos} hoy" if vencidos > 0 else None, 
    delta_color="inverse"
)
m3.metric("Finalizados", resumen.get("tramites_finalizados", 0))
m4.metric("% Cumplimiento", f"{resumen.get('porcentaje_cumplimiento', 0)}%")

st.divider()

# --- 2. Distribución de Estados y Carga de Responsables ---
col_izq, col_der = st.columns([1, 1])

with col_izq:
    st.subheader("📌 Estado de la Correspondencia")
    if dist_estado is not None and not dist_estado.empty:
        st.bar_chart(dist_estado.set_index("estado"), color="#0056b3")
    else:
        st.info("Sin datos de estados para mostrar.")

with col_der:
    st.subheader("👥 Carga por Responsable")
    if carga_usuarios is not None and not carga_usuarios.empty:
        st.dataframe(
            carga_usuarios.rename(columns={"usuario": "Responsable", "cantidad": "Radicados Pendientes"}), 
            hide_index=True, 
            width="stretch"
        )
    else:
        st.info("No hay trámites activos asignados actualmente.")

st.divider()

# --- 3. Eficiencia y Tendencias ---
col_eff, col_trend = st.columns(2)

with col_eff:
    st.subheader("⏱️ Tiempo de Respuesta Promedio (Días)")
    if tiempos_resp is not None and not tiempos_resp.empty:
        st.bar_chart(tiempos_resp.set_index("Tipo"), color="#28a745")
    else:
        st.info("Historial insuficiente para calcular promedios de tiempo.")

with col_trend:
    st.subheader("📅 Tendencia de Radicación Diaria")
    if tendencia_d is not None and not tendencia_d.empty:
        st.area_chart(tendencia_d.set_index("fecha"), color="#17a2b8")
    else:
        st.info("Sin registros en los últimos 30 días.")

st.divider()

# --- 4. Semáforo de Vencimientos ---
st.subheader("🚨 Semáforo de Vencimientos (Activos)")
if vencimientos is not None and not vencimientos.empty:
    import altair as alt
    
    chart = alt.Chart(vencimientos).mark_bar().encode(
        x=alt.X('categoria:N', title="Estado de Vencimiento", sort=['Vencidos', 'Urgentes (0-5d)', 'A Tiempo (>5d)']),
        y=alt.Y('cantidad:Q', title="Cantidad de Radicados"),
        color=alt.Color('categoria:N', scale=alt.Scale(
            domain=['Vencidos', 'Urgentes (0-5d)', 'A Tiempo (>5d)'],
            range=['#dc3545', '#ffc107', '#28a745'] # Rojo, Amarillo, Verde
        ), legend=None),
        tooltip=['categoria', 'cantidad']
    ).properties(height=350)
    
    st.altair_chart(chart, width="stretch")
else:
    st.info("Sin trámites activos en el sistema.")

st.write("")
st.info("💡 **Nota:** El tiempo de respuesta se calcula desde la fecha de radicación hasta la fecha de la última acción de cierre (respuesta o archivo).")
