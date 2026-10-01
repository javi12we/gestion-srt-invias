"""Vista del supervisor para configurar los firmantes designados de cada formato.

Requiere el permiso certificacion.aprobar.
La certificación ocurre automáticamente cuando se registran las 3 firmas
y el contratista cumple: sin vencidas + contrato activo.
"""

import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado

from app.core.cache_datos import limpiar_cache_lecturas
from app.core.sesion import obtener_sesion
from app.pages_admin import admin_cargue_pagos
from app.services.certificacion_service import (
    CertificacionService, MESES_ES, TIPOS_FIRMA_ACTAS, ORDEN_FIRMAS_ACTAS, FIRMA_EXTRA_CONFIG,
)

TIPOS_FIRMA = ("corr", "gd", "secop")

_META_FIRMA = {
    "corr":  ("F. Corr",  "Correspondencia"),
    "gd":    ("F. GD",    "Gestión Documental"),
    "secop": ("F. SECOP", "SECOP II"),
}

_META_FIRMA_ACTAS = {
    "financiera": ("F. Financiera", "Financiera"),
    "abogado":    ("F. Jurídica",   "Jurídico"),
    "jefe":       ("F. Jefe",       "Jefe inmediato"),
}

_TITULO_ACTAS = {
    "acta_compromiso": "Acta de compromiso",
    "acta_recibo_entrega_cps": "Balance General CPS",
    "acta_recibo_entrega_cps_real": "Acta de recibo y entrega CPS",
}


# ── Configuración de firmantes (solo admin con gestionar_firmantes) ──

def _seccion_config_firmantes(servicio: CertificacionService, sesion: dict) -> None:
    if "certificacion.gestionar_firmantes" not in sesion.get("permisos", []):
        return

    from app.repositories.usuario_repo import UsuarioRepositorio

    with st.expander("⚙️ Configurar firmantes designados", expanded=False):
        st.caption(
            "Designa qué usuario ejerce cada rol de aprobación. "
            "Al guardar se asigna automáticamente el permiso correspondiente. "
            "El cambio toma efecto la próxima vez que el firmante inicie sesión."
        )

        config = servicio.obtener_firmantes_config()
        usuarios_activos = [u for u in UsuarioRepositorio().listar() if u.get("activo", True)]
        id_a_nombre = {str(u["_id"]): u["nombre_completo"] for u in usuarios_activos}
        opciones_lista = ["(ninguno)"] + sorted(id_a_nombre.values())
        nombre_a_id = {v: k for k, v in id_a_nombre.items()}

        for tipo in TIPOS_FIRMA:
            label_largo = _META_FIRMA[tipo][1]
            actual = config.get(tipo) or {}
            actual_nombre = actual.get("nombre") if actual else None
            idx_actual = 0
            if actual_nombre and actual_nombre in opciones_lista:
                idx_actual = opciones_lista.index(actual_nombre)

            c1, c2 = st.columns([5, 1])
            with c1:
                seleccionado = st.selectbox(
                    f"Firmante · {label_largo}",
                    options=opciones_lista,
                    index=idx_actual,
                    key=f"sel_firmante_{tipo}",
                )
            with c2:
                st.write("")
                if st.button("Guardar", key=f"btn_firmante_{tipo}", use_container_width=True):
                    if seleccionado == "(ninguno)":
                        servicio.guardar_firmante(tipo, None, None)
                        st.success(f"Firmante de {label_largo} eliminado.")
                    else:
                        uid = nombre_a_id.get(seleccionado)
                        if uid:
                            servicio.guardar_firmante(tipo, uid, seleccionado)
                            st.success(f"Firmante de {label_largo}: **{seleccionado}**")
                    limpiar_cache_lecturas()
                    st.rerun()

        if servicio.firma_extra_activa("gestion_correspondencia"):
            tipo_extra = FIRMA_EXTRA_CONFIG["gestion_correspondencia"]["tipo_firmante"]
            config_extra = servicio.obtener_firmantes_config("firmantes_firma_extra", (tipo_extra,))
            actual = config_extra.get(tipo_extra) or {}
            actual_nombre = actual.get("nombre") if actual else None
            idx_actual = 0
            if actual_nombre and actual_nombre in opciones_lista:
                idx_actual = opciones_lista.index(actual_nombre)

            c1, c2 = st.columns([5, 1])
            with c1:
                seleccionado = st.selectbox(
                    "Firmante · Firma Extra",
                    options=opciones_lista,
                    index=idx_actual,
                    key=f"sel_firmante_{tipo_extra}",
                )
            with c2:
                st.write("")
                if st.button("Guardar", key=f"btn_firmante_{tipo_extra}", use_container_width=True):
                    if seleccionado == "(ninguno)":
                        servicio.guardar_firmante(tipo_extra, None, None, categoria="firmantes_firma_extra")
                        st.success("Firmante de Firma Extra eliminado.")
                    else:
                        uid = nombre_a_id.get(seleccionado)
                        if uid:
                            servicio.guardar_firmante(tipo_extra, uid, seleccionado, categoria="firmantes_firma_extra")
                            st.success(f"Firmante de Firma Extra: **{seleccionado}**")
                    limpiar_cache_lecturas()
                    st.rerun()


