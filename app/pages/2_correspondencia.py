import streamlit as st
import pandas as pd
import json
from datetime import datetime, timezone, timedelta
import holidays
import streamlit.components.v1 as components

from app.core.sesion import obtener_sesion
from app.services.correspondencia_service import CorrespondenciaService
from app.services.opciones_service import OpcionesService
from app.services.usuario_service import UsuarioService

# --- LÓGICA DE REINICIO DE FORMULARIO ---
if "form_key_idx" not in st.session_state:
    st.session_state["form_key_idx"] = 0

form_key = st.session_state["form_key_idx"]

# --- MOSTRAR MENSAJES PERSISTENTES ---
mensaje_placeholder = st.empty()
if "mensaje_exito" in st.session_state:
    mensaje_placeholder.success(st.session_state.pop("mensaje_exito"))
if "mensaje_error" in st.session_state:
    mensaje_placeholder.error(st.session_state.pop("mensaje_error"))



st.title("Correspondencia")
sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()

roles = sesion.get("roles", [])
id_usuario_actual = sesion.get("id")
nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")

# Definir permisos basados en los roles descritos por el usuario
is_admin = "admin" in roles
is_asignacion = "asignacion" in roles or is_admin
is_coordinador = "coordinador" in roles
is_lider = "lider" in roles
is_gestor = "gestor" in roles

can_assign = is_asignacion or is_coordinador or is_lider or is_gestor

# Si no tiene ningún rol relacionado, no mostramos nada
if not (is_asignacion or is_coordinador or is_lider or is_gestor):
    st.info("No tienes permisos para acceder a este módulo.")
    st.stop()

service = CorrespondenciaService()
opciones_service = OpcionesService()
usuario_service = UsuarioService()

# Inicializar estados de formulario si no existen
if f"form_tipo_{form_key}" not in st.session_state:
    st.session_state[f"form_tipo_{form_key}"] = ""
if f"form_manual_tipo_{form_key}" not in st.session_state:
    st.session_state[f"form_manual_tipo_{form_key}"] = False

import re

def determinar_tipo_por_radicado(radicado):
    """Lógica para determinar el tipo basado en el radicado usando Regex."""
    if not radicado:
        return ""
    
    # Búsqueda de VUVRAZ o VURAZ (OFICIO)
    if re.search(r"-VUV?RAZ-", radicado, re.I):
        return "oficios"
    
    # Búsqueda de VUVR (PQRD)
    if re.search(r"-VUVR-", radicado, re.I):
        return "pqrds"
    
    # Cualquier otro caso o código diferente
    return "memorandos"

def on_radicado_change():
    """Callback cuando cambia el número de radicado."""
    fk = st.session_state.get("form_key_idx", 0)
    if not st.session_state.get(f"form_manual_tipo_{fk}", False):
        nuevo_tipo = determinar_tipo_por_radicado(st.session_state.get(f"form_numero_radicado_{fk}", ""))
        st.session_state[f"form_tipo_{fk}"] = nuevo_tipo

# Definir categorías fijas según requerimiento del usuario (ignorando catálogo incompleto en DB)
tipos_dict = {
    "": "Seleccione tipo...",
    "memorandos": "MEMORANDO",
    "oficios": "OFICIO",
    "pqrds": "PQRD"
}

# Cargar el resto de opciones desde la DB
grupos_dict = {op["clave"]: op["etiqueta"] for op in opciones_service.obtener_opciones("grupo")}
clases_dict = {op["clave"]: op["etiqueta"] for op in opciones_service.obtener_opciones("clase_correspondencia")}
if not grupos_dict: grupos_dict = {"permisos": "Permisos", "solicitudes": "Solicitudes", "otros": "Otros"}
if not clases_dict: clases_dict = {"informes": "Informes", "peticiones": "Peticiones", "quejas": "Quejas"}

# Definir quiénes pueden ver toda la correspondencia por defecto
puede_ver_todo = is_admin or is_asignacion or is_coordinador or is_lider


def cargar_datos(skip=0, limit=10, filtros=None):
    # Si puede ver todo y NO ha marcado el checkbox de "ver solo lo mío"
    solo_mio = st.session_state.get("filtro_ver_solo_mio", False)
    
    if puede_ver_todo and not solo_mio:
        return service.listar_correspondencia(ver_todas=True, skip=skip, limit=limit, filtros=filtros)
    else:
        # En cualquier otro caso, o si forzó "ver solo lo mío", filtramos por su ID
        return service.listar_correspondencia(id_usuario=id_usuario_actual, ver_todas=False, skip=skip, limit=limit, filtros=filtros)


def formatear_fecha(fecha):
    if not fecha:
        return ""
    if isinstance(fecha, datetime):
        return fecha.strftime("%Y-%m-%d %H:%M")
    return str(fecha)

