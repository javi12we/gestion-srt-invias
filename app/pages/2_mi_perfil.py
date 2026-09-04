import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from datetime import datetime, timezone

import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado

from app.core.cache_datos import limpiar_cache_lecturas
from app.core.catalogos import TIPOS_CONTRATO
from app.core.sesion import obtener_sesion
from app.core.ui_laboral import (
    boton_guardar_laboral,
    construir_mapas_catalogos,
    inputs_informacion_laboral,
    limpiar_estado_laboral,
    render_seccion_firma,
)
from app.services.auth_service import AuthService
from app.services.usuario_service import DIAS_GRACIA_DESCARGA_FORMATOS, UsuarioService


mostrar_titulo_decorado("Mi perfil")
sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()


def _feedback(tipo: str, mensaje: str, destino: str = "") -> None:
    """Guarda un mensaje de feedback para mostrarlo tras el rerun (persiste, no es toast)."""
    st.session_state["_perfil_msg"] = (tipo, mensaje, destino)


def mostrar_feedback(destino_esperado: str) -> None:
    """Muestra el mensaje de feedback si coincide con el destino esperado y lo elimina."""
    if _msg := st.session_state.get("_perfil_msg"):
        if len(_msg) == 3 and _msg[2] == destino_esperado:
            st.session_state.pop("_perfil_msg", None)
            getattr(st, _msg[0])(_msg[1])
        elif len(_msg) == 2:
            # Fallback para mensajes sin destino: mostrarlos en la primera oportunidad
            st.session_state.pop("_perfil_msg", None)
            getattr(st, _msg[0])(_msg[1])

TIPOS_DOCUMENTO = {
    "": "— Sin especificar —",
    "CC": "CC — Cédula de Ciudadanía",
    "CE": "CE — Cédula de Extranjería",
    "TI": "TI — Tarjeta de Identidad",
    "PA": "PA — Pasaporte",
}

_servicio = UsuarioService()
_usuario_doc = _servicio.obtener_usuario(sesion["id"]) or {}

tab_perfil, tab_laboral, tab_firma, tab_contrato, tab_password = st.tabs(
    ["👤 Perfil", "💼 Información laboral", "✍️ Firma", "📄 Contratos", "🔒 Contraseña"]
)

# ── TAB: PERFIL ──────────────────────────────────────────────────────────────

with tab_perfil:
    st.subheader("Datos de acceso")
    st.write(f"**Usuario:** {sesion['usuario']}")
    st.write(f"**Roles:** {', '.join(sesion.get('roles', [])) or 'Sin roles'}")

    st.divider()
    st.subheader("Editar datos personales")

    tipo_doc_actual = sesion.get("tipo_documento") or ""
    tipo_doc_idx = list(TIPOS_DOCUMENTO.keys()).index(tipo_doc_actual) if tipo_doc_actual in TIPOS_DOCUMENTO else 0

    with st.form("form_editar_perfil"):
        col1, col2 = st.columns(2)
        with col1:
            nuevo_nombre = st.text_input("Nombre completo", value=sesion.get("nombre_completo") or "")
            nuevo_email = st.text_input("Correo electrónico", value=sesion.get("email") or "")
        with col2:
            nuevo_tipo_doc = st.selectbox(
                "Tipo de documento",
                options=list(TIPOS_DOCUMENTO.keys()),
                format_func=lambda k: TIPOS_DOCUMENTO[k],
                index=tipo_doc_idx,
            )
            nuevo_num_doc = st.text_input("Número de documento", value=sesion.get("numero_documento") or "")
            if nuevo_num_doc and not nuevo_num_doc.strip().isdigit():
                st.error("El número de documento debe contener únicamente números.")
        nuevo_lugar_exp = st.text_input(
            "Lugar de expedición del documento",
            value=_usuario_doc.get("lugar_expedicion_documento") or "",
            placeholder="Ciudad de expedición de la cédula",
        )
        st.caption("Los cambios se guardan solo al pulsar el botón. Si sales sin pulsarlo, no se conservan.")
        guardar_perfil = st.form_submit_button("💾 Guardar cambios", use_container_width=True, type="primary")

    mostrar_feedback("perfil")

    if guardar_perfil:
        try:
            _servicio.actualizar_usuario(
                sesion["id"],
                {
                    "nombre_completo": nuevo_nombre.strip(),
                    "email": nuevo_email.strip(),
                    "tipo_documento": nuevo_tipo_doc.strip(),
                    "numero_documento": nuevo_num_doc.strip(),
                    "lugar_expedicion_documento": nuevo_lugar_exp.strip(),
                    "actualizado_por": sesion["usuario"],
                },
                validar_permisos=False,
            )
            st.session_state["usuario_autenticado"].update({
                "nombre_completo": nuevo_nombre.strip(),
                "email": nuevo_email.strip(),
                "tipo_documento": nuevo_tipo_doc.strip(),
                "numero_documento": nuevo_num_doc.strip(),
            })
            _feedback("success", "✅ Datos personales actualizados correctamente.", "perfil")
            limpiar_cache_lecturas()
            st.rerun()
        except ValueError as e:
            st.error(str(e))

