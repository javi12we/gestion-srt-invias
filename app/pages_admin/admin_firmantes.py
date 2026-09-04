"""Módulo de aprobaciones de certificaciones – SRTI INVIAS.

Accesible para los 3 firmantes designados y para el administrador.
  - Firmantes: pueden aprobar o revocar su tipo de firma específico.
  - Admin: vista de solo lectura + gestión de quiénes son los firmantes.
"""

import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado

from app.core.sesion import obtener_sesion
from app.core.ui_certificado import obtener_pdf_certificado_cacheado
from app.core.zona_horaria import formato_fecha_bogota
from app.services.certificacion_service import CertificacionService, MESES_ES, ORDEN_FIRMAS_ACTAS, TIPOS_FIRMA_ACTAS

TIPOS_FIRMA = ("corr", "gd", "secop")

_META_FIRMA = {
    "corr":   ("F. Corr",  "Correspondencia",        "certificacion.firmar_corr"),
    "gd":     ("F. GD",    "Gestión Documental",      "certificacion.firmar_gd"),
    "secop":  ("F. SECOP", "SECOP II",                "certificacion.firmar_secop"),
}

MAPA_TIPOS_CONTRATO = {
    "termino_indefinido": "Término indefinido",
    "termino_fijo": "Término fijo",
    "obra_labor": "Obra o labor",
    "prestacion_servicios": "Prestación de servicios",
    "aprendizaje": "Aprendizaje",
}

_LABEL_FORMATO_ACTAS = {
    "acta_compromiso": "Acta de compromiso",
    "acta_recibo_entrega_cps": "Balance General CPS",
    "acta_recibo_entrega_cps_real": "Acta de recibo y entrega CPS",
}

_META_FIRMA_ACTAS = {
    "financiera": ("F. Financiera", "Financiera",    "certificacion.firmar_financiera"),
    "abogado":    ("F. Jurídica",   "Jurídico",       "certificacion.firmar_abogado"),
    "jefe":       ("F. Jefe",       "Jefe inmediato", "certificacion.firmar_jefe"),
}


# ── Helpers de badges ────────────────────────────────────────────

def _badge_firma(tipo: str, firma: dict | None) -> str:
    label = _META_FIRMA[tipo][0]
    if firma:
        bg, fg, bd = "#1b4721", "#75db8b", "#2d7a3e"
        icono = "✅"
    else:
        bg, fg, bd = "#2c2c2c", "#aaaaaa", "#444"
        icono = "⏳"
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
        f'border-radius:4px;padding:1px 8px;font-size:.76em;font-weight:700;">'
        f"{icono} {label}</span>"
    )


def _badge_corr(pendientes: int, vencidas: int) -> str:
    if pendientes == 0:
        bg, fg, bd = "#1b4721", "#75db8b", "#2d7a3e"
        txt = "✅ Al Día"
    elif vencidas > 0:
        bg, fg, bd = "#511c1e", "#ff9ca2", "#8a2d32"
        txt = f"❌ {pendientes} pend. ({vencidas} venc.)"
    else:
        bg, fg, bd = "#4d3d0f", "#ffe69c", "#7a6010"
        txt = f"⚠️ {pendientes} pend."
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
        f'border-radius:4px;padding:2px 8px;font-size:.78em;font-weight:700;">'
        f"{txt}</span>"
    )


def _badge_firma_actas(rol: str, firma: dict | None) -> str:
    label = _META_FIRMA_ACTAS[rol][0]
    if firma:
        bg, fg, bd = "#1b4721", "#75db8b", "#2d7a3e"
        icono = "✅"
    else:
        bg, fg, bd = "#2c2c2c", "#aaaaaa", "#444"
        icono = "⏳"
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
        f'border-radius:4px;padding:1px 8px;font-size:.76em;font-weight:700;">'
        f"{icono} {label}</span>"
    )


def _cerrar_dialogo_confirmar_firma_actas() -> None:
    st.session_state.pop("_confirmar_firma_actas", None)