def _seccion_config_firmantes_actas(servicio: CertificacionService, sesion: dict, tipo_acta_activo: str) -> None:
    if "certificacion.gestionar_firmantes" not in sesion.get("permisos", []):
        return

    from app.repositories.usuario_repo import UsuarioRepositorio

    orden = ORDEN_FIRMAS_ACTAS.get(tipo_acta_activo, TIPOS_FIRMA_ACTAS)
    titulo_formato = _TITULO_ACTAS.get(tipo_acta_activo, "Actas")
    label_roles = " / ".join(_META_FIRMA_ACTAS[r][1] for r in orden)
    expander_title = f"⚙️ Configurar firmantes de {titulo_formato} ({label_roles})"

    with st.expander(expander_title, expanded=False):
        st.caption(
            f"Designa qué usuario ejerce cada rol de aprobación para {titulo_formato}. "
            "Al guardar se asigna automáticamente el permiso correspondiente."
        )

        config = servicio.obtener_firmantes_config("firmantes_formatos_actas", TIPOS_FIRMA_ACTAS)
        usuarios_activos = [u for u in UsuarioRepositorio().listar() if u.get("activo", True)]
        id_a_nombre = {str(u["_id"]): u["nombre_completo"] for u in usuarios_activos}
        opciones_lista = ["(ninguno)"] + sorted(id_a_nombre.values())
        nombre_a_id = {v: k for k, v in id_a_nombre.items()}

        for tipo in orden:
            label_largo = _META_FIRMA_ACTAS[tipo][1]
            actual = config.get(tipo) or {}
            actual_nombre = actual.get("nombre") if actual else None
            idx_actual = 0
            if actual_nombre and actual_nombre in opciones_lista:
                idx_actual = opciones_lista.index(actual_nombre)

            c1, c2 = st.columns([5, 1])
            with c1:
                seleccionado = st.selectbox(
                    f"Firmante · {label_largo}",
                    options=opciones_lista,
                    index=idx_actual,
                    key=f"sel_firmante_actas_{tipo_acta_activo}_{tipo}",
                )
            with c2:
                st.write("")
                if st.button("Guardar", key=f"btn_firmante_actas_{tipo_acta_activo}_{tipo}", use_container_width=True):
                    if seleccionado == "(ninguno)":
                        servicio.guardar_firmante(tipo, None, None, categoria="firmantes_formatos_actas")
                        st.success(f"Firmante de {label_largo} eliminado.")
                    else:
                        uid = nombre_a_id.get(seleccionado)
                        if uid:
                            servicio.guardar_firmante(tipo, uid, seleccionado, categoria="firmantes_formatos_actas")
                            st.success(f"Firmante de {label_largo}: **{seleccionado}**")
                    limpiar_cache_lecturas()
                    st.rerun()

        if servicio.firma_extra_activa(tipo_acta_activo):
            tipo_extra = FIRMA_EXTRA_CONFIG[tipo_acta_activo]["tipo_firmante"]
            config_extra = servicio.obtener_firmantes_config("firmantes_firma_extra", (tipo_extra,))
            actual = config_extra.get(tipo_extra) or {}
            actual_nombre = actual.get("nombre") if actual else None
            idx_actual = 0
            if actual_nombre and actual_nombre in opciones_lista:
                idx_actual = opciones_lista.index(actual_nombre)

            c1, c2 = st.columns([5, 1])
            with c1:
                seleccionado = st.selectbox(
                    "Firmante · Firma Extra",
                    options=opciones_lista,
                    index=idx_actual,
                    key=f"sel_firmante_actas_{tipo_acta_activo}_{tipo_extra}",
                )
            with c2:
                st.write("")
                if st.button("Guardar", key=f"btn_firmante_actas_{tipo_acta_activo}_{tipo_extra}", use_container_width=True):
                    if seleccionado == "(ninguno)":
                        servicio.guardar_firmante(tipo_extra, None, None, categoria="firmantes_firma_extra")
                        st.success("Firmante de Firma Extra eliminado.")
                    else:
                        uid = nombre_a_id.get(seleccionado)
                        if uid:
                            servicio.guardar_firmante(tipo_extra, uid, seleccionado, categoria="firmantes_firma_extra")
                            st.success(f"Firmante de Firma Extra: **{seleccionado}**")
                    limpiar_cache_lecturas()
                    st.rerun()