# ── TAB: INFORMACIÓN LABORAL ───────────────────────────────────────────────────

with tab_laboral:
    st.subheader("Información laboral")
    st.caption("Seguridad social, datos bancarios, tributarios y dependientes económicos.")

    _mapas = construir_mapas_catalogos()
    _il_actual = _usuario_doc.get("informacion_laboral") or {}
    _il_raw = inputs_informacion_laboral("perfil_lab", _il_actual, _mapas)

    st.divider()
    if boton_guardar_laboral("perfil_lab", _il_raw, key="guardar_lab_perfil"):
        try:
            _servicio.actualizar_usuario(
                sesion["id"],
                {"informacion_laboral": _il_raw, "actualizado_por": sesion["usuario"]},
                validar_permisos=False,
            )
            limpiar_estado_laboral("perfil_lab")
            _feedback("success", "✅ Información laboral guardada correctamente.", "laboral")
            limpiar_cache_lecturas()
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    mostrar_feedback("laboral")

# ── TAB: FIRMA ──────────────────────────────────────────────────────────────────

with tab_firma:
    st.subheader("Firma")
    st.caption("Sube una foto o escaneo de tu firma sobre papel blanco; se procesa para quitar el fondo.")
    render_seccion_firma(
        sesion["id"], sesion["usuario"], "perfil_firma",
        al_terminar=lambda m: _feedback("success", f"✅ {m}", "firma"),
    )
    mostrar_feedback("firma")

# ── TAB: CONTRATOS ────────────────────────────────────────────────────────────