@st.dialog("Confirmar aprobación", width="small", on_dismiss=_cerrar_dialogo_confirmar_firma_actas)
def _dialog_confirmar_firma_actas(servicio: CertificacionService, sesion: dict) -> None:
    pend = st.session_state.get("_confirmar_firma_actas")
    if not pend:
        return

    uid = pend["uid"]
    nombre = pend["nombre"]
    tipo_formato = pend["tipo_formato"]
    rol = pend["rol"]
    _, label_largo, _ = _META_FIRMA_ACTAS[rol]

    st.markdown(f"**Firma:** {label_largo}")
    st.markdown(f"**Formato:** {_LABEL_FORMATO_ACTAS[tipo_formato]}")
    st.markdown(f"**Contratista:** {nombre}")
    st.divider()

    comentario = st.text_area(
        "Comentario (opcional)",
        placeholder="Ej: se aprueba con observaciones...",
        key=f"txt_comentario_actas_{uid}_{tipo_formato}_{rol}",
    )

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmar aprobación", type="primary", use_container_width=True, key="btn_confirmar_actas"):
            firmante_nombre = sesion.get("nombre_completo") or sesion["usuario"]
            try:
                cert_id = pend.get("cert_id")
                if not cert_id:
                    raise ValueError("No se encontró el ID del documento en la sesión.")
                servicio.registrar_firma_actas(cert_id, rol, sesion["id"], firmante_nombre, comentario)
            except ValueError as e:
                st.error(str(e))
            else:
                st.session_state.pop("_confirmar_firma_actas", None)
                st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True, key="btn_cancelar_actas"):
            st.session_state.pop("_confirmar_firma_actas", None)
            st.rerun()

def _cerrar_dialogo_borrador() -> None:
    st.session_state.pop("ver_borrador_acta", None)

@st.dialog("Borrador del Formato", width="large", on_dismiss=_cerrar_dialogo_borrador)
def _dialog_ver_borrador(servicio: CertificacionService) -> None:
    info = st.session_state.get("ver_borrador_acta")
    if not info:
        return
    
    cert = info["cert"]
    nombre = info["nombre"]
    tipo_formato = info["tipo_formato"]
    nombre_mes = info["nombre_mes"]
    año = info["año"]
    
    with st.spinner("Generando borrador del PDF…"):
        try:
            pdf_bytes = servicio.generar_pdf(cert)
        except Exception as e:
            st.error(f"Error al generar el borrador: {str(e)}")
            return
            
    prefijos_archivo = {
        "acta_compromiso": "Acta_Compromiso",
        "acta_recibo_entrega_cps": "Balance_General_CPS",
        "acta_recibo_entrega_cps_real": "Acta_Recibo_Entrega_CPS",
    }
    prefijo = prefijos_archivo.get(tipo_formato, "Acta")
    
    st.write(f"Previsualización del borrador para **{nombre}** ({nombre_mes} {año})")
    
    from streamlit_pdf_viewer import pdf_viewer
    pdf_viewer(input=pdf_bytes, width=700, height=600)
    
    st.download_button(
        "⬇️ Descargar Borrador",
        data=pdf_bytes,
        file_name=f"BORRADOR_{prefijo}_{nombre.replace(' ', '_')}_{nombre_mes}_{año}.pdf",
        mime="application/pdf",
        key=f"dl_borrador_{tipo_formato}_{cert['_id']}",
        use_container_width=True,
    )

# ── Diálogo de confirmación de firma (aplica a los 3 tipos) ──────

def _cerrar_dialogo_confirmar_firma() -> None:
    st.session_state.pop("_confirmar_firma", None)


