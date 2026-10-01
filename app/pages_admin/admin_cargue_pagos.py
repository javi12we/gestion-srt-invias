"""Cargue masivo de pagos de contratos desde el Excel de tesorería.

Flujo: subir archivo -> clasificar en memoria (sin tocar Mongo) -> el admin
revisa/ajusta la selección de filas "válido" -> confirma -> se escribe solo
lo seleccionado. Ver docs/superpowers/specs/2026-09-30-cargue-pagos-excel-design.md.
"""

import streamlit as st

from app.core.sesion import obtener_sesion
from app.core.ui_titulos import mostrar_titulo_decorado
from app.services.cargue_pagos_service import CarguePagosService, CAT_VALIDO

_ETIQUETAS_CATEGORIA = {
    "valido": "✅ Válido",
    "duplicado_interno": "⚠️ Duplicado en el archivo",
    "usuario_no_encontrado": "❌ Usuario no encontrado",
    "sin_contrato_activo": "❌ Sin contrato activo",
    "dato_invalido": "❌ Dato inválido",
    "ya_existe_en_bd": "ℹ️ Ya existe en BD",
    "excede_limite_pagos": "❌ Excede límite de 20 pagos",
}


@st.dialog("Confirmar carga de pagos", width="large")
def _dialog_confirmar(servicio: CarguePagosService, filas_marcadas: list, sesion: dict) -> None:
    contratos_afectados = {(f["id_usuario"], f["numero_contrato"]) for f in filas_marcadas}
    st.markdown(f"Se van a cargar **{len(filas_marcadas)} pagos** en **{len(contratos_afectados)} contratos**.")
    st.warning("Esta acción escribe en la base de datos. No se eliminará ni modificará ningún pago existente.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmar carga", type="primary", use_container_width=True):
            usuario_sesion = sesion.get("usuario") or "admin"
            resultado = servicio.confirmar_carga(filas_marcadas, usuario_que_carga=usuario_sesion)
            st.session_state["_cargue_pagos_resultado"] = resultado
            st.session_state.pop("_cargue_pagos_datos", None)
            st.session_state.pop("_cargue_pagos_archivo_clave", None)
            st.session_state.pop("_cargue_pagos_confirmar", None)
            st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("_cargue_pagos_confirmar", None)
            st.rerun()


def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()
    if "pago.cargar" not in sesion.get("permisos", []):
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    mostrar_titulo_decorado("Cargue de pagos desde Excel")
    st.caption(
        "Sube el Excel de tesorería (.xlsx/.xlsm). El archivo se valida y clasifica "
        "en memoria; nada se guarda hasta que confirmes explícitamente la carga."
    )

    resultado_previo = st.session_state.pop("_cargue_pagos_resultado", None)
    if resultado_previo:
        if resultado_previo["ok"]:
            total_agregados = sum(r["agregados"] for r in resultado_previo["ok"])
            st.success(f"✅ Se cargaron {total_agregados} pagos en {len(resultado_previo['ok'])} contratos.")
        for fallo in resultado_previo["fallidos"]:
            st.error(f"❌ Contrato {fallo['numero_contrato']}: {fallo['motivo']}")

    archivo = st.file_uploader("Archivo de pagos", type=["xlsx", "xlsm"], key="_cargue_pagos_uploader")

    servicio = CarguePagosService()

    if archivo is not None:
        clave_archivo = f"{archivo.name}_{archivo.size}"
        if st.session_state.get("_cargue_pagos_archivo_clave") != clave_archivo:
            try:
                datos = servicio.procesar_archivo(archivo)
            except Exception as e:
                st.error(f"No se pudo procesar el archivo: {e}")
                st.stop()
            st.session_state["_cargue_pagos_datos"] = datos
            st.session_state["_cargue_pagos_archivo_clave"] = clave_archivo

    datos = st.session_state.get("_cargue_pagos_datos")
    if not datos:
        return

    resumen = datos["resumen"]
    cols = st.columns(len(_ETIQUETAS_CATEGORIA))
    for col, (cat, etiqueta) in zip(cols, _ETIQUETAS_CATEGORIA.items()):
        col.metric(etiqueta, resumen.get(cat, 0))

    st.divider()
    st.markdown("**Detalle de registros** — solo puedes marcar los que están en estado Válido.")

    filas_validas = [f for f in datos["filas"] if f["categoria"] == CAT_VALIDO]
    filas_otras = [f for f in datos["filas"] if f["categoria"] != CAT_VALIDO]

    seleccion = {}
    clave_archivo_actual = st.session_state.get("_cargue_pagos_archivo_clave", "")
    for fila in filas_validas:
        etiqueta = (
            f"{fila['nombre']} (CC {fila['cedula']}) · contrato {fila['numero_contrato']} · "
            f"{fila['numero_pago']} · ${fila['valor_neto_pago']:,} · {fila['concepto'][:60]}"
        )
        seleccion[fila["id"]] = st.checkbox(
            etiqueta, value=True, key=f"_cargue_pagos_fila_{clave_archivo_actual}_{fila['id']}"
        )

    if filas_otras:
        with st.expander(f"Registros con error o informativos ({len(filas_otras)})"):
            for fila in filas_otras:
                st.text(
                    f"[{_ETIQUETAS_CATEGORIA[fila['categoria']]}] CC {fila['cedula']} · "
                    f"{fila['motivo']}"
                )

    filas_marcadas = [f for f in filas_validas if seleccion.get(f["id"])]

    st.divider()
    if st.button(f"Confirmar carga ({len(filas_marcadas)} pagos seleccionados)", type="primary", disabled=not filas_marcadas):
        st.session_state["_cargue_pagos_confirmar"] = filas_marcadas

    if st.session_state.get("_cargue_pagos_confirmar"):
        _dialog_confirmar(servicio, st.session_state["_cargue_pagos_confirmar"], sesion)
