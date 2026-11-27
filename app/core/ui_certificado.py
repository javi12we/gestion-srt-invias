"""Componentes de UI reutilizables para la previsualización de certificados PDF."""

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer


@st.cache_data(show_spinner=False)
def obtener_pdf_certificado_cacheado(_servicio, cert_id: str, hash_verificacion: str, _certificacion: dict, version_key: str = "") -> bytes:
    """PDF de un certificado ya aprobado no cambia una vez emitido (el hash se
    preserva). Se cachea por id + hash para no regenerarlo con ReportLab
    (más su consulta a usuario) en cada rerun de Streamlit.
    El parámetro version_key (sin guión bajo) sirve para invalidar la caché cuando cambian las firmas."""
    # Invalida caché por cambio en formato de firma de supervisor (v3)
    return _servicio.generar_pdf(_certificacion)


@st.cache_data(show_spinner=False)
def obtener_excel_certificado_cacheado(_servicio, cert_id: str, hash_verificacion: str, _certificacion: dict, version_key: str = "") -> bytes:
    """Versión .xlsx editable de una Acta (borrador o ya aprobada). Se cachea igual
    que el PDF (por id + hash + version_key) para no regenerar el libro de xlsxwriter
    en cada rerun."""
    return _servicio.generar_excel(_certificacion)


def _version_key(servicio, cert: dict) -> str:
    """Clave de invalidación de la caché: firmas + huella de los contratos del
    usuario, para que cambiar los pagos regenere el documento."""
    return f"{cert.get('firmas', {})}|{servicio.huella_contratos_usuario(cert)}"


def _cerrar_dialogo_documento() -> None:
    st.session_state.pop("_ver_doc", None)


@st.dialog("Vista previa y descarga", width="large", on_dismiss=_cerrar_dialogo_documento)
def _dialog_ver_documento(servicio) -> None:
    """Genera el PDF o Excel solicitado únicamente al abrirse (nunca antes), y lo
    ofrece para descargar. Para PDF incluye vista previa; para Excel no hay visor
    disponible en Streamlit, así que se muestra un aviso y el botón de descarga."""
    info = st.session_state.get("_ver_doc")
    if not info:
        return

    cert = info["cert"]
    nombre = info["nombre"]
    formato = info["formato"]  # "pdf" | "xlsx"
    prefijo = info["prefijo"]
    periodo = info["periodo"]
    es_borrador = info.get("es_borrador", False)
    prefijo_archivo = f"BORRADOR_{prefijo}" if es_borrador else prefijo
    nombre_archivo_base = f"{prefijo_archivo}_{nombre.replace(' ', '_')}_{periodo.replace(' ', '_')}"

    if formato == "xlsx":
        with st.spinner("Generando el Excel…"):
            try:
                xlsx_bytes = obtener_excel_certificado_cacheado(
                    servicio, str(cert.get("_id", "")), cert.get("hash_verificacion", ""), cert,
                    version_key=_version_key(servicio, cert),
                )
            except Exception as e:
                st.error(f"No fue posible generar el Excel: {e}")
                return
        st.write(f"Excel para **{nombre}** ({periodo})")
        st.caption("Reproduce la misma estructura del PDF en una hoja de cálculo editable. No hay vista previa en línea: descárgalo para revisarlo.")
        st.download_button(
            "⬇️ Descargar Excel",
            data=xlsx_bytes,
            file_name=f"{nombre_archivo_base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
            key="_dl_doc_xlsx",
        )
        return

    with st.spinner("Generando el PDF…"):
        try:
            pdf_bytes = obtener_pdf_certificado_cacheado(
                servicio, str(cert.get("_id", "")), cert.get("hash_verificacion", ""), cert,
                version_key=_version_key(servicio, cert),
            )
        except Exception as e:
            st.error(f"No fue posible generar el PDF: {e}")
            return

    st.write(f"Vista previa para **{nombre}** ({periodo})")
    pdf_viewer(input=pdf_bytes, width=700, height=600)
    st.download_button(
        "⬇️ Descargar PDF",
        data=pdf_bytes,
        file_name=f"{nombre_archivo_base}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
        key="_dl_doc_pdf",
    )


def abrir_dialogo_documento(cert: dict, nombre: str, formato: str, prefijo: str, periodo: str, es_borrador: bool = False) -> None:
    """Dispara la apertura del diálogo de vista previa/descarga (PDF o Excel) para
    `cert`. La generación ocurre dentro del diálogo, solo cuando este se abre."""
    st.session_state["_ver_doc"] = {
        "cert": cert, "nombre": nombre, "formato": formato,
        "prefijo": prefijo, "periodo": periodo, "es_borrador": es_borrador,
    }
    st.rerun()


def render_dialogo_documento_si_activo(servicio) -> None:
    if st.session_state.get("_ver_doc"):
        _dialog_ver_documento(servicio)


def render_preview_cert(
    pdf_bytes: bytes,
    caption: str,
    file_name: str,
    dl_key: str,
    show_download: bool = True,
) -> None:
    """Renderiza el visor PDF + botón de descarga dentro de un diálogo de certificado."""
    st.caption(caption)
    pdf_viewer(input=pdf_bytes, width=800, height=620)
    if show_download:
        st.download_button(
            "⬇️ Descargar PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
            key=dl_key,
        )
