"""Panel de administración de parámetros del sistema – SRTI INVIAS.

Permite al administrador ajustar valores que afectan el comportamiento del
sistema (p. ej. el día de inicio del período de certificación). Cada cambio:
  - se valida contra el rango permitido del parámetro,
  - exige confirmación explícita mostrando valor actual → nuevo + impacto,
  - queda registrado en auditoría.

Los parámetros se definen de forma declarativa en ParametrosService.PARAMETROS;
esta página los renderiza genéricamente.
"""

import streamlit as st

from app.core.sesion import obtener_sesion
from app.core.ui_titulos import mostrar_titulo_decorado
from app.core.cache_datos import limpiar_cache_lecturas
from app.services.opciones_service import OpcionesService
from app.services.parametros_service import ParametrosService, PARAMETROS


def _texto_valor(meta: dict, valor):
    """Valor legible de un parámetro (la etiqueta, si es de tipo 'opcion')."""
    if meta["tipo"] == "opcion":
        return meta["opciones"].get(valor, valor)
    return valor


# ── Diálogo de confirmación ──────────────────────────────────────────────────

@st.dialog("Confirmar cambio de parámetro", width="small")
def _dialog_confirmar(servicio: ParametrosService, sesion: dict) -> None:
    pend = st.session_state.get("_param_pendiente")
    if not pend:
        return

    clave = pend["clave"]
    nuevo = pend["valor"]
    meta = PARAMETROS[clave]
    actual = servicio.obtener(clave)

    st.markdown(f"**Parámetro:** {meta['etiqueta']}")
    if meta["tipo"] == "opcion":
        # st.metric recorta los textos largos de las opciones.
        st.markdown(f"**Valor actual:** {_texto_valor(meta, actual)}")
        st.markdown(f"**Nuevo valor:** {_texto_valor(meta, nuevo)}")
    else:
        c1, c2 = st.columns(2)
        c1.metric("Valor actual", actual)
        c2.metric("Nuevo valor", nuevo)

    st.warning(f"⚠️ **Impacto:** {meta['impacto']}")
    st.divider()

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Confirmar cambio", type="primary", use_container_width=True):
            usuario = sesion.get("usuario") or "sistema"
            try:
                servicio.actualizar(clave, nuevo, usuario)
                st.session_state.pop("_param_pendiente", None)
                st.session_state["_param_msg"] = (
                    f"'{meta['etiqueta']}' actualizado a **{_texto_valor(meta, nuevo)}**."
                )
                limpiar_cache_lecturas()
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    with b2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("_param_pendiente", None)
            st.rerun()


# ── Render principal ─────────────────────────────────────────────────────────

def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    es_admin = any(r in {"admin", "administrador"} for r in sesion.get("roles", []))
    if not es_admin:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    servicio = ParametrosService()

    mostrar_titulo_decorado("Parámetros del sistema")
    st.caption(
        "Valores que afectan el comportamiento del sistema. Los cambios requieren "
        "confirmación y quedan registrados en auditoría."
    )

    msg = st.session_state.pop("_param_msg", None)
    if msg:
        st.success(msg)

    for clave, meta in PARAMETROS.items():
        actual = servicio.obtener(clave)
        deshabilitado = not meta.get("habilitado", True)
        with st.container(border=True):
            st.markdown(f"**{meta['etiqueta']}**")
            st.caption(meta["descripcion"])
            if deshabilitado:
                st.info("🔒 Parámetro deshabilitado temporalmente: no admite cambios desde este panel.")

            col_in, col_btn = st.columns([3, 1])
            with col_in:
                if meta["tipo"] == "int":
                    nuevo = st.number_input(
                        meta.get("unidad", "Valor"),
                        min_value=meta["min"],
                        max_value=meta["max"],
                        value=int(actual),
                        step=1,
                        key=f"inp_{clave}",
                        disabled=deshabilitado,
                    )
                elif meta["tipo"] == "opcion":
                    claves_opcion = list(meta["opciones"])
                    nuevo = st.selectbox(
                        meta.get("unidad", "Valor"),
                        options=claves_opcion,
                        index=claves_opcion.index(actual),
                        format_func=lambda k, _op=meta["opciones"]: _op[k],
                        key=f"inp_{clave}",
                        disabled=deshabilitado,
                    )
                elif meta["tipo"] == "bool":
                    nuevo = st.checkbox(
                        meta.get("unidad", "Activo"),
                        value=bool(actual),
                        key=f"inp_{clave}",
                        disabled=deshabilitado,
                    )
                else:
                    nuevo = st.text_input(
                        meta.get("unidad", "Valor"),
                        value=str(actual),
                        key=f"inp_{clave}",
                        disabled=deshabilitado,
                    )
            with col_btn:
                st.write("")
                st.write("")
                sin_cambio = nuevo == actual
                if st.button(
                    "Guardar",
                    key=f"btn_{clave}",
                    use_container_width=True,
                    disabled=deshabilitado or sin_cambio,
                ):
                    st.session_state["_param_pendiente"] = {"clave": clave, "valor": nuevo}
                    st.rerun()

            if meta["tipo"] == "int":
                st.caption(
                    f"Valor actual: **{actual}** · Rango permitido: {meta['min']}–{meta['max']}"
                )
            else:
                st.caption(
                    f"Valor actual: **{_texto_valor(meta, actual)}**"
                )

    if st.session_state.get("_param_pendiente"):
        _dialog_confirmar(servicio, sesion)

    st.divider()
    with st.container(border=True):
        st.markdown("**Caché de catálogos (opciones de configuración)**")
        st.caption(
            "Los catálogos como EPS, ARL, bancos, etc. se cachean en memoria mientras "
            "la aplicación está en ejecución. Si agregaste o editaste una opción "
            "directamente en la base de datos, límpiala aquí para que se refleje sin "
            "reiniciar el servidor."
        )
        if st.button("Limpiar caché de catálogos", key="btn_limpiar_cache_opciones"):
            OpcionesService().limpiar_cache()
            limpiar_cache_lecturas()
            st.success("Caché de catálogos limpiada. Los cambios en la base de datos ya se reflejarán.")