@st.dialog("Confirmar aprobación", width="small", on_dismiss=_cerrar_dialogo_confirmar_firma)
def _dialog_confirmar_firma(
    servicio: CertificacionService, sesion: dict, año: int, mes: int, nombre_mes: str
) -> None:
    pend = st.session_state.get("_confirmar_firma")
    if not pend:
        return

    uid = pend["uid"]
    nombre = pend["nombre"]
    tipo = pend["tipo"]
    _, label_largo, _ = _META_FIRMA[tipo]

    st.markdown(f"**Firma:** {label_largo}")
    st.markdown(f"**Contratista:** {nombre}")
    st.markdown(f"**Período a certificar:** {nombre_mes} {año}")
    st.divider()

    if tipo == "corr":
        from app.services.correspondencia_service import CorrespondenciaService

        with st.spinner("Consultando correspondencia del período…"):
            stats = CorrespondenciaService().obtener_correspondencia_del_periodo(uid, año, mes)

        pendientes = stats["pendientes"]
        vencidas = stats["vencidas"]

        if pendientes == 0:
            st.success("✅ Esta persona está al día en correspondencia para este período.")
        elif vencidas > 0:
            st.error(
                f"⚠️ Esta persona tiene **{pendientes} solicitud(es)** con vencimiento en {nombre_mes} {año}, "
                f"de las cuales **{vencidas} están vencidas**.\n\n"
                "Al aprobar, aceptas la responsabilidad de esta decisión como firmante de Correspondencia."
            )
        else:
            st.warning(
                f"⚠️ Esta persona tiene **{pendientes} solicitud(es) pendiente(s)** con vencimiento en "
                f"{nombre_mes} {año} (ninguna vencida aún)."
            )
        st.divider()

    comentario = st.text_area(
        "Comentario (opcional)",
        placeholder="Ej: se aprueba con pendientes, ponerse al día en...",
        key=f"txt_comentario_firma_{uid}_{tipo}",
    )

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmar aprobación", type="primary", use_container_width=True):
            firmante_nombre = sesion.get("nombre_completo") or sesion["usuario"]
            servicio.registrar_firma(uid, nombre, tipo, sesion["id"], firmante_nombre, comentario, año=año, mes=mes)
            st.session_state.pop("_confirmar_firma", None)
            st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("_confirmar_firma", None)
            st.rerun()


