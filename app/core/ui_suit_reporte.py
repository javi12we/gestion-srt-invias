"""Reporte SUIT: resumen del año y descarga del Excel «DATOS DE OPERACIÓN SUIT».

Lo ve y lo descarga cualquiera que vea el SUIT. El resumen sale del mismo cálculo del
Seguimiento (``cache_datos.seguimiento_suit``); el libro se genera solo al pulsar
«Descargar» (``SuitService.generar_reporte_excel``), no en cada recarga de la página.
"""

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from app.core.autorizacion import ValidacionAutorizacion
from app.core.cache_datos import seguimiento_suit
from app.core.catalogos import TRAMITES_SUIT
from app.core.zona_horaria import utc_a_bogota
from app.services.suit_excel_service import ANIO_FINAL_PLANTILLA
from app.services.suit_service import SuitService, permisos_efectivos

_TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _total(serie: dict, campo: str) -> int:
    return sum(v for v in serie[campo] if v is not None)


def _resumen(datos: dict) -> pd.DataFrame:
    """Una fila por trámite con los totales del año."""
    filas = []
    for t in datos["tramites"]:
        serie = datos["indicadores"][t["tramite"]]
        filas.append({
            "Trámite": t["nombre"],
            "Meses cargados": f"{t['cargados']}/12",
            "Solicitudes resueltas": _total(serie, "solicitudes_linea") + _total(serie, "solicitudes_presencial"),
            "PQRD recibidas": _total(serie, "pqrd_recibidas"),
            "Quejas": _total(serie, "quejas"),
            "Reclamos": _total(serie, "reclamos"),
            "Denuncias": _total(serie, "denuncias"),
        })
    return pd.DataFrame(filas)


def render_reporte(sesion: dict) -> None:
    anio_actual = utc_a_bogota(datetime.now(timezone.utc)).year
    anio = st.selectbox(
        "Año del reporte", list(range(anio_actual, ANIO_FINAL_PLANTILLA - 1, -1)), key="suit_rep_anio",
    )
    permisos = tuple(permisos_efectivos(sesion))

    try:
        datos = seguimiento_suit(anio, sesion.get("id"), permisos)
    except ValidacionAutorizacion as e:
        st.warning(str(e))
        return
    except Exception as e:
        st.error(f"Error al cargar el reporte: {e}")
        return

    st.markdown(f"**Resumen {anio} por trámite**")
    resumen = _resumen(datos)
    st.dataframe(resumen, hide_index=True, width="stretch")
    if not any(t["cargados"] for t in datos["tramites"]):
        st.caption(f"Aún no hay cargues en {anio}: el Excel saldrá con las tablas vacías.")

    servicio, id_usuario = SuitService(), sesion.get("id")

    def generar() -> bytes:
        # Se ejecuta al pulsar «Descargar», en otro hilo: no puede usar comandos de Streamlit.
        return servicio.generar_reporte_excel(anio, id_usuario, list(permisos))

    st.download_button(
        f"Descargar Excel SUIT {anio}", data=generar,
        file_name=f"DATOS_DE_OPERACION_SUIT_{anio}.xlsx", mime=_TIPO_XLSX,
        icon=":material/download:", type="primary", key=f"suit_descarga_{anio}",
    )
    st.caption(
        f"El libro trae la hoja «SUIT {anio}» con los {len(TRAMITES_SUIT)} trámites (con sus totales y porcentajes "
        f"calculados) y la hoja «Historico (consulta)» con las tablas y gráficos de 2017 a {anio}."
    )
