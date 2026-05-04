import pandas as pd
import streamlit as st

from app.core.autorizacion import validar_permiso, ValidacionAutorizacion
from app.core.sesion import obtener_sesion
from app.core.streamlit_compat import show_dataframe
from app.core.zona_horaria import formato_fecha_bogota, formato_duracion
from app.services.reporte_service import ReporteService


st.title("Reportes")
sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()

try:
    validar_permiso(sesion.get("permisos", []), "reporte.ver")
except ValidacionAutorizacion:
    st.error("No tienes permisos para ver este módulo.")
    st.stop()

reporte_service = ReporteService()
resumen = reporte_service.resumen_general(dias=30)
por_usuario = reporte_service.por_usuario(dias=30)
linea_tiempo = reporte_service.linea_tiempo(dias=30)
ultimas = reporte_service.ultimas_sesiones(limite=20)

st.subheader("Resumen general - últimos 30 días")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Sesiones totales", resumen["sesiones_total"])
col2.metric("Activas ahora", resumen["sesiones_activas"])
col3.metric("Cerradas", resumen["sesiones_cerradas"])
col4.metric("Duración promedio", formato_duracion(int(resumen["duracion_promedio_segundos"]) if resumen["duracion_promedio_segundos"] else 0))

st.divider()
st.subheader("Actividad por usuario")
if por_usuario.empty:
    st.info("Todavía no hay actividad suficiente para mostrar el gráfico.")
else:
    st.bar_chart(por_usuario.set_index("usuario")[["sesiones"]])
    show_dataframe(por_usuario, hide_index=True)

st.divider()
st.subheader("Línea de tiempo de actividad")
if linea_tiempo.empty:
    st.info("Todavía no hay eventos para la línea de tiempo.")
else:
    st.line_chart(linea_tiempo.set_index("fecha")[["cantidad"]])

st.divider()
st.subheader("Últimas sesiones cerradas")
if not ultimas:
    st.info("Sin sesiones cerradas registradas aún.")
else:
    tabla = pd.DataFrame(
        [
            {
                "Usuario": s.get("usuario"),
                "Inicio": formato_fecha_bogota(s.get("fecha_inicio")),
                "Cierre": formato_fecha_bogota(s.get("fecha_cierre")),
                "Duración": formato_duracion(s.get("duracion_segundos")),
                "Motivo": s.get("motivo_cierre"),
            }
            for s in ultimas
        ]
    )
    show_dataframe(tabla, hide_index=True)