def _render_panel_actas(
    servicio: CertificacionService, sesion: dict, tipo_formato: str, año: int, mes: int
) -> None:
    permisos = sesion.get("permisos", [])
    roles_sesion = sesion.get("roles", [])
    es_admin = any(r in {"admin", "administrador"} for r in roles_sesion)

    orden = ORDEN_FIRMAS_ACTAS[tipo_formato]
    mis_roles = [r for r in orden if _META_FIRMA_ACTAS[r][2] in permisos]

    if not es_admin and not mis_roles:
        st.warning("No tienes permiso de firma para este formato.")
        return

    st.subheader(_LABEL_FORMATO_ACTAS[tipo_formato])

    if len(mis_roles) > 1:
        opciones_rol = {r: _META_FIRMA_ACTAS[r][1] for r in mis_roles}
        rol_activo = st.radio(
            "Estás actuando como firmante de:",
            options=list(opciones_rol.keys()),
            format_func=lambda r: f"✍️ {opciones_rol[r]}",
            horizontal=True,
            key=f"sel_rol_actas_{tipo_formato}",
        )
    elif mis_roles:
        rol_activo = mis_roles[0]
    else:
        rol_activo = None

    if es_admin and rol_activo is None:
        st.info("🛡️ **Administrador** — Vista de solo lectura.")
    elif rol_activo:
        _, label_largo, _ = _META_FIRMA_ACTAS[rol_activo]
        st.info(f"✍️ **Actuando como:** Firma {label_largo}")

    st.divider()

    with st.spinner("Consultando colaboradores…"):
        empleados = servicio.obtener_empleados_para_certificar(tipo_formato=tipo_formato, año=año, mes=mes)
    empleados = [e for e in empleados if e.get("certificacion")]

    if not empleados:
        st.info("Ningún colaborador ha generado este formato todavía.")
        return

    # Métricas
    total = len(empleados)
    if rol_activo:
        mis_pendientes = sum(
            1 for e in empleados
            if not e.get("firmas", {}).get(rol_activo)
        )
        mis_aprobados = sum(
            1 for e in empleados
            if e.get("firmas", {}).get(rol_activo)
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Total contratistas", total)
        m2.metric("Pendientes mi aprobación", mis_pendientes)
        m3.metric("Aprobados", mis_aprobados)
    else:
        aprobadas = sum(
            1 for e in empleados
            if (e.get("certificacion") or {}).get("estado") == "aprobado"
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Total contratistas", total)
        m2.metric("Aprobadas", aprobadas)
        m3.metric("Pendientes de firmas", total - aprobadas)

    st.divider()

    # Filtros
    fc1, fc2, fc3 = st.columns([3, 3, 2])
    with fc1:
        contratistas_unicos = sorted(list(set(e["nombre"] for e in empleados)))
        opciones_contratista = ["Todos"] + contratistas_unicos
        buscar = st.selectbox(
            "Filtro por Gestor",
            options=opciones_contratista,
            index=0,
            key=f"filtro_contratista_aprob_{tipo_formato}",
        )
    with fc2:
        opciones_tipo = ["Con contrato activo", "Todos (con y sin contrato)"] + list(MAPA_TIPOS_CONTRATO.values()) + ["Sin contrato"]
        filtro_tipo = st.selectbox(
            "Filtro por Contrato",
            options=opciones_tipo,
            index=0,
            key=f"filtro_tipo_contrato_aprob_{tipo_formato}",
        )
    with fc3:
        if rol_activo:
            filtro = st.selectbox(
                "Filtro por Aprobados",
                options=["Todos", "Pendientes mi aprobación", "Aprobados"],
                index=0,
                key=f"filtro_estado_firma_aprob_{tipo_formato}",
            )
        else:
            filtro = st.selectbox(
                "Filtro por Aprobados",
                options=["Todos", "Con todas las firmas", "Faltan firmas"],
                index=0,
                key=f"filtro_estado_firma_aprob_{tipo_formato}",
            )

    # Aplicar Filtros
    lista = empleados
    if buscar != "Todos":
        lista = [e for e in lista if e["nombre"] == buscar]

    if filtro_tipo == "Con contrato activo":
        lista = [e for e in lista if e.get("tiene_contrato")]
    elif filtro_tipo == "Sin contrato":
        lista = [e for e in lista if not e.get("tiene_contrato")]
    elif filtro_tipo == "Todos (con y sin contrato)":
        pass
    else:
        inv_map = {v: k for k, v in MAPA_TIPOS_CONTRATO.items()}
        clave_tecnica = inv_map.get(filtro_tipo)
        lista = [e for e in lista if e.get("tipo_contrato") == clave_tecnica]

    if rol_activo:
        if filtro == "Pendientes mi aprobación":
            lista = [e for e in lista if not e.get("firmas", {}).get(rol_activo)]
        elif filtro == "Aprobados":
            lista = [e for e in lista if e.get("firmas", {}).get(rol_activo)]
    else:
        if filtro == "Con todas las firmas":
            lista = [e for e in lista if (e.get("certificacion") or {}).get("estado") == "aprobado"]
        elif filtro == "Faltan firmas":
            lista = [e for e in lista if (e.get("certificacion") or {}).get("estado") != "aprobado"]

    st.caption(f"Mostrando {len(lista)} de {total} contratistas")

    if not lista:
        st.info("Ningún contratista coincide con los filtros aplicados.")
        return

    for emp in lista:
        uid = emp["usuario_id"]
        nombre = emp["nombre"]
        cert = emp.get("certificacion") or {}
        firmas = emp.get("firmas", {})
        eventos = cert.get("eventos") or []
        cert_año = cert.get("año") or ""
        cert_mes = cert.get("mes") or 1
        cert_nombre_mes = MESES_ES[cert_mes - 1] if cert_mes else ""

        with st.container(border=True):
            c_nom, c_badges, c_accion = st.columns([3, 5, 2])

            with c_nom:
                st.markdown(f"**{nombre}**")
                st.caption("✅ Formato aprobado" if cert.get("estado") == "aprobado" else "⏳ Pendiente de firmas")

            with c_badges:
                badges = "&nbsp;".join(_badge_firma_actas(r, firmas.get(r)) for r in orden)
                st.markdown(badges, unsafe_allow_html=True)

                eventos_rol_activo = [
                    ev for ev in eventos
                    if ev.get("tipo") == "revocacion_cascada" and ev.get("rol_revocado") == rol_activo
                ]
                if rol_activo and eventos_rol_activo and not firmas.get(rol_activo):
                    ultimo = eventos_rol_activo[-1]
                    st.caption(f"⚠️ Tu aprobación fue removida porque **{ultimo.get('causada_por')}** revocó la suya.")

            with c_accion:
                ya_aprobado = cert.get("estado") == "aprobado"

                # Mostrar botón de descarga si el acta ya está aprobada/firmada
                if ya_aprobado:
                    pdf_bytes = obtener_pdf_certificado_cacheado(
                        servicio,
                        str(cert["_id"]),
                        cert.get("hash_verificacion", ""),
                        cert,
                        version_key=str(cert.get("firmas", {})),
                    )
                    prefijos_archivo = {
                        "acta_compromiso": "Acta_Compromiso",
                        "acta_recibo_entrega_cps": "Balance_General_CPS",
                        "acta_recibo_entrega_cps_real": "Acta_Recibo_Entrega_CPS",
                    }
                    prefijo = prefijos_archivo.get(tipo_formato, "Acta")
                    st.download_button(
                        "⬇️ Descargar",
                        data=pdf_bytes,
                        file_name=f"{prefijo}_{nombre.replace(' ', '_')}_{cert_nombre_mes}_{cert_año}.pdf",
                        mime="application/pdf",
                        key=f"dl_{tipo_formato}_{uid}",
                        use_container_width=True,
                    )
                else:
                    if st.button("🔍 Borrador", key=f"draft_{tipo_formato}_{uid}", use_container_width=True):
                        st.session_state["ver_borrador_acta"] = {
                            "cert": cert,
                            "nombre": nombre,
                            "tipo_formato": tipo_formato,
                            "nombre_mes": cert_nombre_mes,
                            "año": cert_año,
                        }
                        st.rerun()

                if rol_activo:
                    idx = orden.index(rol_activo)
                    rol_anterior = orden[idx - 1] if idx > 0 else None
                    puede_firmar = rol_anterior is None or bool(firmas.get(rol_anterior))
                    ya_firmado = bool(firmas.get(rol_activo))

                    if ya_firmado:
                        if st.button("↩ Revocar", key=f"revocar_actas_{tipo_formato}_{uid}", use_container_width=True):
                            servicio.revocar_firma_actas(str(cert["_id"]), rol_activo)
                            st.rerun()
                    elif not ya_aprobado:
                        if not puede_firmar:
                            st.button(
                                "✅ Aprobar",
                                key=f"aprobar_actas_{tipo_formato}_{uid}",
                                use_container_width=True,
                                disabled=True,
                                help=f"Esperando firma de {_META_FIRMA_ACTAS[rol_anterior][1]}",
                            )
                        else:
                            if st.button(
                                "✅ Aprobar",
                                key=f"aprobar_actas_{tipo_formato}_{uid}",
                                type="primary",
                                use_container_width=True,
                            ):
                                st.session_state["_confirmar_firma_actas"] = {
                                    "uid": uid,
                                    "cert_id": str(cert["_id"]),
                                    "nombre": nombre,
                                    "tipo_formato": tipo_formato,
                                    "rol": rol_activo,
                                }
                                st.rerun()


# ── Render principal ─────────────────────────────────────────────

def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    servicio = CertificacionService()
    permisos = sesion.get("permisos", [])
    roles = sesion.get("roles", [])
    es_admin = any(r in {"admin", "administrador"} for r in roles)

    # Recopilar todos los tipos de firma que tiene este usuario.
    # Un mismo usuario puede tener más de un permiso de firma (ej. corr + gd).
    mis_tipos_firma = [t for t in TIPOS_FIRMA if _META_FIRMA[t][2] in permisos]
    # Idem para los roles de firma de actas (financiera/abogado/jefe) — un usuario
    # puede tener solo permisos de actas y ningún permiso corr/gd/secop.
    mis_roles_actas = [r for r in TIPOS_FIRMA_ACTAS if _META_FIRMA_ACTAS[r][2] in permisos]
    puede_ver_control = bool(mis_tipos_firma) or es_admin or "certificacion.aprobar" in permisos

    if not es_admin and not mis_tipos_firma and not mis_roles_actas:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    # Inyectar CSS para dar fondo verde al botón de certificado
    st.markdown(
        """
        <style>
        div[data-testid="stDownloadButton"] button {
            background-color: #2e7d32 !important;
            color: white !important;
            border: 1px solid #1b5e20 !important;
        }
        div[data-testid="stDownloadButton"] button:hover {
            background-color: #1b5e20 !important;
            color: white !important;
            border-color: #1b5e20 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    mostrar_titulo_decorado("Sup. Formatos")

    periodos_globales = servicio.periodos_disponibles_global()
    año, mes = st.selectbox(
        "📅 Período a firmar",
        options=periodos_globales,
        format_func=lambda p: f"{MESES_ES[p[1] - 1]} {p[0]}",
        index=periodos_globales.index(servicio.periodo_certificable()),
        key="sup_periodo_seleccionado",
    )
    nombre_mes = MESES_ES[mes - 1]
    st.caption(servicio.leyenda_periodo(año, mes))

    # Inicializar estado para mostrar/ocultar el formato de control
    if "ver_formato_control" not in st.session_state:
        st.session_state["ver_formato_control"] = False
    if "tab_actas_activo" not in st.session_state:
        st.session_state["tab_actas_activo"] = None
    # Botones de navegación
    st.write("")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if puede_ver_control:
            tipo_btn1 = "primary" if st.session_state["ver_formato_control"] else "secondary"
            if st.button("1-Formato de control Corr-GD-SECOP", type=tipo_btn1, use_container_width=True, key="btn_formato_control"):
                st.session_state["ver_formato_control"] = not st.session_state["ver_formato_control"]
                st.session_state["tab_actas_activo"] = None
                st.rerun()
    with col2:
        activo_compromiso = st.session_state["tab_actas_activo"] == "acta_compromiso"
        tipo_btn2 = "primary" if activo_compromiso else "secondary"
        if st.button("2- Acta de compromiso", type=tipo_btn2, use_container_width=True, key="btn_acta_compromiso_sup"):
            st.session_state["tab_actas_activo"] = None if activo_compromiso else "acta_compromiso"
            st.session_state["ver_formato_control"] = False
            st.rerun()
    with col3:
        activo_balance = st.session_state["tab_actas_activo"] == "acta_recibo_entrega_cps"
        tipo_btn3 = "primary" if activo_balance else "secondary"
        if st.button("3- Balance General CPS", type=tipo_btn3, use_container_width=True, key="btn_balance_general_sup"):
            st.session_state["tab_actas_activo"] = None if activo_balance else "acta_recibo_entrega_cps"
            st.session_state["ver_formato_control"] = False
            st.rerun()
    with col4:
        activo_recibo = st.session_state["tab_actas_activo"] == "acta_recibo_entrega_cps_real"
        tipo_btn4 = "primary" if activo_recibo else "secondary"
        if st.button("4- Acta de recibo y entrega CPS", type=tipo_btn4, use_container_width=True, key="btn_acta_recibo_sup"):
            st.session_state["tab_actas_activo"] = None if activo_recibo else "acta_recibo_entrega_cps_real"
            st.session_state["ver_formato_control"] = False
            st.rerun()

    st.write("")

    # Selector de rol cuando el usuario tiene más de un permiso de firma
    if st.session_state["ver_formato_control"] and puede_ver_control:
        if len(mis_tipos_firma) > 1:
            opciones_firma = {t: _META_FIRMA[t][1] for t in mis_tipos_firma}
            tipo_mi_firma = st.radio(
                "Estás actuando como firmante de:",
                options=list(opciones_firma.keys()),
                format_func=lambda t: f"✍️ {opciones_firma[t]}",
                horizontal=True,
                key="sel_tipo_firma_activo",
            )
        elif mis_tipos_firma:
            tipo_mi_firma = mis_tipos_firma[0]
        else:
            tipo_mi_firma = None

        # Banner de rol
        if es_admin and tipo_mi_firma is None:
            st.info(
                "🛡️ **Administrador** — Vista de solo lectura. "
                "Para configurar los firmantes ve a **Seguimiento de Certificaciones**."
            )
        elif tipo_mi_firma:
            _, label_largo, _ = _META_FIRMA[tipo_mi_firma]
            roles_txt = (
                " · ".join(_META_FIRMA[t][1] for t in mis_tipos_firma)
                if len(mis_tipos_firma) > 1
                else label_largo
            )
            st.info(f"✍️ **Actuando como:** Firma de {label_largo}  ·  Tienes permiso para: {roles_txt}")

        st.divider()

        with st.spinner("Consultando estado de correspondencia…"):
            empleados = servicio.obtener_empleados_para_certificar(año=año, mes=mes)

        if not empleados:
            st.info("No hay colaboradores con correspondencia registrada.")
        else:
            # Métricas
            total = len(empleados)
            con_3_firmas = sum(
                1 for e in empleados
                if all(e.get("firmas", {}).get(t) for t in TIPOS_FIRMA)
            )

            if tipo_mi_firma:
                mis_pendientes = sum(
                    1 for e in empleados
                    if not e.get("firmas", {}).get(tipo_mi_firma)
                )
                mis_aprobados = sum(
                    1 for e in empleados
                    if e.get("firmas", {}).get(tipo_mi_firma)
                )
                m1, m2, m3 = st.columns(3)
                m1.metric("Total contratistas", total)
                m2.metric("Pendientes mi aprobación", mis_pendientes)
                m3.metric("Aprobados", mis_aprobados)
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("Total contratistas", total)
                m2.metric("Con las 3 firmas", con_3_firmas)
                m3.metric("Pendientes de firmas", total - con_3_firmas)

            st.divider()

            # Filtros
            fc1, fc2, fc3 = st.columns([3, 3, 2])
            with fc1:
                contratistas_unicos = sorted(list(set(e["nombre"] for e in empleados)))
                opciones_contratista = ["Todos"] + contratistas_unicos
                buscar = st.selectbox(
                    "Filtro por Gestor",
                    options=opciones_contratista,
                    index=0,
                    key="filtro_contratista_aprob",
                )
            with fc2:
                opciones_tipo = ["Con contrato activo", "Todos (con y sin contrato)"] + list(MAPA_TIPOS_CONTRATO.values()) + ["Sin contrato"]
                filtro_tipo = st.selectbox(
                    "Filtro por Contrato",
                    options=opciones_tipo,
                    index=0,
                    key="filtro_tipo_contrato_aprob",
                )
            with fc3:
                if tipo_mi_firma:
                    filtro = st.selectbox(
                        "Filtro por Aprobados",
                        options=["Todos", "Pendientes mi aprobación", "Aprobados"],
                        index=0,
                        key="filtro_estado_firma_aprob",
                    )
                else:
                    filtro = st.selectbox(
                        "Filtro por Aprobados",
                        options=["Todos", "Con las 3 firmas", "Faltan firmas"],
                        index=0,
                        key="filtro_estado_firma_aprob",
                    )

            lista = empleados
            if buscar != "Todos":
                lista = [e for e in lista if e["nombre"] == buscar]

            if filtro_tipo == "Con contrato activo":
                lista = [e for e in lista if e.get("tiene_contrato")]
            elif filtro_tipo == "Sin contrato":
                lista = [e for e in lista if not e.get("tiene_contrato")]
            elif filtro_tipo == "Todos (con y sin contrato)":
                pass
            else:
                inv_map = {v: k for k, v in MAPA_TIPOS_CONTRATO.items()}
                clave_tecnica = inv_map.get(filtro_tipo)
                lista = [e for e in lista if e.get("tipo_contrato") == clave_tecnica]

            if tipo_mi_firma:
                if filtro == "Pendientes mi aprobación":
                    lista = [e for e in lista if not e.get("firmas", {}).get(tipo_mi_firma)]
                elif filtro == "Aprobados":
                    lista = [e for e in lista if e.get("firmas", {}).get(tipo_mi_firma)]
            else:
                if filtro == "Con las 3 firmas":
                    lista = [e for e in lista if all(e.get("firmas", {}).get(t) for t in TIPOS_FIRMA)]
                elif filtro == "Faltan firmas":
                    lista = [e for e in lista if not all(e.get("firmas", {}).get(t) for t in TIPOS_FIRMA)]

            st.caption(f"Mostrando {len(lista)} de {total} contratistas")

            if not lista:
                st.info("Ningún contratista coincide con los filtros aplicados.")
            else:
                for emp in lista:
                    uid = emp["usuario_id"]
                    nombre = emp["nombre"]
                    pendientes = emp["cantidad_pendientes"]
                    vencidas = emp["cantidad_vencidas"]
                    firmas = emp.get("firmas", {})
                    tiene_contrato = emp.get("tiene_contrato", False)
                    mi_firma_dada = firmas.get(tipo_mi_firma) if tipo_mi_firma else None

                    with st.container(border=True):
                        c_nom, c_badges, c_accion = st.columns([3, 5, 2])

                        with c_nom:
                            cert_emp = emp.get("certificacion") or {}
                            obs_existente = cert_emp.get("observacion") or ""
                            st.markdown(f"**{nombre}**")
                            if obs_existente:
                                st.caption(f"💬 *Obs: {obs_existente}*")
                            if mi_firma_dada:
                                fecha_firma = mi_firma_dada.get("fecha")
                                fecha_str = formato_fecha_bogota(fecha_firma, "%d/%m/%Y %H:%M") if fecha_firma else ""
                                st.caption(f"Aprobado · {fecha_str}")
                            elif not tiene_contrato:
                                st.caption("⚠️ Sin contrato activo")

                        with c_badges:
                            badges = (
                                _badge_corr(pendientes, vencidas)
                                + "&nbsp;&nbsp;"
                                + "&nbsp;".join(_badge_firma(t, firmas.get(t)) for t in TIPOS_FIRMA)
                            )
                            st.markdown(badges, unsafe_allow_html=True)

                            # Detalle de cada firma existente
                            detalles = []
                            comentarios_firma = []
                            for t in TIPOS_FIRMA:
                                f = firmas.get(t)
                                if f:
                                    fecha_f = formato_fecha_bogota(f.get("fecha"), "%d/%m %H:%M")
                                    detalles.append(f"{_META_FIRMA[t][0]}: {f.get('firmante_nombre', '')} · {fecha_f}")
                                    if f.get("comentario"):
                                        comentarios_firma.append(f"💬 {_META_FIRMA[t][0]}: *{f['comentario']}*")
                            if detalles:
                                st.caption(" · ".join(detalles))
                            for linea in comentarios_firma:
                                st.caption(linea)

                        with c_accion:
                            cert_emp = emp.get("certificacion") or {}
                            ya_certificado = cert_emp.get("estado") == "aprobado"

                            if ya_certificado:
                                pdf_bytes = obtener_pdf_certificado_cacheado(
                                    servicio,
                                    str(cert_emp["_id"]),
                                    cert_emp.get("hash_verificacion", ""),
                                    cert_emp,
                                    version_key=str(cert_emp.get("firmas", {})),
                                )
                                st.download_button(
                                    "⬇️ Certificado",
                                    data=pdf_bytes,
                                    file_name=f"Certificado_{nombre.replace(' ', '_')}_{nombre_mes}_{año}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_{uid}",
                                    use_container_width=True,
                                )
                            elif not tipo_mi_firma:
                                # Admin sin designación solo visualiza
                                pass
                            elif mi_firma_dada:
                                if st.button(
                                    "↩ Revocar",
                                    key=f"firma_{uid}",
                                    use_container_width=True,
                                    help="Revocar mi aprobación.",
                                ):
                                    servicio.revocar_firma(uid, tipo_mi_firma, año=año, mes=mes)
                                    st.rerun()
                            else:
                                if st.button(
                                    "✅ Aprobar",
                                    key=f"firma_{uid}",
                                    type="primary",
                                    use_container_width=True,
                                ):
                                    st.session_state["_confirmar_firma"] = {
                                        "uid": uid,
                                        "nombre": nombre,
                                        "tipo": tipo_mi_firma,
                                    }
                                    st.rerun()

    tab_actas = st.session_state.get("tab_actas_activo")
    if tab_actas:
        _render_panel_actas(servicio, sesion, tab_actas, año, mes)

    if st.session_state.get("_confirmar_firma_actas"):
        _dialog_confirmar_firma_actas(servicio, sesion)

    if st.session_state.get("_confirmar_firma"):
        _dialog_confirmar_firma(servicio, sesion, año, mes, nombre_mes)

    if st.session_state.get("ver_borrador_acta"):
        _dialog_ver_borrador(servicio)
