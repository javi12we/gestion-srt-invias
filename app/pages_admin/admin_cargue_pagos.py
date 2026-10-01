"""Sección de cargue masivo de pagos de contratos desde el Excel de tesorería.

Se muestra en Config Formatos, dentro del formato "3- Balance General CPS".
Flujo: subir archivo -> clasificar en memoria (sin tocar Mongo) -> el admin
revisa/ajusta la selección de pagos nuevos y a sobrescribir -> confirma -> se
escribe solo lo seleccionado. Ver docs/cargue_pagos_excel.md.
"""

import pandas as pd
import streamlit as st

from app.core.cache_datos import limpiar_cache_lecturas
from app.services.cargue_pagos_service import (
    CarguePagosService,
    CATEGORIAS_CARGABLES,
    CAT_VALIDO,
    CAT_ACTUALIZA,
    CAT_DUPLICADO_INTERNO,
    CAT_USUARIO_NO_ENCONTRADO,
    CAT_CONTRATO_NO_ENCONTRADO,
    CAT_DATO_INVALIDO,
    CAT_YA_EXISTE,
    CAT_EXCEDE_LIMITE,
)

_ETIQUETAS_CATEGORIA = {
    CAT_VALIDO: "✅ Nuevo",
    CAT_ACTUALIZA: "🔄 Sobrescribe existente",
    CAT_YA_EXISTE: "ℹ️ Sin cambios",
    CAT_DUPLICADO_INTERNO: "⚠️ Duplicado en el archivo",
    CAT_USUARIO_NO_ENCONTRADO: "❌ Usuario no encontrado",
    CAT_CONTRATO_NO_ENCONTRADO: "❌ Contrato no encontrado",
    CAT_DATO_INVALIDO: "❌ Dato inválido",
    CAT_EXCEDE_LIMITE: "❌ Excede límite de 20 pagos",
}

_CLAVES_ESTADO = (
    "_cargue_pagos_datos",
    "_cargue_pagos_archivo_clave",
    "_cargue_pagos_archivo_nombre",
    "_cargue_pagos_confirmar",
)


def _cerrar_dialogo_confirmar() -> None:
    st.session_state.pop("_cargue_pagos_confirmar", None)


