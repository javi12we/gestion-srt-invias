import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pandas as pd
import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado

from app.core.autorizacion import validar_permiso, ValidacionAutorizacion
from app.core.sesion import obtener_sesion
from app.core.cache_datos import usuarios_activos_para_seleccion, datos_dashboard_admin, limpiar_cache_lecturas

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
    mostrar_titulo_decorado("📊 Dashboard de Gestión")
    st.markdown("Métricas clave y gráficos de rendimiento operativo para el control de correspondencia.")
with col_btn:
    st.write("") # Espaciador para alineación vertical
    st.write("") 
    if st.button("🔄 Actualizar", use_container_width=True, key="refresh_dashboard"):
        limpiar_cache_lecturas()
        st.rerun()

st.divider()

# --- Filtros superiores ---
usuarios_map = usuarios_activos_para_seleccion()  # id -> nombre, ya ordenado
opciones_gestores = ["Todos"] + list(usuarios_map.values())
nombre_a_id = {nombre: uid for uid, nombre in usuarios_map.items()}

TIPOS_DASHBOARD = {"Todos": None, "PQRD": "pqrds", "MEMORANDO": "memorandos", "OFICIO": "oficios"}
OPCIONES_ESTADO_DASHBOARD = [
    "Todos", "pendiente", "en_tramite", "en_revision", "respondido", "archivado", "traslado_competencia"
]

col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    gestor_seleccionado = st.selectbox(
        "Por usuario gestor",
        options=opciones_gestores,
        index=0,
        key="dashboard_filtro_gestor"
    )

with col_f2:
    tipo_seleccionado = st.selectbox(
        "Por tipo",
        options=list(TIPOS_DASHBOARD.keys()),
        index=0,
        key="dashboard_filtro_tipo"
    )

with col_f3:
    estado_seleccionado = st.selectbox(
        "Por estado",
        options=OPCIONES_ESTADO_DASHBOARD,
        index=0,
        format_func=lambda x: x.replace("_", " ").title(),
        key="dashboard_filtro_estado"
    )

usuario_id_filtro = nombre_a_id.get(gestor_seleccionado) if gestor_seleccionado != "Todos" else None
tipo_id_filtro = TIPOS_DASHBOARD.get(tipo_seleccionado)
estado_id_filtro = None if estado_seleccionado == "Todos" else estado_seleccionado

# --- Carga de Servicios ---
try:
    datos = datos_dashboard_admin(usuario_id_filtro, tipo_id_filtro, estado_id_filtro)
    resumen = datos["resumen"]
    dist_estado = datos["dist_estado"]
    carga_usuarios = datos["carga_usuarios"]
    vencimientos = datos["vencimientos"]
    tendencia_d = datos["tendencia_d"]
    tiempos_resp = datos["tiempos_resp"]
    conteo_tipo = datos["conteo_tipo"]
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

# --- 1b. Radicados por Tipo de Documento ---
st.markdown("### 🗂️ Radicados por Tipo de Documento")
t1, t2, t3 = st.columns(3)
t1.metric("PQRD", conteo_tipo.get("pqrds", 0))
t2.metric("Memorandos", conteo_tipo.get("memorandos", 0))
t3.metric("Oficios", conteo_tipo.get("oficios", 0))

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