# ── Render principal ─────────────────────────────────────────────

def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    if "certificacion.aprobar" not in sesion.get("permisos", []):
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    servicio = CertificacionService()
    año, mes = servicio.periodo_certificable()
    nombre_mes = MESES_ES[mes - 1]
    es_anterior = servicio.es_mes_anterior()

    mostrar_titulo_decorado("Config Formatos")
    st.caption("Configura los firmantes designados para cada uno de los formatos.")

    if es_anterior:
        st.warning(
            f"Estás certificando el **mes anterior: {nombre_mes} {año}** "
            f"(ventana disponible hasta el día 28 del mes en curso). "
            f"A partir del día 29 solo podrás certificar el mes actual."
        )
    else:
        st.success(
            f"Período de certificación abierto: **{nombre_mes} {año}** "
            f"(días 29 al fin de mes)"
        )

    # Inicializar estado para mostrar/ocultar el formato de control
    if "ver_formato_control_seg" not in st.session_state:
        st.session_state["ver_formato_control_seg"] = False
    if "tipo_acta_seg_activo" not in st.session_state:
        st.session_state["tipo_acta_seg_activo"] = None

    # Botones de navegación
    st.write("")
    _BOTONES_ACTAS_SEG = [
        ("acta_compromiso", "2- Acta de compromiso"),
        ("acta_recibo_entrega_cps", "3- Balance General CPS"),
        ("acta_recibo_entrega_cps_real", "4- Acta de recibo y entrega CPS"),
    ]
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("1- Supervisión Formato de control Corr-GD-SECOP", type="primary" if st.session_state["ver_formato_control_seg"] else "secondary", use_container_width=True, key="btn_formato_control_seg"):
            st.session_state["ver_formato_control_seg"] = not st.session_state["ver_formato_control_seg"]
            st.session_state["tipo_acta_seg_activo"] = None
            st.rerun()
    for col, (tipo, etiqueta) in zip((col2, col3, col4), _BOTONES_ACTAS_SEG):
        with col:
            activo = st.session_state["tipo_acta_seg_activo"] == tipo
            if st.button(etiqueta, type="primary" if activo else "secondary", use_container_width=True, key=f"btn_seg_{tipo}"):
                st.session_state["tipo_acta_seg_activo"] = None if activo else tipo
                st.session_state["ver_formato_control_seg"] = False
                st.rerun()

    st.write("")

    tipo_acta_activo = st.session_state.get("tipo_acta_seg_activo")
    if tipo_acta_activo:
        _seccion_config_firmantes_actas(servicio, sesion, tipo_acta_activo)
    if tipo_acta_activo == "acta_recibo_entrega_cps":
        admin_cargue_pagos.render_seccion(sesion)

    if st.session_state["ver_formato_control_seg"]:
        # Resumen de firmantes designados
        config_firmantes = servicio.obtener_firmantes_config()
        firmantes_ok = all(config_firmantes.get(t) for t in TIPOS_FIRMA)

        with st.expander("👥 Firmantes designados para este período", expanded=not firmantes_ok):
            if not firmantes_ok:
                st.warning(
                    "Aún no están configurados los 3 firmantes. "
                    "Sin los 3 firmantes no se podrán emitir certificaciones. "
                    "Configúralos en el panel ⚙️ que aparece más abajo."
                )
            for tipo in TIPOS_FIRMA:
                dato = config_firmantes.get(tipo)
                label_largo = _META_FIRMA[tipo][1]
                if dato and dato.get("nombre"):
                    st.markdown(f"- ✅ **{label_largo}:** {dato['nombre']}")
                else:
                    st.markdown(f"- ❌ **{label_largo}:** *(sin designar)*")

            if servicio.firma_extra_activa("gestion_correspondencia"):
                tipo_extra = FIRMA_EXTRA_CONFIG["gestion_correspondencia"]["tipo_firmante"]
                dato_extra = servicio.obtener_firmantes_config(
                    "firmantes_firma_extra", (tipo_extra,)
                ).get(tipo_extra)
                if dato_extra and dato_extra.get("nombre"):
                    st.markdown(f"- ✅ **Firma Extra:** {dato_extra['nombre']}")
                else:
                    st.markdown("- ❌ **Firma Extra:** *(sin designar)*")

        _seccion_config_firmantes(servicio, sesion)