@st.dialog("Gestión de Radicado", width="large")
def modal_gestion_correspondencia(corr_actual):
    id_seleccionado = str(corr_actual["_id"])
    numero_radicado = corr_actual.get("numero_radicado", "S/N")
    estado_actual = corr_actual.get('estado_actual', 'pendiente')
    
    # 1. Cabecera principal
    radicado_js = json.dumps(str(numero_radicado))
    components.html(
        f"""
        <div style="display:inline-flex;align-items:center;gap:8px;margin:0 0 6px 0;">
          <span style="font-size:30px;line-height:1;">📄</span>
          <span style="font-size:38px;font-weight:700;line-height:1;">Radicado:</span>
          <code style="font-size:36px;padding:2px 8px;border-radius:8px;background:#ECFDF3;color:#15803D;">{numero_radicado}</code>
          <button
            id="copy-radicado-btn"
            onclick='navigator.clipboard.writeText({radicado_js}).then(() => {{ this.innerText = "✅"; setTimeout(() => this.innerText = "📋", 1200); }})'
            style="border:1px solid #d1d5db;border-radius:8px;width:30px;height:30px;background:#fff;cursor:pointer;font-size:15px;line-height:1;"
            title="Copiar número de radicado"
            aria-label="Copiar número de radicado"
          >📋</button>
        </div>
        """,
        height=48,
    )
    
    # 2. Calcular días de vencimiento
    fecha_venc_dt = corr_actual.get('fecha_vencimiento')
    alerta_vencimiento = ""
    if fecha_venc_dt:
        if isinstance(fecha_venc_dt, datetime):
            if fecha_venc_dt.tzinfo is None:
                fecha_venc_dt = fecha_venc_dt.replace(tzinfo=timezone.utc)
            fecha_venc_utc = fecha_venc_dt.astimezone(timezone.utc)
            colombia_tz = timezone(timedelta(hours=-5))
            hoy = datetime.now(colombia_tz)
            dias_restantes = (fecha_venc_utc.date() - hoy.date()).days
            
            # Si ya finalizó, no mostramos alerta de vencimiento alarmante
            es_finalizado = estado_actual in ["respondido", "archivado", "traslado_competencia"]
            if es_finalizado:
                alerta_vencimiento = "✅ **Trámite Finalizado**"
            elif dias_restantes < 0:
                alerta_vencimiento = f"🛑 **Vencido por {abs(dias_restantes)} días**"
            elif dias_restantes == 0:
                alerta_vencimiento = "⚠️ **Vence hoy**"
            elif dias_restantes <= 3:
                alerta_vencimiento = f"⚠️ **Vence en {dias_restantes} días**"
            else:
                alerta_vencimiento = f"⏳ **A tiempo ({dias_restantes} días)**"
                
    # 3. Datos clave en métricas/columnas
    c1, c2, c3 = st.columns(3)
    c1.metric("Estado", estado_actual.replace("_", " ").title())
    responsable = corr_actual.get("responsable_actual", {}).get("nombre", "Sin asignar")
    c2.metric("Responsable", responsable)
    if alerta_vencimiento:
        c3.markdown(f"<div style='padding-top: 10px; font-size: 1.1em;'>{alerta_vencimiento}</div>", unsafe_allow_html=True)
    
    st.divider()

    # 4. Información en columnas
    col_info1, col_info2 = st.columns([2, 1])
    with col_info1:
        st.markdown(f"**Peticionario:** {corr_actual.get('peticionario')}")
        st.markdown(f"**Asunto:** {corr_actual.get('asunto')}")
        if "respuesta" in corr_actual:
            st.success(f"**Nº Oficio Respuesta:** {corr_actual['respuesta'].get('numero_oficio')}")
    with col_info2:
        st.markdown(f"**Radicación:** {formatear_fecha(corr_actual.get('fecha_radicacion'))}")
        st.markdown(f"**Vencimiento:** {formatear_fecha(corr_actual.get('fecha_vencimiento'))}")

    # 5. Etiquetas de categorización
    t_lbl = tipos_dict.get(corr_actual.get('tipo'), corr_actual.get('tipo'))
    g_lbl = grupos_dict.get(corr_actual.get('grupo'), corr_actual.get('grupo'))
    c_lbl = clases_dict.get(corr_actual.get('clase'), corr_actual.get('clase'))
    
    st.markdown(f"""
    <div style="display: flex; gap: 10px; margin-top: 15px; margin-bottom: 25px; flex-wrap: wrap;">
        <span style="background-color: #1E3A8A; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.85em;">📑 Tipo: <b>{t_lbl}</b></span>
        <span style="background-color: #065F46; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.85em;">📁 Grupo: <b>{g_lbl}</b></span>
        <span style="background-color: #701A75; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.85em;">🏷️ Clase: <b>{c_lbl}</b></span>
    </div>
    """, unsafe_allow_html=True)

    es_finalizado = estado_actual in ["respondido", "archivado", "traslado_competencia"]

    if es_finalizado:
        st.warning("🔒 Este radicado ha finalizado su trámite y no puede ser modificado (Estado: " + estado_actual.upper() + ").")
    else:
        # --- ACCIONES ---
        st.write("### Acciones")
        col_acc1, col_acc2, col_acc3 = st.columns(3)
        
        # Acción 1: Editar (Solo Asignación)
        if is_asignacion:
            with col_acc1:
                with st.popover("✏️ Editar Detalles", use_container_width=True):
                    st.write("Editar Radicado")
                    with st.form(f"form_editar_{id_seleccionado}"):
                        ed_asunto = st.text_area("Asunto", value=corr_actual.get("asunto", ""))
                        ed_peticionario = st.text_input("Peticionario", value=corr_actual.get("peticionario", ""))
                        ed_observaciones = st.text_area("Observaciones", value=corr_actual.get("observaciones_generales", ""))
                        if st.form_submit_button("Guardar Cambios", type="primary"):
                            try:
                                service.editar_correspondencia(
                                    id_seleccionado, 
                                    {"asunto": ed_asunto, "peticionario": ed_peticionario, "observaciones_generales": ed_observaciones}, 
                                    nombre_usuario_actual,
                                    usuario_ejecutor_id=id_usuario_actual
                                )
                                st.success("Actualizado")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # Determinar si el usuario es el responsable actual del radicado
        es_responsable = str(corr_actual.get("responsable_actual", {}).get("usuario_id")) == str(id_usuario_actual)

        # Acción 2: Asignar (Traslado a otro usuario)
        # Los administradores y personal de asignación pueden asignar todo.
        # Los líderes y coordinadores SOLO pueden reasignar lo que ellos tienen asignado.
        # Los gestores SOLO pueden reasignar a usuarios con rol admin.
        puedo_reasignar = is_asignacion or (can_assign and es_responsable and not is_gestor)

        if puedo_reasignar:
            with col_acc2 if is_asignacion else col_acc1:
                with st.popover("👥 Asignar / Reasignar", use_container_width=True):

                    st.write("Asignar a un usuario")
                    usuarios = usuario_service.listar_usuarios()
                    usuarios_opts = {str(u["_id"]): f"{u.get('nombre_completo', u['usuario'])}" for u in usuarios if u.get("activo", True)}
                    
                    with st.form(f"form_asignar_{id_seleccionado}"):
                        nuevo_resp_id = st.selectbox("Seleccionar Responsable", options=list(usuarios_opts.keys()), format_func=lambda x: usuarios_opts[x])
                        comentario_asig = st.text_input("Comentario", value="Reasignación")
                        if st.form_submit_button("Asignar", type="primary"):
                            try:
                                service.asignar_correspondencia(
                                    id_seleccionado,
                                    nuevo_resp_id,
                                    usuarios_opts[nuevo_resp_id],
                                    nombre_usuario_actual,
                                    comentario_asig,
                                    usuario_ejecutor_id=id_usuario_actual
                                )
                                st.success("Asignado exitosamente")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # Acción 2b: Reasignar restringida para GESTOR (solo a admins, comentario obligatorio)
        if is_gestor and not is_asignacion:
            with col_acc2:
                tooltip_gestor = "Solo reasignar en caso de que el radicado no te pertenezca, será revisado"
                with st.popover("👥 Asignar / Reasignar", use_container_width=True):
                    st.markdown(
                        '<p style="color:#FFFFFF; font-weight:bold; font-size:1.05em; margin-bottom:4px;">⚠️ Reasignación restringida</p>',
                        unsafe_allow_html=True
                    )
                    st.caption(tooltip_gestor)
                    
                    # Filtrar solo usuarios activos con rol admin
                    todos_usuarios = usuario_service.listar_usuarios()
                    admins_opts = {
                        str(u["_id"]): f"{u.get('nombre_completo', u['usuario'])}"
                        for u in todos_usuarios
                        if u.get("activo", True) and "admin" in u.get("roles", [])
                    }
                    
                    if not admins_opts:
                        st.warning("No hay administradores disponibles para reasignar.")
                    else:
                        with st.form(f"form_asignar_gestor_{id_seleccionado}"):
                            nuevo_resp_id_g = st.selectbox(
                                "Seleccionar Administrador",
                                options=list(admins_opts.keys()),
                                format_func=lambda x: admins_opts[x]
                            )
                            comentario_gestor = st.text_input(
                                "Motivo de reasignación * (Obligatorio)",
                                value="",
                                placeholder="Explica el motivo de la reasignación..."
                            )
                            submitted_g = st.form_submit_button("Devolver", type="primary")
                            if submitted_g:
                                if not comentario_gestor.strip():
                                    st.error("❌ El campo de motivo es obligatorio para reasignar.")
                                else:
                                    try:
                                        service.asignar_correspondencia(
                                            id_seleccionado,
                                            nuevo_resp_id_g,
                                            admins_opts[nuevo_resp_id_g],
                                            nombre_usuario_actual,
                                            f"[Gestor] {comentario_gestor}",
                                            usuario_ejecutor_id=id_usuario_actual
                                        )
                                        st.success("Reasignado exitosamente al administrador.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error: {e}")

        # Acción 3: Dar Respuesta / Archivar / Traslado por Competencia
        if es_responsable or is_asignacion:

            with col_acc3 if is_asignacion else (col_acc2 if can_assign else col_acc1):
                with st.popover("✅ Responder / Tramitar", use_container_width=True):
                    if estado_actual not in ["respondido", "archivado", "traslado_competencia"]:
                        st.write("Cargar Respuesta")
                        # Se quita st.form para validar en tiempo real el campo y habilitar/deshabilitar el botón
                        col_resp1, col_resp2 = st.columns(2)
                        with col_resp1:
                            num_oficio = st.text_input("Numero de radicado Salida *", key=f"num_oficio_{id_seleccionado}")
                        with col_resp2:
                            fecha_resp = st.date_input("Fecha de Respuesta", value=datetime.now(timezone.utc), key=f"fecha_resp_{id_seleccionado}")
                            
                        comentario_resp = st.text_input("Comentario", value="Se da respuesta", key=f"comentario_resp_{id_seleccionado}")
                        
                        # Validación del formato
                        patron_oficio = r"^\d{4}[A-Za-z]?-(VANT|VATL|VBOG|VBOL|VBOY|VCAL|VCAQ|VCAS|VCAU|VCES|VCHO|VCOR|VCUN|VGUA|VHUI|VMAG|VMET|VNAR|VNSA|VOCA|VPUT|VQUI|VRIS|VSAN|VSUC|VTOL|VUVR|VUVRAZ|VVAL)-[A-Za-z0-9]+$"
                        es_valido = False
                        
                        if num_oficio:
                            if re.match(patron_oficio, num_oficio, re.IGNORECASE):
                                es_valido = True
                            else:
                                st.warning("Formato invalido, no es una respuesta")
                        
                        if st.button("Responder", type="primary", disabled=not es_valido, key=f"btn_marcar_resp_{id_seleccionado}"):
                            # Convertir fecha de date a datetime
                            f_resp_dt = datetime.combine(fecha_resp, datetime.min.time()).replace(tzinfo=timezone.utc)
                            service.dar_respuesta(
                                id_seleccionado,
                                num_oficio,
                                nombre_usuario_actual,
                                comentario_resp,
                                fecha_respuesta=f_resp_dt,
                                usuario_ejecutor_id=id_usuario_actual
                            )
                            st.success("Respuesta registrada")
                            st.rerun()

                    
                    if estado_actual not in ["archivado", "traslado_competencia"]:
                        st.markdown('Archivar Radicado <span title="Solo archivar radicados que no necesiten respuesta y se encuentren debidamente en una Carpeta de Archivados o Archivo en AZ, de lo contrario contará como abierto y generará reporte de retraso (Se realiza revisión semanal de archivados)">ℹ️</span>', unsafe_allow_html=True)
                        comentario_arch = st.text_input("Comentario *", value="", key=f"comentario_arch_{id_seleccionado}")
                        if st.button("Archivar", type="primary", disabled=not bool(comentario_arch.strip()), key=f"btn_archivar_{id_seleccionado}"):
                            service.archivar(
                                id_seleccionado,
                                nombre_usuario_actual,
                                comentario_arch,
                                usuario_ejecutor_id=id_usuario_actual
                            )
                            st.success("Archivado")
                            st.rerun()
                                
                    if estado_actual not in ["archivado", "traslado_competencia"] and (is_admin or is_asignacion or is_coordinador or is_lider):
                        st.write("Traslado por Competencia")
                        with st.form(f"form_traslado_comp_{id_seleccionado}"):
                            comentario_tc = st.text_input("Comentario", value="No es competencia de la entidad")
                            if st.form_submit_button("Trasladar", type="primary"):
                                service.cambiar_estado(
                                    id_seleccionado,
                                    "traslado_competencia",
                                    nombre_usuario_actual,
                                    comentario_tc,
                                    usuario_ejecutor_id=id_usuario_actual
                                )
                                st.success("Traslado por competencia registrado")
                                st.rerun()
                            
    # --- TRAZABILIDAD ---
    st.write("---")
    st.subheader("📜 Historial de Trazabilidad")
    trazabilidad = corr_actual.get("trazabilidad", [])
    
    for evento in reversed(trazabilidad):
        tipo = evento.get('tipo_evento', '').lower()
        fecha = formatear_fecha(evento.get('fecha'))
        ejecutor = evento.get('usuario_ejecutor', 'Sistema')
        
        # Configuración visual según tipo de evento
        icon = "⚪"
        titulo = tipo.replace("_", " ").title()
        color = "grey"
        
        if tipo == "radicacion":
            icon = "📝"
            titulo = "Radicación del Documento"
        elif tipo == "asignacion":
            icon = "👤"
            titulo = "Asignación Inicial"
        elif tipo == "reasignacion":
            icon = "🔄"
            titulo = "Reasignación de Responsable"
        elif tipo == "carga_respuesta":
            icon = "📩"
            titulo = "Respuesta Registrada"
        elif tipo == "cierre":
            icon = "🔒"
            titulo = "Trámite Finalizado"
        elif tipo == "cambio_estado":
            icon = "⚡"
            titulo = "Actualización de Estado"

        with st.container(border=True):
            # Usamos columnas para una mejor alineación
            c_icon, c_info = st.columns([0.1, 0.9])
            with c_icon:
                st.markdown(f"### {icon}")
            with c_info:
                st.markdown(f"**{titulo}** — {fecha}")
                st.markdown(f"Ejecutado por: **{ejecutor}**")
                
                # Lógica detallada para traslados
                if tipo in ["asignacion", "reasignacion"]:
                    resp_n = evento.get("responsable_nuevo", "N/A")
                    resp_a = evento.get("responsable_anterior")
                    if resp_a:
                        st.write(f"De: `{resp_a}` ➡️ Asignado a: **{resp_n}**")
                    else:
                        st.write(f"Asignado a: **{resp_n}**")
                
                # Mostrar cambios de estado
                est_ant = evento.get("estado_anterior")
                est_nue = evento.get("estado_nuevo")
                if est_ant and est_nue and est_ant != est_nue:
                    st.caption(f"Estado cambió de `{est_ant}` a `{est_nue}`")
                
                if evento.get('comentario'):
                    st.info(f"💬 {evento.get('comentario')}")



