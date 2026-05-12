import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from app.core.sesion import obtener_sesion
from app.services.correspondencia_service import CorrespondenciaService
from app.services.opciones_service import OpcionesService
from app.services.usuario_service import UsuarioService



st.title("Correspondencia")
sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()

roles = sesion.get("roles", [])
id_usuario_actual = sesion.get("id_usuario")
nombre_usuario_actual = sesion.get("nombre_completo") or sesion.get("usuario")

# Definir permisos basados en los roles descritos por el usuario
is_admin = "admin" in roles
is_asignacion = "asignacion" in roles or is_admin
is_coordinador = "coordinador" in roles
is_lider = "lider" in roles
is_gestor = "gestor" in roles

can_assign = is_asignacion or is_coordinador or is_lider

# Si no tiene ningún rol relacionado, no mostramos nada
if not (is_asignacion or is_coordinador or is_lider or is_gestor):
    st.info("No tienes permisos para acceder a este módulo.")
    st.stop()

service = CorrespondenciaService()
opciones_service = OpcionesService()
usuario_service = UsuarioService()

# Cargar opciones para los selects
tipos_dict = {op["clave"]: op["etiqueta"] for op in opciones_service.obtener_opciones("tipo")}
grupos_dict = {op["clave"]: op["etiqueta"] for op in opciones_service.obtener_opciones("grupo")}
clases_dict = {op["clave"]: op["etiqueta"] for op in opciones_service.obtener_opciones("clase_correspondencia")}

# Si no hay opciones, usar unas por defecto
if not tipos_dict: tipos_dict = {"memorando": "Memorando", "oficio": "Oficio", "pqrd": "PQRD"}
if not grupos_dict: grupos_dict = {"permisos": "Permisos", "solicitudes": "Solicitudes", "otros": "Otros"}
if not clases_dict: clases_dict = {"informes": "Informes", "peticiones": "Peticiones", "quejas": "Quejas"}

def cargar_datos(skip=0, limit=10, filtros=None):
    # asignacion ve TODA la correspondencia, los demas solo la asignada a ellos
    if is_asignacion:
        return service.listar_correspondencia(ver_todas=True, skip=skip, limit=limit, filtros=filtros)
    else:
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
    st.markdown(f"## 📄 Radicado: `{numero_radicado}`")
    
    # 2. Calcular días de vencimiento
    fecha_venc_dt = corr_actual.get('fecha_vencimiento')
    alerta_vencimiento = ""
    if fecha_venc_dt:
        if isinstance(fecha_venc_dt, datetime):
            if fecha_venc_dt.tzinfo is None:
                fecha_venc_dt = fecha_venc_dt.replace(tzinfo=timezone.utc)
            hoy = datetime.now(timezone.utc)
            dias_restantes = (fecha_venc_dt - hoy).days
            
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
                                    nombre_usuario_actual
                                )
                                st.success("Actualizado")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # Acción 2: Asignar (Traslado a otro usuario)
        if can_assign:
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
                                    comentario_asig
                                )
                                st.success("Asignado exitosamente")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # Acción 3: Dar Respuesta / Archivar / Traslado por Competencia
        es_responsable = corr_actual.get("responsable_actual", {}).get("usuario_id") == id_usuario_actual
        if es_responsable or is_asignacion:
            with col_acc3 if is_asignacion else (col_acc2 if can_assign else col_acc1):
                with st.popover("✅ Responder / Cerrar", use_container_width=True):
                    if estado_actual not in ["respondido", "archivado", "traslado_competencia"]:
                        st.write("Cargar Respuesta")
                        with st.form(f"form_resp_{id_seleccionado}"):
                            num_oficio = st.text_input("Número de Oficio")
                            comentario_resp = st.text_input("Comentario", value="Se da respuesta")
                            if st.form_submit_button("Marcar como Respondido"):
                                if num_oficio:
                                    service.dar_respuesta(id_seleccionado, num_oficio, nombre_usuario_actual, comentario_resp)
                                    st.success("Respuesta registrada")
                                    st.rerun()
                                else:
                                    st.error("El número de oficio es obligatorio")
                    
                    if estado_actual not in ["archivado", "traslado_competencia"]:
                        st.write("Archivar Radicado")
                        with st.form(f"form_archivar_{id_seleccionado}"):
                            comentario_arch = st.text_input("Comentario (Opcional)", value="Cierre del caso")
                            if st.form_submit_button("Archivar", type="primary"):
                                service.archivar(id_seleccionado, nombre_usuario_actual, comentario_arch)
                                st.success("Archivado")
                                st.rerun()
                                
                    if estado_actual not in ["archivado", "traslado_competencia"]:
                        st.write("Traslado por Competencia")
                        with st.form(f"form_traslado_comp_{id_seleccionado}"):
                            comentario_tc = st.text_input("Comentario", value="No es competencia de la entidad")
                            if st.form_submit_button("Trasladar", type="primary"):
                                service.cambiar_estado(id_seleccionado, "traslado_competencia", nombre_usuario_actual, comentario_tc)
                                st.success("Traslado por competencia registrado")
                                st.rerun()
                            
    # --- TRAZABILIDAD ---
    st.write("---")
    st.subheader("Trazabilidad (Historial)")
    trazabilidad = corr_actual.get("trazabilidad", [])
    for evento in reversed(trazabilidad): # Mostrar más recientes primero
        with st.container(border=True):
            st.write(f"**{formatear_fecha(evento.get('fecha'))} - {evento.get('tipo_evento').upper()}**")
            st.write(f"Ejecutor: {evento.get('usuario_ejecutor')}")
            st.write(f"Estado: {evento.get('estado_anterior', 'N/A')} ➡️ {evento.get('estado_nuevo')}")
            if evento.get('comentario'):
                st.info(evento.get('comentario'))


