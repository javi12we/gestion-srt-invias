"""Seguimiento SUIT: tablero de solo lectura para todo el grupo Permisos.

Misma estructura del dashboard de correspondencia: KPIs en tarjetas, pestañas y
gráficos Plotly con el tema compartido de ``app.core.graficos``. Los datos vienen de
``SuitService.seguimiento`` (a través de ``cache_datos``); aquí solo se dibujan.
"""

import textwrap
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.core.autorizacion import ValidacionAutorizacion
from app.core.cache_datos import limpiar_cache_lecturas, seguimiento_suit
from app.core.catalogos import TRAMITES_SUIT
from app.core.graficos import (
    ESTADO_SEMAFORO, GRIDLINE, SUPERFICIE, aplicar_tema, colores_categoricos, color_secuencial, modo,
)
from app.core.zona_horaria import utc_a_bogota
from app.services.suit_service import permisos_efectivos

_MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
_MESES_LARGO = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
                "Septiembre", "Octubre", "Noviembre", "Diciembre"]
_ESTADOS = {"pendiente": 0, "cargado": 1, "futuro": 2}
_ALTURA_KPI = 128


def _color_cumplimiento(valor: int) -> str:
    """Mismos umbrales del gauge de cumplimiento del dashboard."""
    if valor < 50:
        return ESTADO_SEMAFORO["critical"]
    return ESTADO_SEMAFORO["warning"] if valor < 80 else ESTADO_SEMAFORO["good"]


def _etiqueta(nombre: str, ancho: int = 30) -> str:
    return "<br>".join(textwrap.wrap(nombre, ancho))