# Construir pestañas
tabs_names = ["📂 Búsqueda y Gestión"]
if is_asignacion:
    tabs_names.append("📝 Nueva Correspondencia")

tabs = st.tabs(tabs_names)

# Renderizar pestaña "Nueva Correspondencia" si tiene acceso
if is_asignacion:
    with tabs[1]:
        # Inicializar cronómetro de diligenciamiento si no existe
        if "inicio_creacion_radicado" not in st.session_state:
            st.session_state["inicio_creacion_radicado"] = datetime.now(timezone.utc)
            
        st.subheader("Registrar Nuevo Radicado")

        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                PATRON_RADICADO = (
                    r"^\d{4}[A-Za-z]-"
                    r"(VANT|VATL|VBOG|VBOL|VBOY|VCAL|VCAQ|VCAS|VCAU|VCES|VCHO|VCOR|VCUN|"
                    r"VGUA|VHUI|VMAG|VMET|VNAR|VNSA|VOCA|VPUT|VQUI|VRIS|VSAN|VSUC|VTOL|"
                    r"VUVRAZ|VUVR|VVAL)"
                    r"-[A-Za-z0-9]+$"
                )

                raw_radicado = st.text_input(
                    "Número de Radicado *",
                    key=f"form_numero_radicado_{form_key}",
                    on_change=on_radicado_change,
                    placeholder="Ej: 2026E-VUVRAZ-051829"
                )

                numero_radicado = raw_radicado.replace(" ", "").upper()

                if " " in raw_radicado:
                    st.warning("⚠️ Se eliminarán los espacios automáticamente.")

                radicado_cumple_formato = (
                    bool(re.match(PATRON_RADICADO, numero_radicado, re.IGNORECASE))
                    if numero_radicado else True
                )

                if numero_radicado and service.existe_radicado(numero_radicado):
                    st.warning("⚠️ Este número de radicado ya está registrado en el sistema.")

                contingencia_radicado = st.checkbox(
                    "⚠️ Contingencia: omitir validación de formato",
                    key=f"form_contingencia_radicado_{form_key}",
                    help="Activar solo si el radicado no sigue el formato estándar (AAAA[L]-CÓDIGO-número). Quedará registrado en el sistema como radicado irregular."
                )

                radicado_valido = radicado_cumple_formato or contingencia_radicado

                if numero_radicado and not radicado_cumple_formato:
                    if contingencia_radicado:
                        st.warning("⚠️ Formato no estándar. Se guardará con marca de **contingencia** en el sistema.")
                    else:
                        st.error("❌ Formato inválido. Debe ser: `AAAA[L]-CÓDIGO-número` — Ej: `2026E-VUVRAZ-051829`")

                peticionario = st.text_input("Peticionario *", key=f"form_peticionario_{form_key}")
                fecha_radicacion = st.date_input("Fecha de Radicación *", key=f"form_fecha_radicacion_{form_key}")
            with col2:
                asunto = st.text_area("Asunto *", height=115, key=f"form_asunto_{form_key}")
            
            col3, col4, col5 = st.columns(3)
            with col3:
                tipo = st.selectbox(
                    "Tipo", 
                    options=list(tipos_dict.keys()), 
                    format_func=lambda x: tipos_dict.get(x, x),
                    key=f"form_tipo_{form_key}",
                    disabled=not st.session_state.get(f"form_manual_tipo_{form_key}", False)
                )
                manual = st.checkbox("Manual en caso de Contingencia", key=f"form_manual_tipo_{form_key}")
            with col4:
                grupo = st.selectbox("Grupo", options=list(grupos_dict.keys()), format_func=lambda x: grupos_dict.get(x, x), key=f"form_grupo_{form_key}")
            with col5:
                clase = st.selectbox("Clase", options=list(clases_dict.keys()), format_func=lambda x: clases_dict.get(x, x), key=f"form_clase_{form_key}")
                
            observaciones = st.text_area("Observaciones Generales (Opcional)", key=f"form_observaciones_{form_key}")
            
            usuarios = usuario_service.listar_usuarios()
            usuarios_opts = {str(u["_id"]): f"{u.get('nombre_completo', u['usuario'])}" for u in usuarios if u.get("activo", True)}
            
            is_traslado = st.checkbox("Es Traslado por Competencia (Cierra el radicado sin asignar)", key=f"form_is_traslado_{form_key}")
            asignado_a = None
            if not is_traslado:
                asignado_a = st.selectbox("Asignar a *", options=list(usuarios_opts.keys()), format_func=lambda x: usuarios_opts[x], key=f"form_asignado_a_{form_key}")
            
            submit_btn = st.button("Crear Correspondencia", type="primary", use_container_width=True)
            
            if submit_btn:
                if not numero_radicado or not asunto or not peticionario or not tipo:
                    st.error("Los campos marcados con * son obligatorios. Asegúrese de que el tipo de correspondencia esté definido.")
                elif not radicado_valido:
                    st.error("❌ El número de radicado no cumple el formato estándar. Activa la Contingencia si es un caso excepcional.")
                else:
                    def limpiar_formulario():
                        st.session_state["form_key_idx"] = st.session_state.get("form_key_idx", 0) + 1
                        st.session_state.pop("inicio_creacion_radicado", None)

                    tiempo_final = datetime.now(timezone.utc)
                    inicio = st.session_state.get("inicio_creacion_radicado", tiempo_final)
                    duracion_seg = (tiempo_final - inicio).total_seconds()

                    metadatos = {"tiempo_creacion_seg": round(duracion_seg, 2)}
                    if contingencia_radicado and not radicado_cumple_formato:
                        metadatos["radicado_contingencia"] = True
                        metadatos["radicado_contingencia_usuario"] = nombre_usuario_actual

                    datos = {
                        "numero_radicado": numero_radicado,
                        "asunto": asunto,
                        "peticionario": peticionario,
                        "fecha_radicacion": datetime.combine(fecha_radicacion, datetime.min.time()).replace(tzinfo=timezone.utc),
                        "tipo": tipo,
                        "grupo": grupo,
                        "clase": clase,
                        "observaciones_generales": observaciones,
                        "metadatos": metadatos
                    }
                    try:
                        id_nuevo = service.crear_correspondencia(datos, nombre_usuario_actual, id_usuario_actual)
                        if is_traslado:
                            service.cambiar_estado(
                                id_nuevo,
                                "traslado_competencia",
                                nombre_usuario_actual,
                                "Traslado por competencia inicial",
                                usuario_ejecutor_id=id_usuario_actual
                            )
                            st.session_state["mensaje_exito"] = f"Correspondencia {numero_radicado} creada y trasladada por competencia."
                            limpiar_formulario()
                            st.rerun() 

                        else:
                            service.asignar_correspondencia(
                                id_nuevo,
                                asignado_a,
                                usuarios_opts[asignado_a],
                                nombre_usuario_actual,
                                "Asignación inicial en radicación",
                                usuario_ejecutor_id=id_usuario_actual
                            )
                            st.session_state["mensaje_exito"] = f"Correspondencia {numero_radicado} creada y asignada exitosamente."
                        
                        limpiar_formulario()
                        st.rerun()

                    except Exception as e:
                        st.session_state["mensaje_error"] = f"Error al crear: {str(e)}"
                        st.rerun()