# Construir pestañas
tabs_names = ["Búsqueda y Gestión"]
if is_asignacion:
    tabs_names.append("Nueva Correspondencia")

tabs = st.tabs(tabs_names)

# Renderizar pestaña "Nueva Correspondencia" si tiene acceso
if is_asignacion:
    with tabs[1]:
        st.subheader("Registrar Nuevo Radicado")
        with st.form("form_nueva_correspondencia", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                numero_radicado = st.text_input("Número de Radicado *")
                peticionario = st.text_input("Peticionario *")
                fecha_radicacion = st.date_input("Fecha de Radicación *")
            with col2:
                asunto = st.text_area("Asunto *", height=115)
            
            col3, col4, col5 = st.columns(3)
            with col3:
                tipo = st.selectbox("Tipo", options=list(tipos_dict.keys()), format_func=lambda x: tipos_dict.get(x, x))
            with col4:
                grupo = st.selectbox("Grupo", options=list(grupos_dict.keys()), format_func=lambda x: grupos_dict.get(x, x))
            with col5:
                clase = st.selectbox("Clase", options=list(clases_dict.keys()), format_func=lambda x: clases_dict.get(x, x))
                
            observaciones = st.text_area("Observaciones Generales (Opcional)")
            
            usuarios = usuario_service.listar_usuarios()
            usuarios_opts = {str(u["_id"]): f"{u.get('nombre_completo', u['usuario'])}" for u in usuarios if u.get("activo", True)}
            
            is_traslado = st.checkbox("Es Traslado por Competencia (Cierra el radicado sin asignar)")
            asignado_a = None
            if not is_traslado:
                asignado_a = st.selectbox("Asignar a *", options=list(usuarios_opts.keys()), format_func=lambda x: usuarios_opts[x])
            
            submit_btn = st.form_submit_button("Crear Correspondencia", type="primary")
            
            if submit_btn:
                if not numero_radicado or not asunto or not peticionario:
                    st.error("Los campos marcados con * son obligatorios.")
                else:
                    datos = {
                        "numero_radicado": numero_radicado,
                        "asunto": asunto,
                        "peticionario": peticionario,
                        "fecha_radicacion": datetime.combine(fecha_radicacion, datetime.min.time()).replace(tzinfo=timezone.utc),
                        "tipo": tipo,
                        "grupo": grupo,
                        "clase": clase,
                        "observaciones_generales": observaciones
                    }
                    try:
                        id_nuevo = service.crear_correspondencia(datos, nombre_usuario_actual)
                        if is_traslado:
                            service.cambiar_estado(id_nuevo, "traslado_competencia", nombre_usuario_actual, "Traslado por competencia inicial")
                            st.success(f"Correspondencia {numero_radicado} creada y trasladada por competencia.")
                        else:
                            service.asignar_correspondencia(
                                id_nuevo,
                                asignado_a,
                                usuarios_opts[asignado_a],
                                nombre_usuario_actual,
                                "Asignación inicial en radicación"
                            )
                            st.success(f"Correspondencia {numero_radicado} creada y asignada exitosamente.")
                    except Exception as e:
                        st.error(f"Error al crear: {str(e)}")

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
        
    col_f1, col_f2 = st.columns(2)
    opciones_estado = ["Todos", "pendiente", "en_tramite", "en_revision", "respondido", "archivado", "traslado_competencia"]
    filtro_estado = col_f1.selectbox("Filtrar por Estado", options=opciones_estado, format_func=lambda x: x.replace("_", " ").title(), key="filtro_estado", on_change=on_filter_change)
    
    opciones_venc = ["Todos", "Vencidas", "Vencen Hoy", "Próximas a Vencer", "A Tiempo"]
    filtro_vencimiento = col_f2.selectbox("Filtrar por Vencimiento (Solo Activas)", options=opciones_venc, key="filtro_vencimiento", on_change=on_filter_change)
    
    filtros = {"estado": filtro_estado, "vencimiento": filtro_vencimiento}
    st.divider()

    # --- Paginación ---
    if "page_correspondencia" not in st.session_state:
        st.session_state["page_correspondencia"] = 1
        
    page_size = 10
    current_page = st.session_state["page_correspondencia"]
    skip = (current_page - 1) * page_size
    
    datos_corr, total_docs = cargar_datos(skip=skip, limit=page_size, filtros=filtros)
    total_pages = max(1, (total_docs + page_size - 1) // page_size)
    
    # Renderizar controles de paginación
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("⬅️ Anterior", disabled=(current_page <= 1)):
            st.session_state["page_correspondencia"] -= 1
            st.rerun()
    with col_info:
        st.markdown(f"<div style='text-align: center; padding-top: 5px;'>Página {current_page} de {total_pages} (Total: {total_docs})</div>", unsafe_allow_html=True)
    with col_next:
        if st.button("Siguiente ➡️", disabled=(current_page >= total_pages)):
            st.session_state["page_correspondencia"] += 1
            st.rerun()
            
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
            
            tiempo_restante = "✅ Cerrado"
            if not es_finalizado and fecha_venc_dt:
                if isinstance(fecha_venc_dt, datetime):
                    if fecha_venc_dt.tzinfo is None:
                        fecha_venc_dt = fecha_venc_dt.replace(tzinfo=timezone.utc)
                    hoy = datetime.now(timezone.utc)
                    dias_restantes = (fecha_venc_dt - hoy).days
                    if dias_restantes < 0:
                        tiempo_restante = f"🛑 {-dias_restantes} d. atraso"
                    elif dias_restantes == 0:
                        tiempo_restante = "⚠️ Vence hoy"
                    elif dias_restantes <= 3:
                        tiempo_restante = f"⚠️ {dias_restantes} d. restantes"
                    else:
                        tiempo_restante = f"⏳ {dias_restantes} d. restantes"
            elif not fecha_venc_dt and not es_finalizado:
                tiempo_restante = "N/A"

            tabla_datos.append({
                "_id": str(c["_id"]),
                "Radicado": c.get("numero_radicado", ""),
                "Peticionario": c.get("peticionario", ""),
                "Asunto": c.get("asunto", ""),
                "Estado": estado.replace("_", " ").title(),
                "Tiempo": tiempo_restante,
                "Responsable": responsable
            })
            
        df = pd.DataFrame(tabla_datos)
        
        # Renderizar dataframe interactivo
        event = st.dataframe(
            df.drop(columns=["_id"]), 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if event.selection.rows:
            idx = event.selection.rows[0]
            id_sel = df.iloc[idx]["_id"]
            corr_sel = next((c for c in datos_corr if str(c["_id"]) == id_sel), None)
            if corr_sel:
                modal_gestion_correspondencia(corr_sel)
