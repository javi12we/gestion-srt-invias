from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado

from app.core.autorizacion import validar_permiso, ValidacionAutorizacion
from app.core.catalogos import TIPOS_CONTRATO
from app.core.sesion import obtener_sesion
from app.core.cache_datos import limpiar_cache_lecturas
from app.core.ui_laboral import (
    boton_guardar_laboral,
    construir_mapas_catalogos,
    inputs_informacion_laboral,
    laboral_vacia,
    limpiar_estado_laboral,
    render_seccion_firma,
)
from app.services.usuario_service import DIAS_GRACIA_DESCARGA_FORMATOS, UsuarioService

TIPOS_DOCUMENTO = {
    "": "— Sin especificar —",
    "CC": "CC — Cédula de Ciudadanía",
    "CE": "CE — Cédula de Extranjería",
    "TI": "TI — Tarjeta de Identidad",
    "PA": "PA — Pasaporte",
    "RC": "RC — Registro Civil",
    "PEP": "PEP — Permiso Especial de Permanencia",
    "PPT": "PPT — Permiso por Protección Temporal",
}


# ── MODAL DE EDICIÓN ────────────────────────────────────────────────────────────

@st.dialog("Editar usuario", width="large")
def modal_editar_usuario(usuario_doc, permisos, sesion, roles_disponibles, permisos_disponibles, servicio, mapas):
    uo = usuario_doc

    # Cabecera
    estado_badge = (
        '<span style="background:#1a7a4a;color:#d4f5e2;padding:3px 10px;border-radius:12px;font-size:0.85em;">🟢 Activo</span>'
        if uo.get("activo", False)
        else '<span style="background:#7a1a1a;color:#f5d4d4;padding:3px 10px;border-radius:12px;font-size:0.85em;">🔴 Inactivo</span>'
    )
    st.markdown(
        f'<h3 style="margin-bottom:4px;">👤 {uo.get("nombre_completo", "")} &nbsp; {estado_badge}</h3>'
        f'<p style="margin:0;color:gray;font-size:0.9em;">@{uo.get("usuario", "")} &nbsp;·&nbsp; {uo.get("email", "")}</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # Botón de activar/desactivar
    if "usuario.desactivar" in permisos:
        col_tog, _ = st.columns([1, 3])
        with col_tog:
            if uo.get("activo", False):
                if st.button("🔴 Desactivar usuario", use_container_width=True, key="btn_desactivar_modal"):
                    try:
                        servicio.desactivar_usuario(
                            str(uo["_id"]),
                            permisos_usuario=permisos,
                            usuario_actual=sesion["usuario"],
                        )
                        st.session_state["mensaje_exito_usuarios"] = "Usuario desactivado correctamente."
                        st.session_state["last_opened_usuario_id"] = None
                        limpiar_cache_lecturas()
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            else:
                if st.button("🟢 Activar usuario", use_container_width=True, key="btn_activar_modal"):
                    try:
                        servicio.activar_usuario(
                            str(uo["_id"]),
                            permisos_usuario=permisos,
                            usuario_actual=sesion["usuario"],
                        )
                        st.session_state["mensaje_exito_usuarios"] = "Usuario activado correctamente."
                        st.session_state["last_opened_usuario_id"] = None
                        limpiar_cache_lecturas()
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    # Formulario de edición
    if "usuario.editar" not in permisos:
        st.warning("No tienes permiso para editar usuarios.")
        return

    with st.form("form_editar_usuario_modal"):
        col1, col2 = st.columns(2)
        with col1:
            usuario_editado = st.text_input("Usuario", value=uo.get("usuario", ""))
            email_editado = st.text_input("Correo electrónico", value=uo.get("email", ""))
        with col2:
            nombre_editado = st.text_input("Nombre completo", value=uo.get("nombre_completo", ""))
            password_nueva = st.text_input(
                "Nueva contraseña", type="password", placeholder="Dejar vacío para no cambiar"
            )

        col_tdoc, col_ndoc = st.columns(2)
        with col_tdoc:
            tipo_doc_actual = uo.get("tipo_documento") or ""
            tipo_documento_editado = st.selectbox(
                "Tipo de documento",
                options=list(TIPOS_DOCUMENTO.keys()),
                format_func=lambda k: TIPOS_DOCUMENTO[k],
                index=list(TIPOS_DOCUMENTO.keys()).index(tipo_doc_actual) if tipo_doc_actual in TIPOS_DOCUMENTO else 0,
            )
        with col_ndoc:
            numero_documento_editado = st.text_input(
                "Número de documento",
                value=uo.get("numero_documento", ""),
                placeholder="Solo números",
            )
            if numero_documento_editado and not numero_documento_editado.strip().isdigit():
                st.error("El número de documento debe contener únicamente números.")

        lugar_expedicion_editado = st.text_input(
            "Lugar de expedición del documento",
            value=uo.get("lugar_expedicion_documento", "") or "",
            placeholder="Ciudad de expedición de la cédula",
        )

        roles_sel = st.multiselect("Roles", options=roles_disponibles, default=uo.get("roles", []))
        permisos_sel = st.multiselect(
            "Permisos extra", options=permisos_disponibles, default=uo.get("permisos_extra", [])
        )

        st.caption("Los cambios se guardan solo al pulsar el botón.")
        enviar = st.form_submit_button("💾 Guardar cambios", use_container_width=True, type="primary")

    if enviar:
        try:
            servicio.actualizar_usuario(
                str(uo["_id"]),
                {
                    "usuario": usuario_editado.strip(),
                    "nombre_completo": nombre_editado.strip(),
                    "email": email_editado.strip(),
                    "password": password_nueva,
                    "activo": uo.get("activo", False),
                    "roles": roles_sel,
                    "permisos_extra": permisos_sel,
                    "tipo_documento": tipo_documento_editado.strip(),
                    "numero_documento": numero_documento_editado.strip(),
                    "lugar_expedicion_documento": lugar_expedicion_editado.strip(),
                    "actualizado_por": sesion["usuario"],
                },
                permisos_usuario=permisos,
            )
            st.session_state["mensaje_exito_usuarios"] = "Usuario actualizado correctamente."
            st.session_state["last_opened_usuario_id"] = None
            limpiar_cache_lecturas()
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    # ── Información laboral ───────────────────────────────────────────────────
    st.divider()
    st.subheader("💼 Información laboral")
    _pref = f"edit_{uo['_id']}"
    _uid = str(uo["_id"])
    _il_actual = uo.get("informacion_laboral") or {}
    _il_raw = inputs_informacion_laboral(_pref, _il_actual, mapas)
    st.divider()
    if boton_guardar_laboral(_pref, _il_raw, key=f"save_lab_{_uid}"):
        try:
            servicio.actualizar_usuario(
                _uid,
                {"informacion_laboral": _il_raw, "actualizado_por": sesion["usuario"]},
                permisos_usuario=permisos,
            )
            limpiar_estado_laboral(_pref)
            st.session_state["mensaje_exito_usuarios"] = "Información laboral actualizada."
            st.session_state["last_opened_usuario_id"] = None
            limpiar_cache_lecturas()
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    # ── Firma ─────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("✍️ Firma")

    def _cerrar_con_mensaje(mensaje):
        st.session_state["mensaje_exito_usuarios"] = mensaje
        st.session_state["last_opened_usuario_id"] = None

    render_seccion_firma(_uid, sesion["usuario"], f"adm_{_uid}", al_terminar=_cerrar_con_mensaje)

    # ── Gestión de contratos ─────────────────────────────────────────────────
    st.divider()
    st.subheader("📄 Contratos")

    _contratos = sorted(
        uo.get("contratos") or [],
        key=lambda c: c.get("fecha_inicio") or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )

    for _c in _contratos:
        _c_vencido = UsuarioService._contrato_finalizado(_c)
        _c_fin = UsuarioService._contrato_finalizado(_c, dias_gracia=DIAS_GRACIA_DESCARGA_FORMATOS)
        _c_num = _c.get("numero", "")
        _c_fi = _c.get("fecha_inicio")
        _c_ff = _c.get("fecha_fin")
        if not _c_vencido:
            _estado = "🟢 Activo"
        elif not _c_fin:
            _estado = "🟡 Abierto temporalmente (2 meses)"
        else:
            _estado = "🔴 Finalizado"
        with st.expander(f"{_c_num} — {_estado}"):
            _d1, _d2 = st.columns(2)
            with _d1:
                st.write(f"**Tipo:** {TIPOS_CONTRATO.get(_c.get('tipo') or '', '—')}")
                _v = _c.get("valor")
                st.write(f"**Valor:** {'${:,.0f}'.format(_v) if _v else '—'}")
            with _d2:
                _vm = _c.get("valor_mensual")
                st.write(f"**Valor mensual:** {'${:,.0f}'.format(_vm) if _vm else '—'}")
                _vpp = _c.get("valor_primer_pago")
                st.write(f"**Valor primer pago:** {'${:,.0f}'.format(_vpp) if _vpp else '—'}")
                st.write(f"**RP / compromiso presupuestal:** {_c.get('rp_compromiso_presupuestal') or '—'}")
            _d3, _d4, _d5 = st.columns(3)
            with _d3:
                _frp = _c.get("fecha_recurso_presupuestal")
                st.write(f"**Fecha RP:** {_frp.strftime('%d/%m/%Y') if _frp else '—'}")
            with _d4:
                st.write(f"**Inicio:** {_c_fi.strftime('%d/%m/%Y') if _c_fi else '—'}")
            with _d5:
                st.write(f"**Fin:** {_c_ff.strftime('%d/%m/%Y') if _c_ff else '—'}")
            if _c.get("objeto"):
                st.write(f"**Objeto:** {_c.get('objeto')}")
            if _c.get("radicado_del_contrato"):
                st.write(f"**Radicado del contrato:** {_c.get('radicado_del_contrato')}")

            _fi_ed = _c_fi.date() if _c_fi and hasattr(_c_fi, "date") else _c_fi
            _ff_ed = _c_ff.date() if _c_ff and hasattr(_c_ff, "date") else _c_ff
            
            # Usamos st.container en vez de st.form por los botones de pagos interactivos
            with st.container():
                _ec1, _ec2 = st.columns(2)
                with _ec1:
                    _e_num = st.text_input("Número", value=_c_num, key=f"e_num_{_c_num}")
                    _e_tipo_idx = list(TIPOS_CONTRATO.keys()).index(_c.get("tipo") or "") if (_c.get("tipo") or "") in TIPOS_CONTRATO else 0
                    _e_tipo = st.selectbox("Tipo", options=list(TIPOS_CONTRATO.keys()), format_func=lambda k: TIPOS_CONTRATO[k], index=_e_tipo_idx, key=f"e_tipo_{_c_num}")
                with _ec2:
                    _e_valor = st.number_input("Valor (COP)", min_value=0, value=int(_c.get("valor") or 0), step=100000, format="%d", key=f"e_val_{_c_num}")
                    _e_vm = st.number_input("Valor mensual (COP)", min_value=0, value=int(_c.get("valor_mensual") or 0), step=100000, format="%d", key=f"e_vm_{_c_num}")
                    st.markdown(
                        """
                        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                            <span style="font-size: 14px; font-weight: 500; color: #333333;">Valor primer pago</span>
                            <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                                <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                    <div class="srti-tooltip-content" style="font-weight: normal;">
                                        <h4>Valor primer pago</h4>
                                        <p>Este valor figurará en sus formatos de primera cuenta.</p>
                                    </div>
                                </span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    _e_vpp = st.number_input("Valor primer pago", min_value=0, value=int(_c.get("valor_primer_pago") or 0), step=100000, format="%d", key=f"e_vpp_{_c_num}", label_visibility="collapsed")
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span style="font-size: 14px; font-weight: 500; color: #333333;">RP / compromiso presupuestal</span>
                        <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                            <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                <div class="srti-tooltip-content" style="font-weight: normal;">
                                    <h4>RP / compromiso presupuestal</h4>
                                    <p>Este dato se puede encontrar dentro del cargue de datos financiero en SECOP II.</p>
                                </div>
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                _e_rp = st.text_input("RP / compromiso presupuestal", value=_c.get("rp_compromiso_presupuestal") or "", key=f"e_rp_{_c_num}", placeholder="Código alfanumérico", label_visibility="collapsed")
                _ec3, _ec4, _ec5 = st.columns(3)
                with _ec3:
                    _e_frp_ed = _c.get("fecha_recurso_presupuestal")
                    if _e_frp_ed and hasattr(_e_frp_ed, "date"):
                        _e_frp_ed = _e_frp_ed.date()
                    st.markdown(
                        """
                        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                            <span style="font-size: 14px; font-weight: 500; color: #333333;">Fecha recurso presupuestal</span>
                            <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                                <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                    <div class="srti-tooltip-content" style="font-weight: normal;">
                                        <h4>Fecha recurso presupuestal</h4>
                                        <p>Este dato se puede encontrar dentro del cargue de datos financiero en SECOP II.</p>
                                    </div>
                                </span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    _e_frp = st.date_input("Fecha recurso presupuestal", value=_e_frp_ed, format="DD/MM/YYYY", key=f"e_frp_{_c_num}", label_visibility="collapsed")
                with _ec4:
                    st.markdown(
                        """
                        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                            <span style="font-size: 14px; font-weight: 500; color: #333333;">Fecha de inicio contrato</span>
                            <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                                <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                    <div class="srti-tooltip-content" style="font-weight: normal;">
                                        <h4>Fecha de inicio contrato</h4>
                                        <p>El dato se puede encontrar en la cláusula del contrato, estudios previos o en la información general del contrato página de firma.</p>
                                    </div>
                                </span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    _e_fi = st.date_input("Fecha de inicio contrato", value=_fi_ed, format="DD/MM/YYYY", key=f"e_fi_{_c_num}", label_visibility="collapsed")
                with _ec5:
                    st.markdown(
                        """
                        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                            <span style="font-size: 14px; font-weight: 500; color: #333333;">Fecha de fin de contrato</span>
                            <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                                <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                    <div class="srti-tooltip-content" style="font-weight: normal;">
                                        <h4>Fecha de fin de contrato</h4>
                                        <p>El dato se puede encontrar en la cláusula del contrato, estudios previos o en la información general del contrato página de firma.</p>
                                    </div>
                                </span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    _e_ff = st.date_input("Fecha de fin de contrato", value=_ff_ed, format="DD/MM/YYYY", key=f"e_ff_{_c_num}", label_visibility="collapsed")
                _e_obj = st.text_area("Objeto", value=_c.get("objeto") or "", key=f"e_obj_{_c_num}")
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span style="font-size: 14px; font-weight: 500; color: #333333;">Radicado del contrato</span>
                        <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                            <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                <div class="srti-tooltip-content" style="font-weight: normal;">
                                    <h4>Radicado del contrato</h4>
                                    <p>Este radicado puede ser encontrado en las cláusulas, estudios previos o repositorios del contrato, y será necesario para el Acta de entrega.</p>
                                </div>
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                _e_rad = st.text_input("Radicado del contrato", value=_c.get("radicado_del_contrato") or "", key=f"e_rad_{_c_num}", label_visibility="collapsed")
                
                # RENDERIZAMOS EL BALANCE GENERAL Y PLAN DE PAGOS
                from app.core.ui_contratos import render_balance_y_pagos
                _balance_pagos_datos = render_balance_y_pagos(f"admin_c_{_c_num}", _c, deshabilitado=_c_fin)
                
                _e_env = st.button("💾 Guardar", key=f"btn_save_adm_c_{_c_num}", use_container_width=True, type="primary", disabled=_c_fin)
                
            if _e_env:
                try:
                    datos_totales = {
                        "numero": _e_num.strip(),
                        "tipo": _e_tipo,
                        "valor": _e_valor if _e_valor > 0 else None,
                        "rp_compromiso_presupuestal": _e_rp.strip(),
                        "fecha_inicio": _e_fi,
                        "fecha_fin": _e_ff,
                        "fecha_recurso_presupuestal": _e_frp,
                        "valor_mensual": _e_vm if _e_vm > 0 else None,
                        "valor_primer_pago": _e_vpp if _e_vpp > 0 else None,
                        "objeto": _e_obj.strip(),
                        "radicado_del_contrato": _e_rad.strip() if _e_rad else None,
                    }
                    datos_totales.update(_balance_pagos_datos)
                    
                    servicio.editar_contrato(str(uo["_id"]), _c_num, datos_totales)
                    st.session_state["mensaje_exito_usuarios"] = f"Contrato {_c_num} actualizado."
                    st.session_state["last_opened_usuario_id"] = None
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    with st.expander("➕ Agregar nuevo contrato"):
        with st.form("form_nuevo_contrato_modal"):
            _nc1, _nc2 = st.columns(2)
            with _nc1:
                _n_num = st.text_input("Número de contrato *")
                _n_tipo = st.selectbox("Tipo", options=list(TIPOS_CONTRATO.keys()), format_func=lambda k: TIPOS_CONTRATO[k])
            with _nc2:
                _n_valor = st.number_input("Valor (COP)", min_value=0, step=100000, format="%d")
                _n_vm = st.number_input("Valor mensual (COP)", min_value=0, step=100000, format="%d")
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span style="font-size: 14px; font-weight: 500; color: #333333;">Valor primer pago</span>
                        <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                            <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                <div class="srti-tooltip-content" style="font-weight: normal;">
                                    <h4>Valor primer pago</h4>
                                    <p>Este valor figurará en sus formatos de primera cuenta.</p>
                                </div>
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                _n_vpp = st.number_input("Valor primer pago", min_value=0, step=100000, format="%d", label_visibility="collapsed")
            st.markdown(
                """
                <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                    <span style="font-size: 14px; font-weight: 500; color: #333333;">RP / compromiso presupuestal</span>
                    <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                        <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                            <div class="srti-tooltip-content" style="font-weight: normal;">
                                <h4>RP / compromiso presupuestal</h4>
                                <p>Este dato se puede encontrar dentro del cargue de datos financiero en SECOP II.</p>
                            </div>
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            _n_rp = st.text_input("RP / compromiso presupuestal", placeholder="Código alfanumérico", label_visibility="collapsed")
            _nc3, _nc4, _nc5 = st.columns(3)
            with _nc3:
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span style="font-size: 14px; font-weight: 500; color: #333333;">Fecha recurso presupuestal</span>
                        <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                            <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                <div class="srti-tooltip-content" style="font-weight: normal;">
                                    <h4>Fecha recurso presupuestal</h4>
                                    <p>Este dato se puede encontrar dentro del cargue de datos financiero en SECOP II.</p>
                                </div>
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                _n_frp = st.date_input("Fecha recurso presupuestal", value=None, format="DD/MM/YYYY", label_visibility="collapsed")
            with _nc4:
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span style="font-size: 14px; font-weight: 500; color: #333333;">Fecha de inicio contrato</span>
                        <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                            <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                <div class="srti-tooltip-content" style="font-weight: normal;">
                                    <h4>Fecha de inicio contrato</h4>
                                    <p>El dato se puede encontrar en la cláusula del contrato, estudios previos o en la información general del contrato página de firma.</p>
                                </div>
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                _n_fi = st.date_input("Fecha de inicio contrato", value=None, format="DD/MM/YYYY", label_visibility="collapsed")
            with _nc5:
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span style="font-size: 14px; font-weight: 500; color: #333333;">Fecha de fin de contrato</span>
                        <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                            <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                <div class="srti-tooltip-content" style="font-weight: normal;">
                                    <h4>Fecha de fin de contrato</h4>
                                    <p>El dato se puede encontrar en la cláusula del contrato, estudios previos o en la información general del contrato página de firma.</p>
                                </div>
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                _n_ff = st.date_input("Fecha de fin de contrato", value=None, format="DD/MM/YYYY", label_visibility="collapsed")
            _n_obj = st.text_area("Objeto del contrato")
            st.markdown(
                """
                <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                    <span style="font-size: 14px; font-weight: 500; color: #333333;">Radicado del contrato</span>
                    <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                        <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                            <div class="srti-tooltip-content" style="font-weight: normal;">
                                <h4>Radicado del contrato</h4>
                                <p>Este radicado puede ser encontrado en las cláusulas, estudios previos o repositorios del contrato, y será necesario para el Acta de entrega.</p>
                            </div>
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            _n_rad = st.text_input("Radicado del contrato", label_visibility="collapsed")
            _n_env = st.form_submit_button("Agregar contrato", use_container_width=True)
        if _n_env:
            try:
                servicio.agregar_contrato(str(uo["_id"]), {
                    "numero": _n_num.strip(),
                    "tipo": _n_tipo,
                    "valor": _n_valor if _n_valor > 0 else None,
                    "rp_compromiso_presupuestal": _n_rp.strip(),
                    "fecha_inicio": _n_fi,
                    "fecha_fin": _n_ff,
                    "fecha_recurso_presupuestal": _n_frp,
                    "valor_mensual": _n_vm if _n_vm > 0 else None,
                    "valor_primer_pago": _n_vpp if _n_vpp > 0 else None,
                    "objeto": _n_obj.strip(),
                    "radicado_del_contrato": _n_rad.strip() if _n_rad else None,
                })
                st.session_state["mensaje_exito_usuarios"] = "Contrato agregado correctamente."
                st.session_state["last_opened_usuario_id"] = None
                st.rerun()
            except ValueError as e:
                st.error(str(e))


# ── RENDER PRINCIPAL ─────────────────────────────────────────────────────────────

def render(sesion=None):
    servicio = UsuarioService()
    sesion = sesion or obtener_sesion()

    mostrar_titulo_decorado("Administración de usuarios")

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    try:
        validar_permiso(sesion.get("permisos", []), "usuario.ver")
    except ValidacionAutorizacion:
        st.error("No tienes permisos para ver este módulo.")
        st.stop()

    permisos = sesion.get("permisos", [])

    # Mensajes de feedback entre reruns
    if msg := st.session_state.pop("mensaje_exito_usuarios", None):
        st.success(msg)

    # Datos comunes
    usuarios = servicio.listar_usuarios()
    roles_disponibles = [r.get("nombre", "") for r in servicio.repositorio.listar_roles()]
    permisos_disponibles = [p.get("clave", "") for p in servicio.repositorio.listar_permisos()]

    # Catálogos para información laboral (EPS/ARL/AFP/CCF/banco/tipo dependiente)
    mapas = construir_mapas_catalogos()

    # Tabs
    tabs_labels = ["👥 Usuarios"]
    if "usuario.crear" in permisos:
        tabs_labels.append("➕ Nuevo usuario")
    tabs = st.tabs(tabs_labels)

    # ── TAB: LISTADO + FILTROS ───────────────────────────────────────────────────
    with tabs[0]:
        col_h1, col_h2 = st.columns([3, 1])
        with col_h1:
            st.subheader("Listado de usuarios")
        with col_h2:
            if st.button("🔄 Actualizar", width="stretch", key="refresh_usuarios"):
                st.rerun()

        if not usuarios:
            st.info("Todavía no hay usuarios registrados.")
        else:
            # Filtros
            def reset_seleccion():
                st.session_state["last_opened_usuario_id"] = None

            roles_opciones = ["Todos"] + sorted({r for u in usuarios for r in u.get("roles", [])})
            col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
            with col_f1:
                busqueda = st.text_input(
                    "🔍 Buscar",
                    placeholder="Nombre, usuario o correo…",
                    on_change=reset_seleccion,
                    key="filtro_busqueda_usuarios",
                )
            with col_f2:
                filtro_estado = st.selectbox(
                    "Estado",
                    options=["Todos", "Activo", "Inactivo"],
                    on_change=reset_seleccion,
                    key="filtro_estado_usuarios",
                )
            with col_f3:
                filtro_rol = st.selectbox(
                    "Rol",
                    options=roles_opciones,
                    on_change=reset_seleccion,
                    key="filtro_rol_usuarios",
                )

            st.divider()

            # Aplicar filtros
            usuarios_filtrados = usuarios
            if busqueda.strip():
                q = busqueda.strip().lower()
                usuarios_filtrados = [
                    u for u in usuarios_filtrados
                    if q in u.get("usuario", "").lower()
                    or q in u.get("nombre_completo", "").lower()
                    or q in u.get("email", "").lower()
                ]
            if filtro_estado != "Todos":
                activo = filtro_estado == "Activo"
                usuarios_filtrados = [u for u in usuarios_filtrados if u.get("activo", False) == activo]
            if filtro_rol != "Todos":
                usuarios_filtrados = [u for u in usuarios_filtrados if filtro_rol in u.get("roles", [])]

            if not usuarios_filtrados:
                st.info("Ningún usuario coincide con los filtros.")
            else:
                dark_mode = st.session_state.get("dark_mode", False)

                df = pd.DataFrame(
                    [
                        {
                            "_id": str(u["_id"]),
                            "Usuario": u.get("usuario", ""),
                            "Nombre": u.get("nombre_completo", ""),
                            "Correo": u.get("email", ""),
                            "Estado": "Activo" if u.get("activo", False) else "Inactivo",
                            "Roles": ", ".join(u.get("roles", [])),
                        }
                        for u in usuarios_filtrados
                    ]
                )

                def style_rows(row):
                    base = (
                        "background-color: #22223A; color: #F0F0FF; "
                        "border-right: 1px solid rgba(255,255,255,0.10); "
                        "border-bottom: 1px solid rgba(255,255,255,0.11);"
                    ) if dark_mode else ""
                    styles = [base] * len(row)

                    if dark_mode:
                        VERDE = "background-color: #1F4A35; color: #D8FFE8; font-weight:600;"
                        ROJO = "background-color: #5A1F24; color: #FFDDE0; font-weight:600;"
                    else:
                        VERDE = "background-color: #E8F5E9; color: #1B5E20;"
                        ROJO = "background-color: #FFEBEE; color: #B71C1C;"

                    idx_estado = row.index.get_loc("Estado")
                    if row["Estado"] == "Activo":
                        styles[idx_estado] = VERDE
                    else:
                        styles[idx_estado] = ROJO
                    return styles

                df_display = df.drop(columns=["_id"])
                styled_df = df_display.style.apply(style_rows, axis=1)

                # CSS cabeceras
                st.markdown("""
                    <style>
                    [data-testid="stDataFrame"] div[class*="StyledDataGridHeaderCell"] {
                        justify-content: center !important;
                        text-align: center !important;
                    }
                    </style>
                """, unsafe_allow_html=True)

                altura = min(50 + len(df) * 35, 500)
                event = st.dataframe(
                    styled_df,
                    width="stretch",
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    height=altura,
                )

                if event.selection.rows:
                    idx = event.selection.rows[0]
                    id_sel = df.iloc[idx]["_id"]
                    if st.session_state.get("last_opened_usuario_id") != id_sel:
                        st.session_state["last_opened_usuario_id"] = id_sel
                        u_sel = next((u for u in usuarios_filtrados if str(u["_id"]) == id_sel), None)
                        if u_sel:
                            modal_editar_usuario(u_sel, permisos, sesion, roles_disponibles, permisos_disponibles, servicio, mapas)
                else:
                    st.session_state["last_opened_usuario_id"] = None

                st.caption(f"{len(df)} usuario(s) encontrado(s)")

    # ── TAB: CREAR USUARIO ───────────────────────────────────────────────────────
    if "➕ Nuevo usuario" in tabs_labels:
        with tabs[1]:
            st.subheader("Nuevo usuario")

            # Sin st.form: la sección laboral lleva el selector dinámico de
            # dependientes, que necesita re-renderizar al cambiar (no admitido
            # dentro de un form). Los valores se leen al pulsar "Crear usuario".
            st.markdown("##### 🔑 Cuenta y acceso")
            col1, col2 = st.columns(2)
            with col1:
                nuevo_usuario = st.text_input("Usuario", key="crear_usuario")
                nuevo_email = st.text_input("Correo electrónico", key="crear_email")
                nuevo_activo = st.checkbox("Activo", value=True, key="crear_activo")
            with col2:
                nuevo_nombre = st.text_input("Nombre completo", key="crear_nombre")
                nuevo_password = st.text_input("Contraseña", type="password", key="crear_password")

            st.markdown("##### 🪪 Identificación")
            col_tdoc, col_ndoc = st.columns(2)
            with col_tdoc:
                nuevo_tipo_doc = st.selectbox(
                    "Tipo de documento (opcional)",
                    options=list(TIPOS_DOCUMENTO.keys()),
                    format_func=lambda k: TIPOS_DOCUMENTO[k],
                    key="crear_tipo_doc",
                )
            with col_ndoc:
                nuevo_num_doc = st.text_input(
                    "Número de documento (opcional)",
                    placeholder="Solo números",
                    key="crear_num_doc",
                )
                if nuevo_num_doc and not nuevo_num_doc.strip().isdigit():
                    st.error("El número de documento debe contener únicamente números.")
            nuevo_lugar_exp = st.text_input(
                "Lugar de expedición del documento (opcional)",
                placeholder="Ciudad de expedición de la cédula",
                key="crear_lugar_exp",
            )

            st.markdown("##### 🛡️ Roles y permisos")
            nuevos_roles = st.multiselect("Roles", options=roles_disponibles, key="crear_roles")
            nuevos_permisos = st.multiselect("Permisos extra", options=permisos_disponibles, key="crear_permisos")

            st.divider()
            st.markdown("#### 💼 Información laboral")
            il_raw_nuevo = inputs_informacion_laboral("crear", {}, mapas)

            if st.button("Crear usuario", use_container_width=True, type="primary", key="crear_submit"):
                try:
                    datos_nuevo = {
                        "usuario": nuevo_usuario.strip(),
                        "nombre_completo": nuevo_nombre.strip(),
                        "email": nuevo_email.strip(),
                        "password": nuevo_password,
                        "activo": nuevo_activo,
                        "tipo_documento": nuevo_tipo_doc.strip(),
                        "numero_documento": nuevo_num_doc.strip(),
                        "lugar_expedicion_documento": nuevo_lugar_exp.strip(),
                        "roles": nuevos_roles,
                        "permisos_extra": nuevos_permisos,
                        "creado_por": sesion["usuario"],
                    }
                    if not laboral_vacia(il_raw_nuevo):
                        datos_nuevo["informacion_laboral"] = il_raw_nuevo
                    servicio.crear_usuario(datos_nuevo, permisos_usuario=permisos)
                    limpiar_estado_laboral("crear")
                    st.session_state["mensaje_exito_usuarios"] = "Usuario creado correctamente."
                    limpiar_cache_lecturas()
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