# Pestaña Búsqueda y Gestión
tab_gestion = tabs[0]

with tab_gestion:
    col_header1, col_header2 = st.columns([3, 1])
    with col_header1:
        st.subheader("Listado de Correspondencia")
    with col_header2:
        if st.button("🔄 Actualizar Datos", use_container_width=True, help="Recarga la lista de correspondencia"):
            st.rerun()

    
    # --- Filtros ---
    def on_filter_change():
        st.session_state["page_correspondencia"] = 1

    # Fila 1: Búsqueda y Responsable
    if puede_ver_todo:
        col_busq, col_resp_f = st.columns([2, 1])
    else:
        col_busq = st.columns([2, 1])[0] # Ocupa el mismo espacio que si hubiera otro
        col_resp_f = None

    with col_busq:
        busqueda_radicado = st.text_input(
            "🔍 Buscador de radicados", 
            placeholder="Ej: 2024-EXT-001", 
            on_change=on_filter_change,
            help="Permite buscar por el número completo o parcial del radicado. Permite copiar y pegar."
        )

    filtro_responsable = "Todos"
    if puede_ver_todo and col_resp_f:
        with col_resp_f:
            usuarios_list = usuario_service.listar_usuarios()
            usuarios_f_opts = {"Todos": "Todos los responsables"}
            for u in usuarios_list:
                if u.get("activo", True):
                    usuarios_f_opts[str(u["_id"])] = f"{u.get('nombre_completo', u['usuario'])}"
            
            filtro_responsable = st.selectbox(
                "Filtrar por Responsable", 
                options=list(usuarios_f_opts.keys()), 
                format_func=lambda x: usuarios_f_opts[x],
                key="filtro_responsable",
                on_change=on_filter_change
            )

    # Fila 2: Estado, Grupo y Vencimiento
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        opciones_estado = ["Todos", "pendiente", "en_tramite", "en_revision", "respondido", "archivado", "traslado_competencia"]
        filtro_estado = st.selectbox("Filtrar por Estado", options=opciones_estado, format_func=lambda x: x.replace("_", " ").title(), key="filtro_estado", on_change=on_filter_change)
    
    with col_f2:
        # Preparar opciones de grupo con "Todos"
        grupos_opts = {"Todos": "Todos los grupos"}
        grupos_opts.update(grupos_dict)
        filtro_grupo = st.selectbox(
            "Filtrar por Grupo", 
            options=list(grupos_opts.keys()), 
            format_func=lambda x: grupos_opts[x], 
            key="filtro_grupo", 
            on_change=on_filter_change
        )

    with col_f3:
        opciones_venc = ["Todos", "Vencidas", "Vencen Hoy", "Próximas a Vencer", "A Tiempo"]
        filtro_vencimiento = st.selectbox("Filtrar por Vencimiento (Solo Activas)", options=opciones_venc, key="filtro_vencimiento", on_change=on_filter_change, help="Próximas a Vencer considera radicados que vencen en los próximos 5 días.")

    filtros = {
        "estado": filtro_estado, 
        "grupo": filtro_grupo,
        "vencimiento": filtro_vencimiento,
        "responsable_id": filtro_responsable,
        "busqueda": busqueda_radicado.strip()
    }

    
    # Checkbox para ver solo lo propio (solo para usuarios que pueden ver todo)
    if puede_ver_todo:
        st.checkbox(
            "🔍 Ver solo mis radicados asignados", 
            key="filtro_ver_solo_mio", 
            on_change=on_filter_change,
            help="Si se marca, solo verás la correspondencia donde tú eres el responsable."
        )
    
    st.divider()

    # --- Estilo CSS para forzar el centrado de cabeceras ---
    st.markdown("""
        <style>
            /* Intentar centrar las cabeceras del dataframe interactivo */
            [data-testid="stDataFrame"] div[class*="StyledDataGridHeaderCell"] {
                justify-content: center !important;
                text-align: center !important;
            }
            [data-testid="stDataFrame"] div[role="columnheader"] > div {
                justify-content: center !important;
                text-align: center !important;
            }
            /* Refuerzo para el texto dentro de la cabecera */
            [data-testid="stDataFrame"] div[role="columnheader"] span {
                text-align: center !important;
                width: 100%;
            }
        </style>
    """, unsafe_allow_html=True)


    # --- Paginación ---
    if "page_correspondencia" not in st.session_state:
        st.session_state["page_correspondencia"] = 1
        
    page_size = 50

    current_page = max(1, st.session_state["page_correspondencia"])
    st.session_state["page_correspondencia"] = current_page
    skip = (current_page - 1) * page_size
    
    datos_corr, total_docs = cargar_datos(skip=skip, limit=page_size, filtros=filtros)
    total_pages = max(1, (total_docs + page_size - 1) // page_size)
    
    # Función interna para renderizar controles de paginación
    def render_paginacion(posicion):
        c_prev, c_info, c_next = st.columns([1, 2, 1])
        with c_prev:
            if st.button("⬅️ Anterior", disabled=(current_page <= 1), key=f"btn_prev_{posicion}"):
                st.session_state["page_correspondencia"] -= 1
                st.rerun()
        with c_info:
            st.markdown(f"<div style='text-align: center; padding-top: 5px;'>Página {current_page} de {total_pages} (Total: {total_docs})</div>", unsafe_allow_html=True)
        with c_next:
            if st.button("Siguiente ➡️", disabled=(current_page >= total_pages), key=f"btn_next_{posicion}"):
                st.session_state["page_correspondencia"] += 1
                st.rerun()

    # Renderizar paginación superior
    render_paginacion("top")

            
    st.write("")
    
    if not datos_corr:
        st.info("No hay correspondencia que coincida con los filtros en esta página.")
    else:
        import pandas as pd
        
        st.write("Selecciona una fila en la tabla para gestionar el radicado.")
        
        tabla_datos = []
        for c in datos_corr:
            responsable = c.get("responsable_actual", {}).get("nombre", "Sin asignar")
            
            # Calcular tiempo restante
            fecha_venc_dt = c.get('fecha_vencimiento')
            estado = c.get("estado_actual", "")
            es_finalizado = estado in ["respondido", "archivado", "traslado_competencia"]
            
            dias_restantes_val = None
            tiempo_restante = "✅ Cerrado"
            if not es_finalizado and fecha_venc_dt:
                if isinstance(fecha_venc_dt, datetime):
                    if fecha_venc_dt.tzinfo is None:
                        fecha_venc_dt = fecha_venc_dt.replace(tzinfo=timezone.utc)
                    fecha_venc_utc = fecha_venc_dt.astimezone(timezone.utc)
                    colombia_tz = timezone(timedelta(hours=-5))
                    hoy = datetime.now(colombia_tz)
                    dias_calendario = (fecha_venc_utc.date() - hoy.date()).days
                    dias_restantes_val = dias_calendario
                    
                    if dias_calendario < 0:
                        inicio = fecha_venc_utc.date()
                        fin = hoy.date()
                        dias_habiles = 0
                        actual = inicio + timedelta(days=1)
                        co_holidays = holidays.CO()
                        while actual <= fin:
                            if actual.weekday() < 5 and actual not in co_holidays:
                                dias_habiles += 1
                            actual += timedelta(days=1)
                        tiempo_restante = f"🛑 {dias_habiles} d. atraso"
                        dias_restantes_val = -dias_habiles
                    elif dias_calendario == 0:
                        tiempo_restante = "⚠️ Vence hoy"
                    elif dias_calendario > 0:
                        inicio = hoy.date()
                        fin = fecha_venc_utc.date()
                        dias_habiles = 0
                        actual = inicio + timedelta(days=1)
                        co_holidays = holidays.CO()
                        while actual <= fin:
                            if actual.weekday() < 5 and actual not in co_holidays:
                                dias_habiles += 1
                            actual += timedelta(days=1)
                        if dias_habiles <= 5:
                            tiempo_restante = f"⚠️ {dias_habiles} d. restantes"
                        else:
                            tiempo_restante = f"⏳ {dias_habiles} d. restantes"
                        dias_restantes_val = dias_habiles
            elif not fecha_venc_dt and not es_finalizado:
                tiempo_restante = "N/A"

            # Formatear fecha de radicación simplificada
            f_rad = c.get("fecha_radicacion")
            f_rad_str = f_rad.strftime("%Y-%m-%d") if isinstance(f_rad, datetime) else str(f_rad)[:10]

            tabla_datos.append({
                "_id": str(c["_id"]),
                "Radicado": c.get("numero_radicado", ""),
                "F. Radicado": f_rad_str,
                "Peticionario": c.get("peticionario", ""),
                "Asunto": c.get("asunto", ""),
                "Estado": estado.replace("_", " ").title(),
                "Tiempo": tiempo_restante,
                "Responsable": responsable,
                "R. Respuesta": c.get("respuesta", {}).get("numero_oficio", "-"),
                "_dias_num": dias_restantes_val
            })

            
        df = pd.DataFrame(tabla_datos)
        
        # Calcular altura para evitar scroll interno (aprox 35px por fila + cabecera)
        altura_dinamica = (len(df) + 1) * 35 + 3
        
        # Configuración de columnas con títulos en negrita Unicode y centrado
        column_config = {
            "Radicado": st.column_config.TextColumn("𝐑𝐚𝐝𝐢𝐜𝐚𝐝𝐨", help="Número único de identificación del radicado"),
            "F. Radicado": st.column_config.TextColumn("𝐅. 𝐑𝐚𝐝𝐢𝐜𝐚𝐝𝐨", help="Fecha en que se recibió el documento"),
            "Peticionario": st.column_config.TextColumn("𝐏𝐞𝐭𝐢𝐜𝐢𝐨𝐧𝐚𝐫𝐢𝐨"),
            "Asunto": st.column_config.TextColumn("𝐀𝐬𝐮𝐧𝐭𝐨"),
            "Estado": st.column_config.TextColumn("𝐄𝐬𝐭𝐚𝐝𝐨"),
            "Tiempo": st.column_config.TextColumn("𝐓𝐢𝐞𝐦𝐩𝐨", help="Tiempo restante para el vencimiento"),
            "Responsable": st.column_config.TextColumn("𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐚𝐛𝐥𝐞"),
            "R. Respuesta": st.column_config.TextColumn("𝐑. 𝐑𝐞𝐬𝐩𝐮𝐞𝐬𝐭𝐚", help="Referencia de la respuesta emitida"),
            "_dias_num": None # Ocultar columna auxiliar
        }

        # Función para aplicar colores según el tiempo restante y el estado
        def style_rows(row):
            styles = [""] * len(row)
            
            # --- PALETA DE COLORES TENUES ---
            ROJO_TENUE = "background-color: #FFEBEE; color: #B71C1C;"
            NARANJA_TENUE = "background-color: #FFF3E0; color: #E65100;"
            AMARILLO_TENUE = "background-color: #FFFDE7; color: #F57F17;"
            VERDE_TENUE = "background-color: #E8F5E9; color: #1B5E20;"
            GRIS_TENUE = "background-color: #F5F5F5; color: #616161;"

            # --- Estilo para columna TIEMPO ---
            dias = row["_dias_num"]
            idx_tiempo = row.index.get_loc("Tiempo")
            if row["Tiempo"] == "✅ Cerrado":
                styles[idx_tiempo] = VERDE_TENUE
            elif not pd.isna(dias):
                if dias < 0:
                    styles[idx_tiempo] = ROJO_TENUE        # Vencido (Atrasado)
                elif dias <= 5:
                    styles[idx_tiempo] = NARANJA_TENUE     # Urgente (0-5 días restantes)
                elif dias <= 10:
                    styles[idx_tiempo] = AMARILLO_TENUE    # Preventivo (6-10 días restantes)
                else:
                    styles[idx_tiempo] = VERDE_TENUE       # Cómodo (> 10 días restantes)
            
            # --- Estilo para columna ESTADO ---
            estado_texto = row["Estado"].lower()
            idx_estado = row.index.get_loc("Estado")
            
            if "pendiente" in estado_texto:
                styles[idx_estado] = ROJO_TENUE
            elif "tramite" in estado_texto or "revision" in estado_texto:
                styles[idx_estado] = AMARILLO_TENUE
            elif "respondido" in estado_texto or "archivado" in estado_texto:
                styles[idx_estado] = VERDE_TENUE
            elif "traslado" in estado_texto:
                styles[idx_estado] = GRIS_TENUE
                
            return styles

        # Aplicar el estilo al dataframe (excluyendo _id para visualización pero manteniéndolo en df original para selección)
        df_display = df.drop(columns=["_id"])
        styled_df = df_display.style.apply(style_rows, axis=1)

        # Renderizar dataframe interactivo
        event = st.dataframe(
            styled_df, 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            height=altura_dinamica,
            column_config=column_config
        )

        
        if event.selection.rows:
            idx = event.selection.rows[0]
            id_sel = df.iloc[idx]["_id"]
            if st.session_state.get("last_opened_id") != id_sel:
                st.session_state["last_opened_id"] = id_sel
                corr_sel = next((c for c in datos_corr if str(c["_id"]) == id_sel), None)
                if corr_sel:
                    modal_gestion_correspondencia(corr_sel)
        else:
            st.session_state["last_opened_id"] = None
        
        # Renderizar paginación inferior
        st.write("")
        render_paginacion("bottom")

