import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

"""Página del sistema SUIT — cargue mensual de PQRD, separado de Correspondencia.

Una sola vista: pestañas (Cargue / Seguimiento / Reporte), un selector de trámite y el
formulario del mes. No hay menús que abran subpantallas ni st.rerun: cada widget
conserva su propio estado y el semáforo se refresca en el mismo pase tras guardar.
Las reglas de negocio viven en SuitService.
"""

from datetime import datetime, timezone

import streamlit as st
from app.core.autorizacion import ValidacionAutorizacion
from app.core.cache_datos import seguimiento_suit
from app.core.catalogos import CAMPOS_SUIT, TOTALES_SUIT, TRAMITES_SUIT
from app.core.ui_suit_reporte import render_reporte
from app.core.ui_suit_seguimiento import render_seguimiento
from app.core.ui_titulos import mostrar_titulo_decorado
from app.core.sesion import obtener_sesion
from app.core.zona_horaria import utc_a_bogota
from app.services.suit_service import ErrorConflictoSuit, ErrorSuit, SuitService, permisos_efectivos

st.set_page_config(
    page_title="SUIT",
    page_icon="app/assets/invias_fav_ico_3.ico",
    layout="wide",
)


_TRIMESTRES = {
    "1": ["Enero", "Febrero", "Marzo"],
    "2": ["Abril", "Mayo", "Junio"],
    "3": ["Julio", "Agosto", "Septiembre"],
    "4": ["Octubre", "Noviembre", "Diciembre"],
}
_SECCIONES = {
    "resueltas": ("Solicitudes resueltas", ":material/task_alt:"),
    "pqrd": ("PQRD", ":material/forum:"),
}


_NOMBRE_MES = dict(enumerate((n for meses in _TRIMESTRES.values() for n in meses), start=1))

# Semáforo del cargue: rojo si falta algún mes ya vencido, verde si no falta ninguno,
# gris si aún no vence ningún mes del periodo.
_SEMAFORO = {
    "pendiente": ("red", ":material/error:"),
    "al_dia": ("green", ":material/check_circle:"),
    "por_vencer": ("gray", ":material/schedule:"),
}


def _render_avance(servicio: SuitService, tramite: str, anio: int) -> None:
    """Semáforo del año: rojo o verde por trimestre según falte o no cargue, y responsables del trámite."""
    progreso = servicio.progreso(tramite, anio)
    color, icono = _SEMAFORO[progreso["estado"]]
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**Avance del cargue {anio}**")
            st.badge(f"{progreso['anual']}%", icon=icono, color=color)
            if progreso["faltan"]:
                st.caption(f"Faltan {len(progreso['faltan'])} mes(es) por cargar")
        for col, (trim, datos) in zip(st.columns(4), progreso["trimestres"].items()):
            color_t, icono_t = _SEMAFORO[datos["estado"]]
            with col:
                st.badge(f"T{trim} · {datos['porcentaje']}%", icon=icono_t, color=color_t)
                st.progress(datos["porcentaje"] / 100)
                if datos["faltan"]:
                    st.caption("Falta: " + ", ".join(_NOMBRE_MES[m] for m in datos["faltan"]))
                else:
                    st.caption(f"{datos['meses_cargados']}/3 meses cargados")
        responsables = servicio.responsables(tramite)
        if responsables:
            st.caption(":material/person: Encargado(s): "
                       + ", ".join(f"{r['nombre']} (@{r['usuario']})" for r in responsables))
        else:
            st.caption(":material/person_off: Sin responsable asignado")