def figura_matriz(tramites: list[dict], oscuro: bool) -> go.Figure:
    """Mapa de calor trámite × mes: cargado / pendiente / por vencer (con símbolo, no solo color)."""
    m = modo(oscuro)
    colores = [ESTADO_SEMAFORO["critical"], ESTADO_SEMAFORO["good"], GRIDLINE[m]]
    escala = [[0, colores[0]], [1 / 3, colores[0]], [1 / 3, colores[1]],
              [2 / 3, colores[1]], [2 / 3, colores[2]], [1, colores[2]]]
    simbolo = {"cargado": "✓", "pendiente": "!", "futuro": ""}
    nombre_estado = {"cargado": "Cargado", "pendiente": "Pendiente", "futuro": "Por vencer"}

    fig = go.Figure(go.Heatmap(
        z=[[_ESTADOS[e] for e in t["estados"]] for t in tramites],
        x=_MESES,
        y=[_etiqueta(t["nombre"]) for t in tramites],
        text=[[simbolo[e] for e in t["estados"]] for t in tramites],
        customdata=[[nombre_estado[e] for e in t["estados"]] for t in tramites],
        texttemplate="%{text}", textfont=dict(color="#ffffff", size=15),
        colorscale=escala, zmin=0, zmax=2, showscale=False,
        xgap=3, ygap=3,
        hovertemplate="%{y}<br>%{x}: %{customdata}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(side="top")
    aplicar_tema(fig, oscuro, altura=64 * len(tramites) + 60)
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor=SUPERFICIE[m])
    return fig


def figura_cumplimiento(tramites: list[dict], oscuro: bool) -> go.Figure:
    """Barras horizontales: % de meses vencidos ya cargados por trámite."""
    datos = sorted(tramites, key=lambda t: t["cumplimiento"])
    fig = go.Figure(go.Bar(
        x=[t["cumplimiento"] for t in datos],
        y=[_etiqueta(t["nombre"]) for t in datos],
        orientation="h",
        marker_color=[_color_cumplimiento(t["cumplimiento"]) for t in datos],
        text=[f"{t['cumplimiento']}%" for t in datos], textposition="outside",
        hovertemplate="%{y}: %{x}% de los meses vencidos cargados<extra></extra>",
    ))
    fig.update_xaxes(range=[0, 115], title="Meses vencidos cargados (%)", tickvals=[0, 25, 50, 75, 100])
    aplicar_tema(fig, oscuro, altura=max(320, 58 * len(datos)))
    return fig


def figura_solicitudes(serie: dict, oscuro: bool) -> go.Figure:
    """Solicitudes resueltas por mes, en línea vs presencial."""
    cat = colores_categoricos(oscuro)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=_MESES, y=serie["solicitudes_linea"], name="En línea", marker_color=cat[0],
                         hovertemplate="%{x}: %{y} en línea<extra></extra>"))
    fig.add_trace(go.Bar(x=_MESES, y=serie["solicitudes_presencial"], name="Presenciales", marker_color=cat[1],
                         hovertemplate="%{x}: %{y} presenciales<extra></extra>"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="Solicitudes resueltas")
    return aplicar_tema(fig, oscuro, altura=320)


def figura_pqrd_mensual(serie: dict, oscuro: bool) -> go.Figure:
    """PQRD recibidas por mes (los meses sin cargue quedan como hueco, no como cero)."""
    color = color_secuencial(oscuro)
    fig = go.Figure(go.Scatter(
        x=_MESES, y=serie["pqrd_recibidas"], mode="lines+markers", name="PQRD recibidas",
        line=dict(color=color, width=2), marker=dict(size=8, line=dict(width=2, color=SUPERFICIE[modo(oscuro)])),
        connectgaps=False, hovertemplate="%{x}: %{y} PQRD<extra></extra>",
    ))
    fig.update_yaxes(title="PQRD recibidas", rangemode="tozero")
    return aplicar_tema(fig, oscuro, altura=320)


def figura_composicion_pqrd(totales: dict, oscuro: bool) -> go.Figure:
    """Composición del año de las PQRD relacionadas con el trámite."""
    cat = colores_categoricos(oscuro)
    etiquetas = ["Quejas", "Reclamos", "Denuncias", "Otras PQRD"]
    valores = [totales["quejas"], totales["reclamos"], totales["denuncias"], totales["otras_pqrd"]]
    fig = go.Figure(go.Pie(
        labels=etiquetas, values=valores, hole=0.55,
        marker=dict(colors=cat[:4], line=dict(color=SUPERFICIE[modo(oscuro)], width=2)),
        textinfo="label+percent", textposition="outside", sort=False,
        hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
    ))
    fig.add_annotation(text=f"<b>{sum(valores)}</b><br>en el año", x=0.5, y=0.5, showarrow=False, font=dict(size=15))
    fig.update_layout(showlegend=False)
    return aplicar_tema(fig, oscuro, altura=320)


def _fmt(valor: float, decimales: int = 0) -> str:
    """Formato colombiano: punto de miles y coma decimal."""
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _total(serie: dict, campo: str) -> int:
    return sum(v for v in serie[campo] if v is not None)


def _render_kpis(datos: dict) -> None:
    k = datos["kpis"]
    c1, c2, c3, c4 = st.columns(4)
    with c1.container(border=True, height=_ALTURA_KPI):
        st.metric(f"Avance {datos['anio']}", f"{k['avance_anual']}%", help="Meses cargados del año sobre el total (7 trámites × 12 meses).")
    with c2.container(border=True, height=_ALTURA_KPI):
        st.metric("Cumplimiento al día", "—" if k["cumplimiento"] is None else f"{k['cumplimiento']}%",
                  help="Meses ya vencidos que sí tienen cargue.")
    with c3.container(border=True, height=_ALTURA_KPI):
        pend = k["pendientes_vencidos"]
        st.metric("Meses vencidos sin cargar", pend,
                  delta=f"{pend} por cargar" if pend else None, delta_color="inverse")
    with c4.container(border=True, height=_ALTURA_KPI):
        sin = k["sin_responsable"]
        st.metric("Trámites sin responsable", sin,
                  delta=f"{sin} sin asignar" if sin else None, delta_color="inverse")


def _tab_cumplimiento(datos: dict, oscuro: bool) -> None:
    st.markdown("**Cargue por trámite y mes**")
    st.markdown(":green-badge[:material/check: Cargado] :red-badge[:material/priority_high: Pendiente] "
                ":gray-badge[Por vencer]")
    st.plotly_chart(figura_matriz(datos["tramites"], oscuro), width="stretch", config={"displayModeBar": False})
    st.caption("Un mes se considera vencido cuando ya terminó y no tiene cargue guardado.")

    st.markdown("**Cumplimiento por trámite**")
    if datos["meses_vencidos"]:
        st.plotly_chart(figura_cumplimiento(datos["tramites"], oscuro), width="stretch",
                        config={"displayModeBar": False})
    else:
        st.caption(f"Aún no hay meses vencidos en {datos['anio']}: el cumplimiento se calcula cuando termine el primer mes.")

    with st.expander("Ver datos del seguimiento"):
        st.dataframe(pd.DataFrame(
            [{"Trámite": t["nombre"], **{_MESES[i]: e.capitalize() for i, e in enumerate(t["estados"])}}
             for t in datos["tramites"]]
        ), hide_index=True, width="stretch")


def _tab_indicadores(datos: dict, oscuro: bool) -> None:
    opciones = ["todos", *TRAMITES_SUIT]
    tramite = st.selectbox(
        "Trámite", opciones, key="suit_seg_tramite",
        format_func=lambda t: "Todos los trámites" if t == "todos" else TRAMITES_SUIT[t]["label_corto"],
    )
    serie = datos["indicadores"][tramite]
    meses_con_datos = sum(1 for v in serie["solicitudes_linea"] if v is not None)
    if not meses_con_datos:
        st.info("Aún no hay cargues para este trámite en el año seleccionado.")
        return

    linea, presencial = _total(serie, "solicitudes_linea"), _total(serie, "solicitudes_presencial")
    resueltas = linea + presencial
    m1, m2, m3, m4 = st.columns(4)
    with m1.container(border=True, height=_ALTURA_KPI):
        st.metric("Solicitudes resueltas", _fmt(resueltas))
    with m2.container(border=True, height=_ALTURA_KPI):
        st.metric("Resueltas en línea", f"{round(100 * linea / resueltas)}%" if resueltas else "—",
                  help="Porcentaje de solicitudes resueltas por medios electrónicos.")
    with m3.container(border=True, height=_ALTURA_KPI):
        st.metric("PQRD recibidas", _fmt(_total(serie, "pqrd_recibidas")))
    with m4.container(border=True, height=_ALTURA_KPI):
        st.metric("Promedio mensual de solicitudes", _fmt(resueltas / meses_con_datos, 1),
                  help=f"Sobre los {meses_con_datos} mes(es) con cargue.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Solicitudes resueltas por mes**")
        st.plotly_chart(figura_solicitudes(serie, oscuro), width="stretch", config={"displayModeBar": False})
    with c2:
        st.markdown("**PQRD recibidas por mes**")
        st.plotly_chart(figura_pqrd_mensual(serie, oscuro), width="stretch", config={"displayModeBar": False})

    totales = {c: _total(serie, c) for c in ("quejas", "reclamos", "denuncias", "otras_pqrd")}
    if sum(totales.values()):
        st.markdown("**Composición de las PQRD relacionadas con el trámite**")
        st.plotly_chart(figura_composicion_pqrd(totales, oscuro), width="stretch", config={"displayModeBar": False})
    st.caption("Los meses sin cargue no se cuentan como cero: aparecen vacíos en los gráficos.")

    with st.expander("Ver datos de indicadores"):
        st.dataframe(pd.DataFrame({"Mes": _MESES_LARGO, **{
            campo: serie[campo] for campo in serie
        }}), hide_index=True, width="stretch")


def _tab_responsables(datos: dict) -> None:
    st.markdown("**Responsables y estado por trámite**")
    filas = []
    for t in datos["tramites"]:
        ultimo = t["ultimo_guardado"]
        filas.append({
            "Trámite": t["nombre"],
            "Encargado(s)": ", ".join(t["responsables"]) or "⚠ Sin responsable",
            "Cumplimiento": t["cumplimiento"],
            "Meses cargados": f"{t['cargados']}/12",
            "Vencidos sin cargar": t["pendientes"],
            "Último guardado": utc_a_bogota(ultimo).strftime("%d/%m/%Y %H:%M") if ultimo else "—",
        })
    st.dataframe(
        pd.DataFrame(filas), hide_index=True, width="stretch",
        column_config={"Cumplimiento": st.column_config.ProgressColumn(
            "Cumplimiento", min_value=0, max_value=100, format="%d%%")},
    )


def render_seguimiento(sesion: dict) -> None:
    oscuro = st.session_state.get("dark_mode", False)
    anio_actual = utc_a_bogota(datetime.now(timezone.utc)).year

    col_anio, col_btn = st.columns([4, 1], vertical_alignment="bottom")
    with col_anio:
        anio = st.selectbox("Año", list(range(anio_actual, anio_actual - 5, -1)), key="suit_seg_anio")
    with col_btn:
        if st.button("Actualizar", icon=":material/refresh:", key="suit_seg_refrescar"):
            limpiar_cache_lecturas()  # el clic ya re-ejecuta el script: no hace falta st.rerun

    try:
        datos = seguimiento_suit(anio, sesion.get("id"), tuple(permisos_efectivos(sesion)))
    except ValidacionAutorizacion as e:
        st.warning(str(e))
        return
    except Exception as e:
        st.error(f"Error al cargar el seguimiento: {e}")
        return

    _render_kpis(datos)
    st.space("small")
    tab_cumplimiento, tab_indicadores, tab_responsables = st.tabs([
        ":material/grid_view: Cumplimiento", ":material/query_stats: Indicadores", ":material/groups: Responsables",
    ])
    with tab_cumplimiento:
        _tab_cumplimiento(datos, oscuro)
    with tab_indicadores:
        _tab_indicadores(datos, oscuro)
    with tab_responsables:
        _tab_responsables(datos)
