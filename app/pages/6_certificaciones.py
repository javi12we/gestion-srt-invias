import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

"""Página de certificaciones mensuales — vista del colaborador.

Cada usuario ve el estado de su certificación del mes actual
y el historial de certificados anteriores con opción de descarga PDF.
"""

import os

import streamlit as st
from app.config import configuracion
from app.core.ui_titulos import mostrar_titulo_decorado

from app.core.sesion import obtener_sesion
from app.core.ui_certificado import render_preview_cert
from app.core.zona_horaria import formato_fecha_bogota
from app.services.certificacion_service import CertificacionService, MESES_ES, ORDEN_FIRMAS_ACTAS
from app.services.usuario_service import UsuarioService


def _badge_estado(estado: str | None) -> str:
    if estado == "aprobado":
        return "✅ **Certificado**"
    return "⏳ Pendiente de aprobación"


# Prefijo de nombre de archivo por tipo de formato. Los formatos sin
# tipo_formato (p. ej. el control de correspondencia) usan el prefijo por defecto.
_PREFIJO_ARCHIVO = {
    "dependencia_economica": "Condicion_Declarante",
    "cuenta_cobro": "Cuenta_Cobro",
    "retencion_fuente_primera": "Retencion_Fuente_Primera",
    "retencion_fuente_segunda": "Retencion_Fuente_Segunda",
    "acta_compromiso": "Acta_Compromiso",
    "acta_recibo_entrega_cps": "Balance_General_CPS",
    "acta_recibo_entrega_cps_real": "Acta_Recibo_Entrega_CPS",
    "informe_actividades_final_cps": "Informe_Actividades_Final",
}
_PREFIJO_ARCHIVO_DEFAULT = "Certificado_correspondencia"


_LABEL_ROL_ACTAS = {
    "financiera": "Financiera",
    "abogado": "Jurídico",
    "jefe": "Jefe inmediato",
}


def _mostrar_avance_actas(tipo_formato: str, cert_actual: dict) -> None:
    """Stepper de avance de firmas para los formatos de actas (financiera/abogado/jefe)."""
    firmas = (cert_actual or {}).get("firmas", {}) or {}
    orden = ORDEN_FIRMAS_ACTAS.get(tipo_formato, ())
    pasos = [
        f"✅ {_LABEL_ROL_ACTAS[rol]}" if firmas.get(rol) else f"⏳ {_LABEL_ROL_ACTAS[rol]}"
        for rol in orden
    ]
    st.markdown(" &nbsp;→&nbsp; ".join(pasos))

    eventos = (cert_actual or {}).get("eventos") or []
    if eventos:
        ultimo = eventos[-1]
        rol_afectado = ultimo.get("rol_revocado")
        if rol_afectado and not firmas.get(rol_afectado):
            causante = _LABEL_ROL_ACTAS.get(ultimo.get("causada_por"), ultimo.get("causada_por"))
            st.caption(
                f"⚠️ La firma de **{_LABEL_ROL_ACTAS.get(rol_afectado, rol_afectado)}** fue removida "
                f"porque **{causante}** revocó la suya."
            )


def _nombre_archivo_pdf(cert: dict, mes_nombre: str, año) -> str:
    """Construye el nombre del PDF según el tipo de formato del certificado."""
    prefijo = _PREFIJO_ARCHIVO.get(cert.get("tipo_formato"), _PREFIJO_ARCHIVO_DEFAULT)
    return f"{prefijo}_{mes_nombre}_{año}.pdf"


def _nombre_archivo_docx(cert: dict, mes_nombre: str, año) -> str:
    """Construye el nombre del .docx según el tipo de formato del certificado."""
    prefijo = _PREFIJO_ARCHIVO.get(cert.get("tipo_formato"), _PREFIJO_ARCHIVO_DEFAULT)
    return f"{prefijo}_{mes_nombre}_{año}.docx"


@st.dialog("Vista previa del certificado", width="large")
def _dialog_preview_cert(servicio: CertificacionService) -> None:
    data = st.session_state.pop("_preview_cert_user", None)
    if not data:
        return

    pdf_bytes = servicio.generar_pdf(data["cert"])
    mes_nombre = data["mes_nombre"]
    año = data["año"]

    tipo_formato = data["cert"].get("tipo_formato")
    show_dl = tipo_formato not in [
        "acta_compromiso",
        "acta_recibo_entrega_cps",
        "acta_recibo_entrega_cps_real"
    ]

    render_preview_cert(
        pdf_bytes=pdf_bytes,
        caption=f"{mes_nombre} {año}",
        file_name=_nombre_archivo_pdf(data["cert"], mes_nombre, año),
        dl_key="_dl_preview_user",
        show_download=show_dl,
    )


_META_FIRMA = {
    "corr":  ("F. Corr",  "Correspondencia"),
    "gd":    ("F. GD",    "Gestión Documental"),
    "secop": ("F. SECOP", "SECOP II"),
}