def _render_formulario(tramite: str, sesion: dict) -> None:
    """Formulario del mes: carga lo ya guardado y se puede editar siempre."""
    servicio = SuitService()
    anio_actual = utc_a_bogota(datetime.now(timezone.utc)).year

    zona_avance = st.container()  # se llena al final para reflejar un guardado reciente

    col_anio, col_trim, col_mes = st.columns([1, 2, 3], vertical_alignment="bottom")
    with col_anio:
        anio = st.selectbox("Año", list(range(anio_actual, anio_actual - 5, -1)), key=f"anio_{tramite}")
    with col_trim:
        trimestre = st.segmented_control(
            "Trimestre", list(_TRIMESTRES), default="1",
            format_func=lambda k: f"T{k}", key=f"trimestre_{tramite}",
        )
    with col_mes:
        nombre_mes = st.segmented_control(
            "Mes", _TRIMESTRES[trimestre or "1"], default=_TRIMESTRES[trimestre or "1"][0],
            key=f"mes_{tramite}_{trimestre or '1'}",
        )

    def refrescar_avance() -> None:
        with zona_avance:
            _render_avance(servicio, tramite, anio)

    if not trimestre or not nombre_mes:
        refrescar_avance()
        st.caption("Selecciona un trimestre y un mes para diligenciar el cargue.")
        return
    mes = (int(trimestre) - 1) * 3 + _TRIMESTRES[trimestre].index(nombre_mes) + 1

    guardado = servicio.obtener_mes(tramite, anio, mes)
    previos = (guardado or {}).get("valores", {})

    # Versión del mes que el usuario está viendo (para detectar ediciones de otra persona).
    # Los campos conservan lo digitado entre reruns; si aún no existen, parten de lo guardado.
    prefijo = f"{tramite}_{anio}_{mes}_"
    clave_version = f"suit_version_{prefijo}"
    if f"{prefijo}{CAMPOS_SUIT[0]['id']}" not in st.session_state:
        st.session_state[clave_version] = (guardado or {}).get("actualizado_en")

    def recargar_guardado() -> None:
        for campo in CAMPOS_SUIT:
            st.session_state.pop(f"{prefijo}{campo['id']}", None)
        st.session_state.pop(clave_version, None)

    if guardado:
        actualizado = utc_a_bogota(guardado["actualizado_en"]).strftime("%d/%m/%Y %H:%M")
        st.caption(f":material/history: Último guardado: {actualizado} por {guardado.get('actualizado_por', '—')}")
    else:
        st.caption(f":material/edit_note: {nombre_mes} {anio} aún no se ha cargado.")

    valores: dict[str, int] = {}
    for col, (seccion, (titulo, icono)) in zip(st.columns(2), _SECCIONES.items()):
        with col.container(border=True, height="stretch"):
            st.markdown(f"**{icono} {titulo}**")
            for campo in (c for c in CAMPOS_SUIT if c["seccion"] == seccion):
                valores[campo["id"]] = int(st.number_input(
                    campo["etiqueta"], min_value=0, value=int(previos.get(campo["id"], 0)),
                    step=1, format="%d", key=f"{tramite}_{anio}_{mes}_{campo['id']}",
                ))
            # Totales calculados de esta tarjeta (no se digitan ni se guardan).
            totales = servicio.totales(valores)
            for clave, total in TOTALES_SUIT.items():
                if total["seccion"] == seccion:
                    st.metric(total["etiqueta"], totales[clave], help=total["ayuda"], border=True)

    with st.container(horizontal=True, horizontal_alignment="right"):
        guardar = st.button("Guardar cargue", icon=":material/save:", type="primary",
                            key=f"guardar_{tramite}_{anio}_{mes}")

    if guardar:
        try:
            accion = servicio.guardar_mes(
                tramite, anio, mes, valores,
                actor=sesion.get("usuario", "sistema"),
                permisos_actor=permisos_efectivos(sesion),
                actor_id=sesion.get("id"),
                version_esperada=st.session_state.get(clave_version),
            )
        except ErrorConflictoSuit as e:
            st.warning(str(e))
            st.button("Recargar valores guardados", icon=":material/refresh:",
                      on_click=recargar_guardado, key=f"recargar_{prefijo}")
        except (ErrorSuit, ValidacionAutorizacion) as e:
            st.warning(str(e))
        except Exception as e:
            st.error(f"No se pudo guardar el cargue: {e}")
        else:
            st.session_state[clave_version] = (servicio.obtener_mes(tramite, anio, mes) or {}).get("actualizado_en")
            seguimiento_suit.clear()  # el tablero de Seguimiento debe reflejar este guardado
            st.toast(f"Cargue de {nombre_mes} {anio} {accion} correctamente.", icon=":material/check_circle:")
    refrescar_avance()


def _render_cargue(sesion: dict) -> None:
    tramites = [t for t in TRAMITES_SUIT if t in set(sesion.get("suit_tramites", []))]
    if not tramites:
        st.info(
            "No tienes ningún trámite SUIT asignado. Solicita acceso a un administrador "
            "o al líder del grupo de Permisos."
        )
        return

    tramite = st.selectbox(
        "Trámite", tramites, format_func=lambda t: TRAMITES_SUIT[t]["label_corto"], key="suit_tramite",
    )
    st.subheader(TRAMITES_SUIT[tramite]["nombre_completo"], divider="gray")
    _render_formulario(tramite, sesion)


def render(sesion=None) -> None:
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    mostrar_titulo_decorado("SUIT")
    st.caption("Sistema Unificado de Información de Trámites · Cargue de PQRD, independiente de Correspondencia.")

    tab_cargue, tab_seguimiento, tab_reporte = st.tabs([
        ":material/upload_file: Cargue",
        ":material/query_stats: Seguimiento",
        ":material/summarize: Reporte",
    ])
    with tab_cargue:
        _render_cargue(sesion)
    with tab_seguimiento:
        render_seguimiento(sesion)
    with tab_reporte:
        render_reporte(sesion)


# Punto de entrada cuando Streamlit carga la página directamente
render(obtener_sesion())