with tab_contrato:
    # Reducir el tamaño de las fuentes y elementos en el panel de contratos por CSS
    st.markdown(
        """
        <style>
        /* Reducir tamaño de las etiquetas de los inputs */
        div[data-testid="stWidgetLabel"] p {
            font-size: 12px !important;
            font-weight: 500 !important;
        }
        /* Reducir tamaño de los inputs y dropdowns */
        div[data-testid="stWidget"] input, div[data-testid="stWidget"] select, div[role="combobox"] {
            font-size: 13px !important;
            padding: 2px 4px !important;
        }
        /* Reducir tamaño de los textos de st.write y st.caption dentro del expander */
        div[data-testid="stExpander"] div.element-container p {
            font-size: 13px !important;
        }
        /* Reducir tamaño de los botones */
        div[data-testid="stWidget"] button {
            font-size: 13px !important;
            padding: 4px 8px !important;
        }
        /* Ajustar espaciado vertical general del expander */
        div[data-testid="stExpander"] {
            margin-bottom: 5px !important;
            padding: 4px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    _contratos = sorted(
        (_usuario_doc.get("contratos") or []),
        key=lambda c: c.get("fecha_inicio") or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )

    # Agregar nuevo contrato
    with st.expander("➕ Agregar nuevo contrato", expanded=len(_contratos) == 0):
        with st.form("form_nuevo_contrato"):
            _nc1, _nc2 = st.columns(2)
            with _nc1:
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span style="font-size: 14px; font-weight: 500; color: #333333;">Numero del contrato *</span>
                        <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                            <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                <div class="srti-tooltip-content" style="font-weight: normal;">
                                    <h4>Numero del contrato</h4>
                                    <p>Este es el numero de serie del contrato, sin adjetivos ni fechas.</p>
                                </div>
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                _n_num_raw = st.text_input("Número de contrato *", label_visibility="collapsed")
                _n_num = "".join(filter(str.isdigit, _n_num_raw))
                if _n_num_raw and not _n_num_raw.isdigit():
                    st.error("El número de contrato debe contener solo dígitos.")
                _n_tipo = st.selectbox(
                    "Tipo de contrato",
                    options=list(TIPOS_CONTRATO.keys()),
                    format_func=lambda k: TIPOS_CONTRATO[k],
                )
            with _nc2:
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span style="font-size: 14px; font-weight: 500; color: #333333;">Valor del contrato (COP)</span>
                        <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                            <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                <div class="srti-tooltip-content" style="font-weight: normal;">
                                    <h4>Valor del contrato (COP)</h4>
                                    <p>Es el valor total del contrato sin adiciones ni disminuciones.</p>
                                </div>
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                _n_valor = st.number_input("Valor del contrato (COP)", min_value=0, step=100000, format="%d", label_visibility="collapsed")
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
                        <span style="font-size: 14px; font-weight: 500; color: #333333;">Personalizar valor última cuenta</span>
                        <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                            <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                <div class="srti-tooltip-content" style="font-weight: normal;">
                                    <h4>Personalizar valor última cuenta</h4>
                                    <p>Active esta función solo si desea personalizar el valor de su última cuenta del contrato, de lo contrario no lo use.</p>
                                </div>
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                _n_personalizar = st.checkbox("Personalizar valor última cuenta", value=False, key="n_personalizar_check")
                _n_val_personalizar = st.number_input(
                    "Valor personalizar última cuenta",
                    min_value=0,
                    value=0,
                    step=100000,
                    format="%d",
                    disabled=not _n_personalizar,
                    label_visibility="collapsed",
                    key="n_personalizar_val"
                )
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
            st.markdown(
                """
                <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                    <span style="font-size: 14px; font-weight: 500; color: #333333;">Objeto del contrato</span>
                    <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                        <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                            <div class="srti-tooltip-content" style="font-weight: normal;">
                                <h4>Objeto del contrato</h4>
                                <p>Objeto del contrato identificable en la cláusula del contrato y deberá escribirlo en mayúscula sostenida.</p>
                            </div>
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            _n_obj = st.text_area("Objeto del contrato", label_visibility="collapsed")
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
            st.caption("El contrato se registra solo al pulsar el botón.")
            _n_env = st.form_submit_button("➕ Agregar contrato", use_container_width=True, type="primary")

        mostrar_feedback("contrato_nuevo")

        if _n_env:
            try:
                _servicio.agregar_contrato(sesion["id"], {
                    "numero": _n_num.strip(),
                    "tipo": _n_tipo,
                    "valor": _n_valor if _n_valor > 0 else None,
                    "rp_compromiso_presupuestal": _n_rp.strip(),
                    "fecha_inicio": _n_fi,
                    "fecha_fin": _n_ff,
                    "fecha_recurso_presupuestal": _n_frp,
                    "valor_mensual": _n_vm if _n_vm > 0 else None,
                    "valor_primer_pago": _n_vpp if _n_vpp > 0 else None,
                    "personalizar_ultimacuenta": _n_personalizar,
                    "valor_personalizar_ultimacuenta": _n_val_personalizar if _n_personalizar else None,
                    "objeto": _n_obj.strip(),
                    "radicado_del_contrato": _n_rad.strip() if _n_rad else None,
                })
                _feedback("success", "✅ Contrato agregado correctamente.", "contrato_nuevo")
                limpiar_cache_lecturas()
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    # Listado de contratos
    if not _contratos:
        st.info("Aún no tienes contratos registrados.")
    else:
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

            with st.expander(f"{_c_num} — {_estado}", expanded=not _c_fin):
                _d1, _d2 = st.columns(2)
                with _d1:
                    st.write(f"**Tipo:** {TIPOS_CONTRATO.get(_c.get('tipo') or '', '—')}")
                    _v = _c.get("valor")
                    st.write(f"**Valor total de contrato:** {'${:,.0f}'.format(_v) if _v else '—'}")
                with _d2:
                    _vm = _c.get("valor_mensual")
                    st.write(f"**Valor mensual:** {'${:,.0f}'.format(_vm) if _vm else '—'}")
                    _vpp = _c.get("valor_primer_pago")
                    st.write(f"**Valor primer pago:** {'${:,.0f}'.format(_vpp) if _vpp else '—'}")
                    if _c.get("personalizar_ultimacuenta"):
                        _vuc = _c.get("valor_personalizar_ultimacuenta")
                        st.write(f"**Valor personalizado última cuenta:** {'${:,.0f}'.format(_vuc) if _vuc else '—'}")
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

                st.write("---")
                _fi_ed = _c_fi.date() if _c_fi and hasattr(_c_fi, "date") else _c_fi
                _ff_ed = _c_ff.date() if _c_ff and hasattr(_c_ff, "date") else _c_ff
                
                # Usamos st.container en vez de st.form porque agregamos pagos dinámicamente
                with st.container():
                    _ec1, _ec2 = st.columns(2)
                    with _ec1:
                        st.markdown(
                            """
                            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                                <span style="font-size: 14px; font-weight: 500; color: #333333;">Numero del contrato</span>
                                <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                                    <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                        <div class="srti-tooltip-content" style="font-weight: normal;">
                                            <h4>Numero del contrato</h4>
                                            <p>Este es el numero de serie del contrato, sin adjetivos ni fechas.</p>
                                        </div>
                                    </span>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        _e_num_raw = st.text_input("Número", value=_c_num, key=f"e_num_{_c_num}", label_visibility="collapsed")
                        _e_num = "".join(filter(str.isdigit, _e_num_raw))
                        if _e_num_raw and not _e_num_raw.isdigit():
                            st.error("El número de contrato debe contener solo dígitos.")
                        _e_tipo_idx = list(TIPOS_CONTRATO.keys()).index(_c.get("tipo") or "") if (_c.get("tipo") or "") in TIPOS_CONTRATO else 0
                        _e_tipo = st.selectbox(
                            "Tipo",
                            options=list(TIPOS_CONTRATO.keys()),
                            format_func=lambda k: TIPOS_CONTRATO[k],
                            index=_e_tipo_idx,
                            key=f"e_tipo_{_c_num}",
                        )
                    with _ec2:
                        st.markdown(
                            """
                            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                                <span style="font-size: 14px; font-weight: 500; color: #333333;">Valor total de contrato (COP)</span>
                                <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                                    <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                        <div class="srti-tooltip-content" style="font-weight: normal;">
                                            <h4>Valor total de contrato (COP)</h4>
                                            <p>Es el valor total del contrato sin adiciones ni disminuciones.</p>
                                        </div>
                                    </span>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        _e_valor = st.number_input(
                            "Valor total de contrato (COP)", min_value=0, value=int(_c.get("valor") or 0),
                            step=100000, format="%d", key=f"e_val_{_c_num}",
                            label_visibility="collapsed"
                        )
                        _e_vm = st.number_input(
                            "Valor mensual (COP)", min_value=0, value=int(_c.get("valor_mensual") or 0),
                            step=100000, format="%d", key=f"e_vm_{_c_num}",
                        )
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
                        _e_vpp = st.number_input(
                            "Valor primer pago", min_value=0, value=int(_c.get("valor_primer_pago") or 0),
                            step=100000, format="%d", key=f"e_vpp_{_c_num}",
                            label_visibility="collapsed"
                        )
                        st.markdown(
                            """
                            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                                <span style="font-size: 14px; font-weight: 500; color: #333333;">Personalizar valor última cuenta</span>
                                <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                                    <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                        <div class="srti-tooltip-content" style="font-weight: normal;">
                                            <h4>Personalizar valor última cuenta</h4>
                                            <p>Active esta función solo si desea personalizar el valor de su última cuenta del contrato, de lo contrario no lo use.</p>
                                        </div>
                                    </span>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        _e_personalizar = st.checkbox(
                            "Personalizar valor última cuenta",
                            value=bool(_c.get("personalizar_ultimacuenta")),
                            key=f"e_personalizar_check_{_c_num}"
                        )
                        _e_val_personalizar = st.number_input(
                            "Valor personalizar última cuenta",
                            min_value=0,
                            value=int(_c.get("valor_personalizar_ultimacuenta") or 0),
                            step=100000,
                            format="%d",
                            disabled=not _e_personalizar,
                            label_visibility="collapsed",
                            key=f"e_personalizar_val_{_c_num}"
                        )
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
                    _e_rp = st.text_input(
                        "RP / compromiso presupuestal", value=_c.get("rp_compromiso_presupuestal") or "",
                        key=f"e_rp_{_c_num}", placeholder="Código alfanumérico", label_visibility="collapsed"
                    )
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
                    st.markdown(
                        """
                        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                            <span style="font-size: 14px; font-weight: 500; color: #333333;">Objeto</span>
                            <div class="srti-tooltip-container" style="margin: 0; display: inline-flex;">
                                <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                                    <div class="srti-tooltip-content" style="font-weight: normal;">
                                        <h4>Objeto del contrato</h4>
                                        <p>Objeto del contrato identificable en la cláusula del contrato y deberá escribirlo en mayúscula sostenida.</p>
                                    </div>
                                </span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    _e_obj = st.text_area("Objeto", value=_c.get("objeto") or "", key=f"e_obj_{_c_num}", label_visibility="collapsed")
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
                    _balance_pagos_datos = render_balance_y_pagos(f"perfil_c_{_c_num}", _c, deshabilitado=_c_fin)
                    
                    _e_env = st.button("💾 Guardar cambios", key=f"btn_save_c_{_c_num}", use_container_width=True, type="primary", disabled=_c_fin)
                    mostrar_feedback(f"contrato_edicion_{_c_num}")

                if _e_env:
                    try:
                        # Combinar campos básicos con los nuevos campos de balance/pagos
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
                            "personalizar_ultimacuenta": _e_personalizar,
                            "valor_personalizar_ultimacuenta": _e_val_personalizar if _e_personalizar else None,
                            "objeto": _e_obj.strip(),
                            "radicado_del_contrato": _e_rad.strip() if _e_rad else None,
                        }
                        datos_totales.update(_balance_pagos_datos)
                        
                        _servicio.editar_contrato(sesion["id"], _c_num, datos_totales)
                        _feedback("success", f"✅ Contrato {_c_num} actualizado correctamente.", f"contrato_edicion_{_c_num}")
                        limpiar_cache_lecturas()
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

# ── TAB: CONTRASEÑA ────────────────────────────────────────────────────────────

with tab_password:
    st.subheader("Cambiar contraseña")

    with st.form("form_cambiar_password"):
        pwd_actual = st.text_input("Contraseña actual", type="password")
        pwd_nueva = st.text_input("Contraseña nueva", type="password")
        pwd_confirmar = st.text_input("Confirmar contraseña nueva", type="password")
        enviar_pwd = st.form_submit_button("🔒 Cambiar contraseña", type="primary")

    mostrar_feedback("password")

    if enviar_pwd:
        if pwd_nueva != pwd_confirmar:
            st.error("❌ Las contraseñas nuevas no coinciden.")
        else:
            auth_service = AuthService()
            exito, mensaje = auth_service.cambiar_password(sesion["id"], pwd_actual, pwd_nueva)
            if exito:
                _feedback("success", f"✅ {mensaje}", "password")
                limpiar_cache_lecturas()
                st.rerun()
            else:
                st.error(f"❌ {mensaje}")