def _mostrar_avance(servicio: CertificacionService, usuario_id: str, año: int, mes: int, cert_actual) -> None:
    from app.repositories.usuario_repo import UsuarioRepositorio

    firmas = cert_actual.get("firmas", {}) if cert_actual else {}

    usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
    contratos = usuario_data.get("contratos") or []
    contrato = servicio._contrato_relevante(contratos, año, mes)
    tiene_contrato = bool(contrato.get("numero"))

    n_firmas = sum(1 for t in _META_FIRMA if firmas.get(t))
    total = len(_META_FIRMA)

    avance_extra = "" if tiene_contrato else " · ❌ Sin contrato"
    st.markdown(f"##### Avance: {n_firmas}/{total} aprobaciones{avance_extra}")

    if n_firmas == total and not tiene_contrato:
        st.warning(
            "✅ Tienes las **3 aprobaciones** del período, pero el certificado no pudo "
            "generarse porque **no tienes un contrato activo** registrado. "
            "Ve a **Mi Perfil** y registra tu contrato para completar el proceso."
        )

    col_firmas, col_contrato = st.columns([3, 2])

    with col_firmas:
        st.markdown("**Aprobaciones requeridas**")
        for tipo, (_, label_largo) in _META_FIRMA.items():
            f = firmas.get(tipo)
            if f:
                fecha_str = formato_fecha_bogota(f.get("fecha"), "%d/%m/%Y %H:%M")
                st.markdown(
                    f"✅ &nbsp;**{label_largo}**  \n"
                    f"<span style='font-size:.82em;color:#888;'>{f.get('firmante_nombre', '')} · {fecha_str}</span>",
                    unsafe_allow_html=True,
                )
                if f.get("comentario"):
                    st.caption(f"💬 *{f['comentario']}*")
            else:
                st.markdown(f"⏳ &nbsp;**{label_largo}** — pendiente")

    with col_contrato:
        st.markdown("**Contrato activo**")
        if tiene_contrato:
            st.markdown(f"✅ &nbsp;Contrato **{contrato['numero']}**")
        else:
            st.markdown("❌ &nbsp;Sin contrato activo")
            st.caption(
                "Para que tu certificado pueda generarse necesitas tener "
                "un contrato activo registrado."
            )
            st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")


def _render_verificador_codigo(servicio: CertificacionService):
    mostrar_titulo_decorado("Verificar formato")
    st.caption(
        "Ingresa el código que aparece en el recuadro inferior del certificado PDF "
        "para comprobar su autenticidad. Un certificado genuino siempre devuelve "
        "resultado positivo con los datos exactos del titular."
    )
    codigo = st.text_input("Código de verificación", placeholder="XXXX-XXXX-XXXX-XXXX", max_chars=19)
    if st.button("Verificar autenticidad", type="primary"):
        codigo_limpio = codigo.strip().upper().replace(" ", "")
        if not codigo_limpio:
            st.warning("Ingresa el código de verificación antes de continuar.")
            return

        cert = servicio.verificar_certificado(codigo_limpio)
        if cert:
            nombre = cert.get("nombre_usuario", "")
            año = cert.get("año", "")
            mes_num = cert.get("mes", 1)
            mes_nombre = MESES_ES[mes_num - 1]
            aprobado_por = cert.get("aprobado_por", {})
            fecha_ap = aprobado_por.get("fecha")
            fecha_str = formato_fecha_bogota(fecha_ap, "%d de %B de %Y a las %H:%M") if fecha_ap else "—"

            st.success("Certificado válido — documento auténtico")
            with st.container(border=True):
                st.markdown(f"**Titular:** {nombre}")
                st.markdown(f"**Período certificado:** {mes_nombre} {año}")
                st.markdown(f"**Emitido por:** {aprobado_por.get('nombre', '—')} · {fecha_str}")
                if cert.get("observaciones"):
                    st.caption(f"Observaciones: {cert['observaciones']}")

            pdf_bytes = servicio.generar_pdf(cert)
            nombre_archivo = _nombre_archivo_pdf(cert, mes_nombre, año)
            st.download_button(
                label="⬇️ Descargar certificado verificado",
                data=pdf_bytes,
                file_name=nombre_archivo,
                mime="application/pdf",
                type="primary",
            )
        else:
            st.error("Código no encontrado. El certificado puede ser falso, haber sido revocado o el código fue transcrito incorrectamente.")
            st.caption("Revisa que el código esté completo y en el formato XXXX-XXXX-XXXX-XXXX.")