# on_dismiss: sin él, cerrar el diálogo con la X dejaba la bandera puesta y el
# diálogo volvía a abrirse solo en el siguiente rerun.
@st.dialog("Confirmar carga de pagos", width="large", on_dismiss=_cerrar_dialogo_confirmar)
def _dialog_confirmar(
    servicio: CarguePagosService, filas_marcadas: list, sesion: dict, nombre_archivo: str
) -> None:
    contratos_afectados = {(f["id_usuario"], f["numero_contrato"]) for f in filas_marcadas}
    nuevos = sum(1 for f in filas_marcadas if f["categoria"] == CAT_VALIDO)
    sobrescritos = len(filas_marcadas) - nuevos
    st.markdown(
        f"Se van a cargar **{nuevos} pagos nuevos** y a sobrescribir **{sobrescritos} pagos "
        f"existentes** en **{len(contratos_afectados)} contratos**."
    )
    st.warning(
        "Esta acción escribe en la base de datos. Los pagos existentes con el mismo número "
        "de pago se reemplazan con los datos del Excel; no se elimina ningún pago."
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmar carga", type="primary", use_container_width=True):
            usuario_sesion = sesion.get("usuario") or "admin"
            try:
                resultado = servicio.confirmar_carga(
                    filas_marcadas, usuario_que_carga=usuario_sesion, nombre_archivo=nombre_archivo
                )
            except Exception as e:
                st.error(f"No se pudo completar la carga: {e}")
            else:
                st.session_state["_cargue_pagos_resultado"] = resultado
                for clave in _CLAVES_ESTADO:
                    st.session_state.pop(clave, None)
                limpiar_cache_lecturas()
                st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("_cargue_pagos_confirmar", None)
            st.rerun()


def render_seccion(sesion: dict) -> None:
    if "pago.cargar" not in sesion.get("permisos", []):
        return

    en_curso = bool(
        st.session_state.get("_cargue_pagos_datos") or st.session_state.get("_cargue_pagos_resultado")
    )
    with st.expander("💰 Cargue de pagos desde Excel de tesorería", expanded=en_curso):
        _render_contenido(sesion)


def _render_contenido(sesion: dict) -> None:
    st.caption(
        "Sube el Excel de tesorería (.xlsx/.xlsm). Cada pago se asigna al contrato indicado en "
        "la columna «Num Doc Soporte Compromiso» (número/año), esté vigente o finalizado. El "
        "archivo se valida y clasifica en memoria; nada se guarda hasta que confirmes la carga."
    )

    resultado_previo = st.session_state.pop("_cargue_pagos_resultado", None)
    if resultado_previo:
        if resultado_previo["ok"]:
            total_agregados = sum(r["agregados"] for r in resultado_previo["ok"])
            total_actualizados = sum(r["actualizados"] for r in resultado_previo["ok"])
            st.success(
                f"✅ Se cargaron {total_agregados} pagos nuevos y se sobrescribieron "
                f"{total_actualizados} en {len(resultado_previo['ok'])} contratos."
            )
        for fallo in resultado_previo["fallidos"]:
            st.error(f"❌ Contrato {fallo['numero_contrato']}: {fallo['motivo']}")
        if not resultado_previo["ok"] and not resultado_previo["fallidos"]:
            st.info(
                "No se cargó ningún pago: todos los seleccionados ya estaban iguales en la base de datos."
            )

    archivo = st.file_uploader("Archivo de pagos", type=["xlsx", "xlsm"], key="_cargue_pagos_uploader")

    servicio = CarguePagosService()

    if archivo is not None:
        clave_archivo = f"{archivo.name}_{archivo.size}"
        if st.session_state.get("_cargue_pagos_archivo_clave") != clave_archivo:
            try:
                datos = servicio.procesar_archivo(archivo)
            except Exception as e:
                st.error(f"No se pudo procesar el archivo: {e}")
                return
            st.session_state["_cargue_pagos_datos"] = datos
            st.session_state["_cargue_pagos_archivo_clave"] = clave_archivo
            st.session_state["_cargue_pagos_archivo_nombre"] = archivo.name

    datos = st.session_state.get("_cargue_pagos_datos")
    if not datos:
        return

    resumen = datos["resumen"]
    if sum(resumen.values()) == 0:
        st.warning(
            "No se encontró ninguna fila con Tipo Identificacion = 'Cédula de Ciudadanía' en "
            "este archivo. Verifica que sea el formato esperado del Excel de tesorería."
        )
    etiquetas = list(_ETIQUETAS_CATEGORIA.items())
    for inicio in range(0, len(etiquetas), 4):
        cols = st.columns(4)
        for col, (cat, etiqueta) in zip(cols, etiquetas[inicio:inicio + 4]):
            col.metric(etiqueta, resumen.get(cat, 0))

    st.divider()
    st.markdown(
        "**Detalle de registros** — solo puedes marcar los pagos nuevos y los que sobrescriben "
        "uno existente. Están ordenados por contrato y fecha de pago."
    )

    filas_cargables = sorted(
        (f for f in datos["filas"] if f["categoria"] in CATEGORIAS_CARGABLES),
        key=lambda f: (f["nombre"] or "", f["numero_contrato"], f["orden_pago"]),
    )
    filas_otras = [f for f in datos["filas"] if f["categoria"] not in CATEGORIAS_CARGABLES]

    clave_archivo_actual = st.session_state.get("_cargue_pagos_archivo_clave", "")

    filas_marcadas = []
    if filas_cargables:
        df_cargables = pd.DataFrame(
            [
                {
                    "Cargar": True,
                    "Acción": _ETIQUETAS_CATEGORIA[fila["categoria"]],
                    "Nombre": fila["nombre"],
                    "Cédula": fila["cedula"],
                    "Contrato": fila["contrato_excel"],
                    "Fecha de pago": fila["fecha_pago"].date(),
                    "N° pago": fila["numero_pago"],
                    "Estado": fila["estado"],
                    "Valor bruto": fila["valor_bruto_pago"],
                    "Valor neto": fila["valor_neto_pago"],
                    "Concepto": fila["concepto"][:80],
                }
                for fila in filas_cargables
            ]
        )
        # st.data_editor virtualiza las filas (a diferencia de un st.checkbox por
        # fila), indispensable con el Excel real de tesorería (~25.000 filas tras
        # el filtro de cédula).
        df_editado = st.data_editor(
            df_cargables,
            hide_index=True,
            use_container_width=True,
            disabled=[c for c in df_cargables.columns if c != "Cargar"],
            key=f"_cargue_pagos_editor_{clave_archivo_actual}",
        )
        # st.data_editor preserva el orden original de las filas (ordenar por
        # columna solo cambia la vista), así que esta lista y el DataFrame
        # editado quedan alineados posición a posición.
        filas_marcadas = [
            fila
            for fila, marcado in zip(filas_cargables, df_editado["Cargar"].tolist())
            if marcado
        ]
    else:
        st.info("No hay pagos nuevos ni por sobrescribir en este archivo.")

    # st.toggle y no st.expander: esta sección ya vive dentro de un expander.
    if filas_otras:
        if st.toggle(
            f"Ver registros con error o informativos ({len(filas_otras)})",
            key=f"_cargue_pagos_ver_otras_{clave_archivo_actual}",
        ):
            df_otras = pd.DataFrame(
                [
                    {
                        "Categoría": _ETIQUETAS_CATEGORIA.get(fila["categoria"], fila["categoria"]),
                        "Cédula": fila["cedula"],
                        "Nombre": fila["nombre"],
                        "Contrato": fila["contrato_excel"],
                        "N° pago": fila["numero_pago"],
                        "Motivo": fila["motivo"],
                    }
                    for fila in filas_otras
                ]
            )
            st.dataframe(df_otras, hide_index=True, use_container_width=True)

    st.divider()
    if st.button(
        f"Confirmar carga ({len(filas_marcadas)} pagos seleccionados)",
        type="primary",
        disabled=not filas_marcadas,
        key="_cargue_pagos_btn_confirmar",
    ):
        st.session_state["_cargue_pagos_confirmar"] = filas_marcadas

    if st.session_state.get("_cargue_pagos_confirmar"):
        nombre_archivo = st.session_state.get("_cargue_pagos_archivo_nombre", "")
        _dialog_confirmar(servicio, st.session_state["_cargue_pagos_confirmar"], sesion, nombre_archivo)