def _render_opcion_6_gestion_corr(servicio, usuario_id, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    mostrar_titulo_decorado("Formato de control a la correspondencia - Gestión documental - SECOP II")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, año=año_cert, mes=mes_cert)

    if cert_actual and cert_actual.get("estado") != "aprobado":
        if servicio.recuperar_auto_cert(usuario_id, cert_actual):
            cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, año=año_cert, mes=mes_cert)

    if cert_actual and cert_actual.get("estado") == "aprobado":
        aprobado_por = cert_actual.get("aprobado_por", {})
        fecha_corte = aprobado_por.get("fecha")
        fecha_str = formato_fecha_bogota(fecha_corte, "%d/%m/%Y %H:%M")

        st.success(
            f"Tu certificado de **{nombre_mes_cert} {año_cert}** está aprobado.\n\n"
            f"Aprobado por **{aprobado_por.get('nombre', '')}** el {fecha_str}."
        )

        if cert_actual.get("observaciones"):
            st.info(f"Observación del supervisor: {cert_actual['observaciones']}")

        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del certificado: {e}")
            pdf_bytes = None

        if pdf_bytes:
            nombre_archivo = _nombre_archivo_pdf(cert_actual, nombre_mes_cert, año_cert)
            c_dl, c_prev = st.columns(2)
            with c_dl:
                st.download_button(
                    "⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=nombre_archivo,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            with c_prev:
                if st.button("👁️ Ver certificado", use_container_width=True):
                    st.session_state["_preview_cert_user"] = {
                        "cert": cert_actual,
                        "mes_nombre": nombre_mes_cert,
                        "año": año_cert,
                    }
                    st.rerun()
    else:
        st.warning(f"Tu certificado de **{nombre_mes_cert} {año_cert}** aún está en proceso.")
        _mostrar_avance(servicio, usuario_id, año_cert, mes_cert, cert_actual)


def _render_opcion_7_herramientas():
    """Viñeta 7 — acceso a plataformas externas (ADRES, SECOP II, KLIC 2, AZ Digital, Her. PDF)."""
    from app.core.recursos import imagen_b64

    mostrar_titulo_decorado("🌐 Otros certificados · Herramientas")
    st.caption("Haz clic en cualquier imagen para abrir la plataforma en una nueva pestaña.")
    st.write("")

    PLATAFORMAS = [
        {
            "img": os.path.join("app", "assets", "az_digital.png"),
            "name": "AZ Digital",
            "desc": "Carpeta digital de gestión documental",
            "url": configuracion.az_digital_url,
        },
        {
            "img": os.path.join("app", "assets", "klic_2.png"),
            "name": "KLIC 2",
            "desc": "Sistema de correspondencia INVIAS",
            "url": configuracion.klic_2_url,
        },
        {
            "img": os.path.join("app", "assets", "adres.png"),
            "name": "ADRES",
            "desc": "Administradora de Recursos del SGSSS",
            "url": configuracion.adres_url,
        },
        {
            "img": os.path.join("app", "assets", "secop.png"),
            "name": "SECOP II",
            "desc": "Sistema Electrónico de Contratación Pública",
            "url": configuracion.secop_url,
        },
        {
            "img": os.path.join("app", "assets", "pdf_h.png"),
            "name": "Her. PDF",
            "desc": "Herramienta de edición y gestión PDF",
            "url": configuracion.pdf_h_url,
        },
        {
            "img": os.path.join("app", "assets", "procuraduria_logo.png"),
            "name": "Procuraduría",
            "desc": "Certificado de antecedentes disciplinarios",
            "url": configuracion.url_procuraduria,
        },
        {
            "img": os.path.join("app", "assets", "contraloria_logo.png"),
            "name": "Contraloría",
            "desc": "Certificado de antecedentes fiscales",
            "url": configuracion.url_contraloria,
        },
        {
            "img": os.path.join("app", "assets", "policia_logo.png"),
            "name": "Policía Antecedentes",
            "desc": "Certificado de antecedentes judiciales (Policía).",
            "url": configuracion.url_pol_antecedentes,
        },
        {
            "img": os.path.join("app", "assets", "policia_RCMC.png"),
            "name": "Policía RNMC",
            "desc": "Certificado de medidas correctivas (RNMC)",
            "url": configuracion.url_pol_rcmc,
        },
        {
            "img": os.path.join("app", "assets", "rut_dian.png"),
            "name": "RUT (DIAN)",
            "desc": 'Descargar Rut (Virtual) "Requiere cuenta Virtual en la DIAN"',
            "url": configuracion.url_rut,
        },
    ]

    def _card(plat: dict, delay_ms: int = 0) -> str:
        b64 = imagen_b64(plat["img"])
        img_tag = (
            f'<img src="data:image/png;base64,{b64}" alt="{plat["name"]}" '
            f'style="max-height:80px;max-width:100%;object-fit:contain;'
            f'transition:transform 0.22s ease;" />'
            if b64 else ""
        )
        # Si hay URL, toda la imagen es un enlace; si no, solo muestra la imagen
        if plat["url"]:
            content = (
                f'<a href="{plat["url"]}" target="_blank" rel="noopener noreferrer" '
                f'style="display:block;text-decoration:none;">'
                f'{img_tag}'
                f'</a>'
            )
        else:
            content = img_tag

        return f"""
        <div style="
            border: 1.5px solid rgba(255,140,0,0.28);
            border-radius: 16px;
            padding: 22px 16px 16px;
            text-align: center;
            background: transparent;
            transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
            animation: fadeCardIn7 0.4s ease {delay_ms}ms both;
            cursor: {'pointer' if plat['url'] else 'default'};
        " onmouseover="this.style.transform='translateY(-5px)';this.style.boxShadow='0 10px 32px rgba(255,140,0,0.22)';this.style.borderColor='rgba(255,140,0,0.60)'"
           onmouseout="this.style.transform='';this.style.boxShadow='';this.style.borderColor='rgba(255,140,0,0.28)'">
            {content}
            <div style="font-weight:700;font-size:0.96em;margin:10px 0 3px;color:#FF8C00;">{plat["name"]}</div>
            <div style="font-size:0.78em;color:#888;">{plat["desc"]}</div>
        </div>
        """

    # CSS de animación (una sola vez)
    st.markdown(
        """
        <style>
        @keyframes fadeCardIn7 {
            from { opacity: 0; transform: translateY(16px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Renderizado en filas de 3 columnas ──────────────────────────────────────────
    for r in range(0, len(PLATAFORMAS), 3):
        cols = st.columns(3, gap="medium")
        row_plats = PLATAFORMAS[r:r+3]
        for c_idx, plat in enumerate(row_plats):
            with cols[c_idx]:
                st.markdown(_card(plat, delay_ms=(r + c_idx) * 80), unsafe_allow_html=True)
        st.write("")


def _render_opcion_8_historial(servicio, usuario_id, año_cert, mes_cert, bloqueado=False):
    mostrar_titulo_decorado("Historial de formatos")

    if bloqueado:
        _aviso_bloqueado()
        return

    historial = servicio.obtener_historial(usuario_id)

    historial_pasado = [
        c for c in historial
        if not (c.get("año") == año_cert and c.get("mes") == mes_cert)
    ]

    if not historial_pasado:
        st.caption("Aún no tienes formatos de meses anteriores.")
    else:
        for cert in historial_pasado:
            mes_num = cert.get("mes", 1)
            año_cert_hist = cert.get("año", "")
            mes_nombre = MESES_ES[mes_num - 1]
            estado = cert.get("estado")

            with st.container(border=True):
                c_info, c_btn = st.columns([4, 1])

                with c_info:
                    st.markdown(
                        f"**{mes_nombre} {año_cert_hist}** &nbsp; {_badge_estado(estado)}",
                        unsafe_allow_html=False,
                    )
                    if estado == "aprobado":
                        aprobado_por = cert.get("aprobado_por", {})
                        fecha_ap = aprobado_por.get("fecha")
                        fecha_str = formato_fecha_bogota(fecha_ap, "%d/%m/%Y")
                        st.caption(
                            f"Aprobado por {aprobado_por.get('nombre', '')} · {fecha_str}"
                        )
                    if cert.get("observaciones"):
                        st.caption(f"Obs: {cert['observaciones']}")

                with c_btn:
                    if estado == "aprobado":
                        pdf_bytes = servicio.generar_pdf(cert)
                        nombre_archivo = _nombre_archivo_pdf(cert, mes_nombre, año_cert_hist)
                        cert_id = str(cert.get("_id", ""))
                        st.download_button(
                            "⬇️ PDF",
                            data=pdf_bytes,
                            file_name=nombre_archivo,
                            mime="application/pdf",
                            key=f"dl_{cert_id}",
                            use_container_width=True,
                        )
                        if st.button("👁️ Ver", key=f"prev_{cert_id}", use_container_width=True):
                            st.session_state["_preview_cert_user"] = {
                                "cert": cert,
                                "mes_nombre": mes_nombre,
                                "año": año_cert_hist,
                            }
                            st.rerun()


def _render_opcion_1_cuenta_cobro(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Cuenta de Cobro")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "cuenta_cobro", año=año_cert, mes=mes_cert)

    if cert_actual:
        st.success(
            f"Tu formato de **Cuenta de cobro** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )
        
        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del formato: {e}")
            pdf_bytes = None

        if pdf_bytes:
            nombre_archivo = _nombre_archivo_pdf(cert_actual, nombre_mes_cert, año_cert)
            c_dl, c_prev = st.columns(2)
            with c_dl:
                st.download_button(
                    "⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=nombre_archivo,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            with c_prev:
                if st.button("👁️ Ver formato", use_container_width=True):
                    st.session_state["_preview_cert_user"] = {
                        "cert": cert_actual,
                        "mes_nombre": nombre_mes_cert,
                        "año": año_cert,
                    }
                    st.rerun()
    else:
        st.warning(f"Aún no has generado el formato para el período **{nombre_mes_cert} {año_cert}**.")
        
        # Mostrar resumen de datos del usuario
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
        info_laboral = usuario_data.get("informacion_laboral") or {}
        bancaria = info_laboral.get("bancaria") or {}
        
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)

        st.write("### Datos para generación de formato")
        st.write(f"**Contratista:** {usuario_data.get('nombre_completo', '')}")
        st.write(f"**Identificación:** {usuario_data.get('tipo_documento', '')} Nº {usuario_data.get('numero_documento', '')}")
        st.write(f"**Lugar de expedición:** {usuario_data.get('lugar_expedicion_documento', '—')}")

        from app.services.opciones_service import OpcionesService
        banco_clave = bancaria.get("banco")
        banco_nombre = (
            OpcionesService().obtener_etiqueta_por_clave("banco", banco_clave)
            if banco_clave else "No registrado"
        )
        st.write(f"**Banco:** {banco_nombre}")
        st.write(f"**Cuenta:** {bancaria.get('numero_cuenta') or 'No registrada'}")

        if contrato_vig:
            st.write(f"**Contrato:** {contrato_vig.get('numero', '')}")
            st.write(f"**Honorarios Mensuales:** $ {contrato_vig.get('valor_mensual', 0):,}")
            st.write(f"**RP Compromiso Presupuestal:** {contrato_vig.get('rp_compromiso_presupuestal') or '—'}")
        else:
            st.write("**Contrato:** No se detectó contrato vigente")
            
        st.caption("Si alguno de estos datos es incorrecto o deseas modificarlo, ve a tu perfil.")
        st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")
        
        st.write("---")
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_cuenta_cobro(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
                st.success("¡Formato generado y firmado digitalmente con éxito!")
                st.rerun()


def _render_opcion_2_retencion_primera(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Disminución Base Retención en la Fuente Contrato - Primera Cuenta")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "retencion_fuente_primera", año=año_cert, mes=mes_cert)

    if cert_actual:
        st.success(
            f"Tu formato de **Retención en la fuente Primera cuenta** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )
        
        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del formato: {e}")
            pdf_bytes = None

        if pdf_bytes:
            nombre_archivo = _nombre_archivo_pdf(cert_actual, nombre_mes_cert, año_cert)
            c_dl, c_prev = st.columns(2)
            with c_dl:
                st.download_button(
                    "⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=nombre_archivo,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            with c_prev:
                if st.button("👁️ Ver formato", use_container_width=True):
                    st.session_state["_preview_cert_user"] = {
                        "cert": cert_actual,
                        "mes_nombre": nombre_mes_exp_val if 'nombre_mes_exp_val' in locals() else nombre_mes_cert,
                        "año": año_cert,
                    }
                    st.rerun()
    else:
        st.warning(f"Aún no has generado el formato para el período **{nombre_mes_cert} {año_cert}**.")
        
        # Mostrar resumen de datos del usuario
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
        info_laboral = usuario_data.get("informacion_laboral") or {}
        tributaria = info_laboral.get("tributaria") or {}
        declarante_renta = tributaria.get("declarante_renta", False)
        
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)

        st.write("### Datos para generación de formato")
        st.write(f"**Contratista:** {usuario_data.get('nombre_completo', '')}")
        st.write(f"**Identificación:** {usuario_data.get('tipo_documento', '')} Nº {usuario_data.get('numero_documento', '')}")
        st.write(f"**Lugar de expedición:** {usuario_data.get('lugar_expedicion_documento', '—')}")

        renta_str = "Declarante de Renta" if declarante_renta else "No Declarante de Renta"
        st.write(f"**Condición Tributaria:** {renta_str}")
        st.write(f"**RUT:** {tributaria.get('rut') or 'No registrado'}")

        from app.services.opciones_service import OpcionesService
        regimen_clave = tributaria.get("regimen")
        regimen_etiqueta = (
            OpcionesService().obtener_etiqueta_por_clave("regimen_tributario", regimen_clave)
            if regimen_clave else "No registrado"
        )
        st.write(f"**Régimen tributario:** {regimen_etiqueta}")

        if contrato_vig:
            st.write(f"**Contrato:** {contrato_vig.get('numero', '')}")
            st.write(f"**Valor total contrato:** $ {contrato_vig.get('valor', 0):,}")
            st.write(f"**Honorarios Mensuales:** $ {contrato_vig.get('valor_mensual', 0):,}")
        else:
            st.write("**Contrato:** No se detectó contrato vigente")

        st.caption("Si alguno de estos datos es incorrecto o deseas modificarlo, ve a tu perfil.")
        st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")

        st.write("---")
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_retencion_primera(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
                st.success("¡Formato generado y firmado digitalmente con éxito!")
                st.rerun()


def _render_opcion_3_retencion_segunda(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Disminución Base Retención en la Fuente Contrato - Segunda Cuenta ++")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "retencion_fuente_segunda", año=año_cert, mes=mes_cert)

    if cert_actual:
        st.success(
            f"Tu formato de **Retención en la fuente Segunda cuenta** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )
        
        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del formato: {e}")
            pdf_bytes = None

        if pdf_bytes:
            nombre_archivo = _nombre_archivo_pdf(cert_actual, nombre_mes_cert, año_cert)
            c_dl, c_prev = st.columns(2)
            with c_dl:
                st.download_button(
                    "⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=nombre_archivo,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            with c_prev:
                if st.button("👁️ Ver formato", use_container_width=True):
                    st.session_state["_preview_cert_user"] = {
                        "cert": cert_actual,
                        "mes_nombre": nombre_mes_cert,
                        "año": año_cert,
                    }
                    st.rerun()
    else:
        st.warning(f"Aún no has generado el formato para el período **{nombre_mes_cert} {año_cert}**.")
        
        # Mostrar resumen de datos del usuario
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
        info_laboral = usuario_data.get("informacion_laboral") or {}
        tributaria = info_laboral.get("tributaria") or {}
        declarante_renta = tributaria.get("declarante_renta", False)
        
        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)

        st.write("### Datos para generación de formato")
        st.write(f"**Contratista:** {usuario_data.get('nombre_completo', '')}")
        st.write(f"**Identificación:** {usuario_data.get('tipo_documento', '')} Nº {usuario_data.get('numero_documento', '')}")
        st.write(f"**Lugar de expedición:** {usuario_data.get('lugar_expedicion_documento', '—')}")

        renta_str = "Declarante de Renta" if declarante_renta else "No Declarante de Renta"
        st.write(f"**Condición Tributaria:** {renta_str}")
        st.write(f"**RUT:** {tributaria.get('rut') or 'No registrado'}")

        from app.services.opciones_service import OpcionesService
        regimen_clave = tributaria.get("regimen")
        regimen_etiqueta = (
            OpcionesService().obtener_etiqueta_por_clave("regimen_tributario", regimen_clave)
            if regimen_clave else "No registrado"
        )
        st.write(f"**Régimen tributario:** {regimen_etiqueta}")

        if contrato_vig:
            st.write(f"**Contrato:** {contrato_vig.get('numero', '')}")
            st.write(f"**Valor total contrato:** $ {contrato_vig.get('valor', 0):,}")
            st.write(f"**Honorarios Mensuales:** $ {contrato_vig.get('valor_mensual', 0):,}")
        else:
            st.write("**Contrato:** No se detectó contrato vigente")

        st.caption("Si alguno de estos datos es incorrecto o deseas modificarlo, ve a tu perfil.")
        st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")

        st.write("---")
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_retencion_segunda(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
                st.success("¡Formato generado y firmado digitalmente con éxito!")
                st.rerun()


def _render_opcion_4_declarante_dependencia(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Condición de Declarante y Existencia y Dependencia Económica")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "dependencia_economica", año=año_cert, mes=mes_cert)

    if cert_actual:
        st.success(
            f"Tu formato de **Condición de Declarante y Dependencia Económica** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )
        
        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del formato: {e}")
            pdf_bytes = None

        if pdf_bytes:
            nombre_archivo = _nombre_archivo_pdf(cert_actual, nombre_mes_cert, año_cert)
            c_dl, c_prev = st.columns(2)
            with c_dl:
                st.download_button(
                    "⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=nombre_archivo,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            with c_prev:
                if st.button("👁️ Ver formato", use_container_width=True):
                    st.session_state["_preview_cert_user"] = {
                        "cert": cert_actual,
                        "mes_nombre": nombre_mes_cert,
                        "año": año_cert,
                    }
                    st.rerun()
    else:
        st.warning(f"Aún no has generado el formato para el período **{nombre_mes_cert} {año_cert}**.")
        
        # Mostrar resumen de datos del usuario
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
        info_laboral = usuario_data.get("informacion_laboral") or {}
        tributaria = info_laboral.get("tributaria") or {}
        declarante_renta = tributaria.get("declarante_renta", False)
        dependientes = info_laboral.get("dependientes") or []

        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)

        st.write("### Datos para generación de formato")
        st.write(f"**Contratista:** {usuario_data.get('nombre_completo', '')}")
        st.write(f"**Identificación:** {usuario_data.get('tipo_documento', '')} Nº {usuario_data.get('numero_documento', '')}")
        st.write(f"**Lugar de expedición:** {usuario_data.get('lugar_expedicion_documento', '—')}")

        if contrato_vig:
            st.write(f"**Contrato:** {contrato_vig.get('numero', '')}")
        else:
            st.write("**Contrato:** No se detectó contrato vigente")

        renta_str = "Declarante de Renta" if declarante_renta else "No Declarante de Renta"
        st.write(f"**Condición Tributaria:** {renta_str}")

        st.write("**Dependientes Económicos:**")
        if dependientes:
            import pandas as pd
            df_dep = pd.DataFrame(dependientes)
            df_dep.columns = ["Nombre", "Tipo Documento", "Número Documento", "Tipo Dependiente"]
            st.table(df_dep)
        else:
            st.info("No tienes dependientes económicos registrados. Se generará la tabla en blanco.")

        st.caption("Si alguno de estos datos es incorrecto o deseas modificarlo, ve a tu perfil.")
        st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")
        
        st.write("---")
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_dependencia(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
                st.success("¡Formato generado y firmado digitalmente con éxito!")
                st.rerun()


def _render_opcion_5_acta_compromiso(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Acta de Compromiso")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "acta_compromiso", año=año_cert, mes=mes_cert)

    if cert_actual and cert_actual.get("estado") == "aprobado":
        st.success(
            f"Tu formato de **Acta de compromiso** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )

        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del formato: {e}")
            pdf_bytes = None

        if pdf_bytes:
            if st.button("👁️ Ver formato", type="primary", use_container_width=True):
                st.session_state["_preview_cert_user"] = {
                    "cert": cert_actual,
                    "mes_nombre": nombre_mes_cert,
                    "año": año_cert,
                }
                st.rerun()
    elif cert_actual:
        st.info(
            f"Tu formato de **Acta de compromiso** para **{nombre_mes_cert} {año_cert}** "
            "fue generado y está en espera de aprobación."
        )
        _mostrar_avance_actas("acta_compromiso", cert_actual)
    else:
        st.warning(f"Aún no has generado el formato para el período **{nombre_mes_cert} {año_cert}**.")
        
        # Mostrar resumen de datos del usuario
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
        info_laboral = usuario_data.get("informacion_laboral") or {}
        seg_social = info_laboral.get("seguridad_social") or {}

        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)

        st.write("### Datos para generación de formato")
        st.write(f"**Contratista:** {usuario_data.get('nombre_completo', '')}")
        st.write(f"**Identificación:** {usuario_data.get('tipo_documento', '')} Nº {usuario_data.get('numero_documento', '')}")
        st.write(f"**Lugar de expedición:** {usuario_data.get('lugar_expedicion_documento', '—')}")

        if contrato_vig:
            st.write(f"**Contrato:** {contrato_vig.get('numero', '')}")
            st.write(f"**Vigencia del Contrato:** {contrato_vig.get('fecha_inicio').strftime('%d/%m/%Y') if contrato_vig.get('fecha_inicio') else '—'} a {contrato_vig.get('fecha_fin').strftime('%d/%m/%Y') if contrato_vig.get('fecha_fin') else '—'}")
        else:
            st.write("**Contrato:** No se detectó contrato vigente")

        # AFP
        afp_obj = seg_social.get("afp") or {}
        afp_val = afp_obj.get("valor")
        afp_str = f"$ {afp_val:,.0f}" if afp_val is not None else (afp_obj.get("entidad") or "No registrada")

        # EPS
        eps_obj = seg_social.get("eps") or {}
        eps_val = eps_obj.get("valor")
        eps_str = f"$ {eps_val:,.0f}" if eps_val is not None else (eps_obj.get("entidad") or "No registrada")

        # ARL
        arl_obj = seg_social.get("arl") or {}
        arl_val = arl_obj.get("valor")
        arl_str = f"$ {arl_val:,.0f}" if arl_val is not None else (arl_obj.get("entidad") or "No registrada")

        # IBC
        ibc_val = info_laboral.get("ibc_prestaciones_sociales")
        ibc_str = f"$ {ibc_val:,.0f}" if ibc_val is not None else "No registrado"

        st.write(f"**Ingreso Base de Cotización:** {ibc_str}")
        st.write(f"**AFP:** {afp_str}")
        st.write(f"**EPS:** {eps_str}")
        st.write(f"**ARL:** {arl_str}")
            
        st.caption("Si alguno de estos datos es incorrecto o deseas modificarlo, ve a tu perfil.")
        st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")
        
        st.write("---")
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_acta_compromiso(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
                st.success("¡Formato generado y firmado digitalmente con éxito!")
                st.rerun()


def _render_opcion_9_acta_recibo_entrega_real(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Acta de recibo y entrega CPS")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "acta_recibo_entrega_cps_real", año=año_cert, mes=mes_cert)

    if cert_actual and cert_actual.get("estado") == "aprobado":
        st.success(
            f"Tu formato de **Acta de recibo y entrega CPS** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )

        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del formato: {e}")
            pdf_bytes = None

        if pdf_bytes:
            if st.button("👁️ Ver formato", type="primary", use_container_width=True):
                st.session_state["_preview_cert_user"] = {
                    "cert": cert_actual,
                    "mes_nombre": nombre_mes_cert,
                    "año": año_cert,
                }
                st.rerun()
    elif cert_actual:
        st.info(
            f"Tu formato de **Acta de recibo y entrega CPS** para **{nombre_mes_cert} {año_cert}** "
            "fue generado y está en espera de aprobación."
        )
        _mostrar_avance_actas("acta_recibo_entrega_cps_real", cert_actual)
    else:
        # Validar requisitos específicos de Acta de Recibo y Entrega CPS
        from app.services.usuario_service import UsuarioService
        req_acta = UsuarioService().validar_datos_acta_recibo_entrega_cps(usuario_id)
        if not req_acta["valido"]:
            st.warning(
                "⚠️ **Requisitos para habilitar el Acta de Recibo y Entrega CPS**\n\n"
                "Para poder generar y firmar digitalmente este formato, debes completar "
                "los siguientes datos obligatorios en tu contrato activo en **Mi Perfil**:\n\n" +
                "\n".join([f"- {item}" for item in req_acta["faltantes"]])
            )
            st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")
            return

        st.warning(f"Aún no has generado el formato para el período **{nombre_mes_cert} {año_cert}**.")
        
        # Mostrar resumen de datos del usuario
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}

        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)

        st.write("### Datos para generación de formato")
        st.write(f"**Contratista:** {usuario_data.get('nombre_completo', '')}")
        st.write(f"**Identificación:** {usuario_data.get('tipo_documento', '')} Nº {usuario_data.get('numero_documento', '')}")
        if contrato_vig:
            st.write(f"**Contrato:** {contrato_vig.get('numero', '')}")
        else:
            st.write("**Contrato:** No se detectó contrato vigente")

        st.caption("Si alguno de estos datos es incorrecto o deseas modificarlo, ve a tu perfil.")
        st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")

        st.write("---")
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_acta_recibo_entrega_cps_real(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
                st.success("¡Formato generado y firmado digitalmente con éxito!")
                st.rerun()


def _render_opcion_8_acta_recibo_entrega(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Balance General CPS")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "acta_recibo_entrega_cps", año=año_cert, mes=mes_cert)

    if cert_actual and cert_actual.get("estado") == "aprobado":
        st.success(
            f"Tu formato de **Balance General CPS** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )

        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del formato: {e}")
            pdf_bytes = None

        if pdf_bytes:
            if st.button("👁️ Ver formato", type="primary", use_container_width=True):
                st.session_state["_preview_cert_user"] = {
                    "cert": cert_actual,
                    "mes_nombre": nombre_mes_cert,
                    "año": año_cert,
                }
                st.rerun()
    elif cert_actual:
        st.info(
            f"Tu formato de **Balance General CPS** para **{nombre_mes_cert} {año_cert}** "
            "fue generado y está en espera de aprobación."
        )
        _mostrar_avance_actas("acta_recibo_entrega_cps", cert_actual)
    else:
        # Validar requisitos específicos de Balance General CPS
        from app.services.usuario_service import UsuarioService
        req_bg = UsuarioService().validar_datos_balance_general_cps(usuario_id)
        if not req_bg["valido"]:
            st.warning(
                "⚠️ **Requisitos para habilitar el Balance General CPS**\n\n"
                "Para poder generar y firmar digitalmente este formato, debes completar "
                "los siguientes datos obligatorios en tu contrato activo en **Mi Perfil**:\n\n" +
                "\n".join([f"- {item}" for item in req_bg["faltantes"]])
            )
            st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")
            return

        st.warning(f"Aún no has generado el formato para el período **{nombre_mes_cert} {año_cert}**.")
        
        # Mostrar resumen de datos del usuario
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}

        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)

        st.write("### Datos para generación de formato")
        st.write(f"**Contratista:** {usuario_data.get('nombre_completo', '')}")
        st.write(f"**Identificación:** {usuario_data.get('tipo_documento', '')} Nº {usuario_data.get('numero_documento', '')}")
        if contrato_vig:
            st.write(f"**Contrato:** {contrato_vig.get('numero', '')}")
        else:
            st.write("**Contrato:** No se detectó contrato vigente")

        st.caption("Si alguno de estos datos es incorrecto o deseas modificarlo, ve a tu perfil.")
        st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")

        st.write("---")
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_acta_recibo_entrega(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
                st.success("¡Formato generado y firmado digitalmente con éxito!")
                st.rerun()



def _render_opcion_10_informe_actividades_final(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado=False):
    usuario_id = sesion["id"]
    nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")
    mostrar_titulo_decorado("Informe de actividades Final CPS")

    if bloqueado:
        _aviso_bloqueado()
        return

    st.subheader(servicio.leyenda_periodo(año_cert, mes_cert))

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id, "informe_actividades_final_cps", año=año_cert, mes=mes_cert)

    if cert_actual:
        st.success(
            f"Tu formato de **Informe de actividades Final CPS** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )

        try:
            docx_bytes = servicio.generar_docx(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el documento Word del formato: {e}")
            docx_bytes = None

        if docx_bytes:
            nombre_archivo = _nombre_archivo_docx(cert_actual, nombre_mes_cert, año_cert)
            st.download_button(
                "⬇️ Descargar Word (.docx)",
                data=docx_bytes,
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True,
            )
    else:
        st.warning(f"Aún no has generado el formato para el período **{nombre_mes_cert} {año_cert}**.")

        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
        contratos = usuario_data.get("contratos") or []
        contrato_vig = servicio._contrato_relevante(contratos, año_cert, mes_cert)

        st.write("### Datos para generación de formato")
        st.write(f"**Contratista:** {usuario_data.get('nombre_completo', '')}")
        st.write(f"**Identificación:** {usuario_data.get('tipo_documento', '')} Nº {usuario_data.get('numero_documento', '')}")
        if contrato_vig:
            st.write(f"**Contrato:** {contrato_vig.get('numero', '')}")
        else:
            st.write("**Contrato:** No se detectó contrato vigente")

        st.caption("Si alguno de estos datos es incorrecto o deseas modificarlo, ve a tu perfil.")
        st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")

        st.write("---")
        if st.button("✍️ Firmar y Generar Formato", type="primary", use_container_width=True, disabled=not bool(contrato_vig.get("numero"))):
            if servicio.firmar_y_generar_informe_actividades_final(usuario_id, nombre_usuario_actual, año=año_cert, mes=mes_cert):
                st.success("¡Formato generado y firmado digitalmente con éxito!")
                st.rerun()


def _render_alerta_faltantes(faltantes: dict) -> None:
    """Alerta superior que enumera los datos pendientes que bloquean la descarga."""
    msg = (
        "⚠️ **No podrás descargar los formatos de contrato.**\n\n"
        "Faltan datos por diligenciar. Complétalos en **Mi perfil** para habilitar "
        "la descarga:\n"
    )
    for sec in faltantes["secciones"]:
        msg += f"\n**{sec['titulo']}** — _{sec['destino']}_\n"
        for f in sec["faltantes"]:
            msg += f"- {f}\n"
    st.warning(msg)
    st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil para completar mis datos →", icon="👤")


def _aviso_bloqueado() -> None:
    """Mensaje mostrado en lugar del contenido de un formato cuando está bloqueado."""
    st.warning(
        "🔒 No puedes descargar este formato hasta completar tus datos. "
        "Revisa la alerta de **datos pendientes** en la parte superior de la página "
        "y complétalos en **Mi perfil**."
    )
    st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")


def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    servicio = CertificacionService()
    usuario_id = sesion["id"]

    periodos_usuario = servicio.periodos_disponibles_usuario(usuario_id)
    año_cert, mes_cert = st.selectbox(
        "📅 Período de trabajo",
        options=periodos_usuario,
        format_func=lambda p: f"{MESES_ES[p[1] - 1]} {p[0]}",
        index=periodos_usuario.index(servicio.periodo_certificable()),
        key="cert_periodo_seleccionado",
    )
    nombre_mes_cert = MESES_ES[mes_cert - 1]

    tab_activa = st.session_state.get("tab_formato_activo")
    if tab_activa == 5:
        mostrar_titulo_decorado("Formato de acta de compromiso")
    elif tab_activa == 8:
        mostrar_titulo_decorado("Balance General CPS")
    elif tab_activa == 9:
        mostrar_titulo_decorado("Acta de recibo y entrega CPS")
    else:
        mostrar_titulo_decorado("Formatos de contrato")

    dia_inicio = servicio._dia_inicio_periodo()

    # CSS global para pintar de verde el botón de instructivos en el segundo contenedor
    st.markdown(
        """
        <style>
        /* Selecciona el botón dentro del segundo contenedor del panel izquierdo */
        div[data-testid="stColumn"]:first-child div[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(2) div.stButton > button {
            background-color: #28a745 !important;
            background: #28a745 !important;
            color: white !important;
            border: 1px solid #28a745 !important;
        }
        div[data-testid="stColumn"]:first-child div[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(2) div.stButton > button:hover {
            background-color: #218838 !important;
            background: #218838 !important;
            border-color: #1e7e34 !important;
        }
        div[data-testid="stColumn"]:first-child div[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(2) div.stButton > button * {
            color: white !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    faltantes = UsuarioService().faltantes_para_formatos(usuario_id)
    bloqueado = not faltantes["puede_descargar"]
    if bloqueado:
        _render_alerta_faltantes(faltantes)

    col_menu, col_contenido = st.columns([1, 2], gap="large")

    with col_menu:
        with st.container(border=True):
            st.markdown("### Formatos - Cuenta de cobro SRTI")
            if st.button("1- Cuenta de cobro.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 1
                st.rerun()
            if st.button("2- Form. retención en la fuente Primera cuenta.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 2
                st.rerun()
            if st.button("3- Form. retención en la fuente Segunda cuenta ++", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 3
                st.rerun()
            if st.button("4- Form. condicion de declarante y dep. Economica.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 4
                st.rerun()
            if st.button("5- Form. Gestión Corr – GD – SECOP II.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 6
                st.rerun()
            if st.button("6- Otros certificados - Herramientas", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 7
                st.rerun()
            if st.button("7- Historial de formatos.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 10
                st.rerun()
            if st.button("8- Verificar formato.", type="primary", disabled=True, use_container_width=True):
                st.session_state["tab_formato_activo"] = 11
                st.rerun()

        with st.container(border=True):
            st.markdown("### Últimos formatos de contrato")
            if st.button("1- Form. Acta compromiso.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 5
                st.rerun()
            if st.button("2- Balance General CPS.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 8
                st.rerun()
            if st.button("3- Formato de acta de recibo y entrega CPS.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 9
                st.rerun()
            if st.button("4- Informe de actividades Final CPS.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 12
                st.rerun()
        
        # Segundo contenedor para el botón de instructivos (viñeta separada)
        with st.container(border=True):
            st.markdown("""
            <style>
                div.element-container:has(style#btn-instructivo-verde) {
                    display: none !important;
                    height: 0px !important;
                    margin: 0px !important;
                    padding: 0px !important;
                }
                div.element-container:has(style#btn-instructivo-verde) + div.element-container button {
                    background-color: #28a745 !important;
                    background: #28a745 !important;
                    border-color: #28a745 !important;
                }
                div.element-container:has(style#btn-instructivo-verde) + div.element-container button:hover {
                    background-color: #218838 !important;
                    background: #218838 !important;
                    border-color: #1e7e34 !important;
                }
                div.element-container:has(style#btn-instructivo-verde) + div.element-container button p {
                    color: white !important;
                }
            </style>
            <style id="btn-instructivo-verde"></style>
            """, unsafe_allow_html=True)
            if st.button("📚 Instructivo de cargue de cuenta", type="primary", use_container_width=True):
                st.switch_page("pages/3_instructivos.py")
        
        # Anuncio/Tarjeta informativa debajo del segundo contenedor
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #FF8C00, #FF9800); color: white; padding: 12px 15px; border-radius: 8px; margin-top: 15px;">
                <h4 style="margin: 0; font-size: 13.5px; display: flex; align-items: center; gap: 8px; color: white !important; font-weight: 600;">
                    💡 Los formatos de correspondencia se generan desde el día {dia_inicio} de cada mes.
                </h4>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_contenido:
        tab_activa = st.session_state.get("tab_formato_activo")
        if tab_activa == 1:
            _render_opcion_1_cuenta_cobro(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 2:
            _render_opcion_2_retencion_primera(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 3:
            _render_opcion_3_retencion_segunda(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 4:
            _render_opcion_4_declarante_dependencia(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 5:
            _render_opcion_5_acta_compromiso(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 6:
            _render_opcion_6_gestion_corr(servicio, usuario_id, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 7:
            _render_opcion_7_herramientas()
        elif tab_activa == 8:
            _render_opcion_8_acta_recibo_entrega(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 9:
            _render_opcion_9_acta_recibo_entrega_real(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        elif tab_activa == 10:
            _render_opcion_8_historial(servicio, usuario_id, año_cert, mes_cert, bloqueado)
        elif tab_activa == 11:
            _render_verificador_codigo(servicio)
        elif tab_activa == 12:
            _render_opcion_10_informe_actividades_final(servicio, sesion, año_cert, mes_cert, nombre_mes_cert, bloqueado)
        else:
            st.info("👈 Selecciona un formato en el menú de la izquierda para visualizar su contenido.")

    if st.session_state.get("_preview_cert_user"):
        _dialog_preview_cert(servicio)


# Punto de entrada cuando Streamlit carga la página directamente
render(obtener_sesion())
