import streamlit as st
import pandas as pd

from app.core.autorizacion import validar_permiso, ValidacionAutorizacion
from app.core.sesion import obtener_sesion
from app.core.streamlit_compat import show_dataframe
from app.services.rol_service import RolService
from app.services.usuario_service import UsuarioService


def render(sesion=None):
    servicio = RolService()
    usuario_serv = UsuarioService()
    sesion = sesion or obtener_sesion()

    st.title("Administración de roles")

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    try:
        validar_permiso(sesion.get("permisos", []), "rol.ver")
    except ValidacionAutorizacion:
        st.error("No tienes permisos para ver este módulo.")
        st.stop()

    # Tracking de vistas removido

    roles = servicio.listar_roles()
    datos = []
    for rol in roles:
        datos.append({
            "nombre": rol.get("nombre", ""),
            "descripcion": rol.get("descripcion", ""),
            "activo": rol.get("activo", False),
            "permisos": ", ".join(rol.get("permisos", [])),
        })

    st.subheader("Listado de roles")
    show_dataframe(pd.DataFrame(datos), hide_index=True)

    if not roles:
        st.info("No hay roles definidos aún.")
        st.stop()

    # Cargar datos comunes
    permisos_disponibles = [p.get("clave") for p in usuario_serv.repositorio.listar_permisos()]

    # SECCIÓN: CREAR ROL
    st.divider()
    st.subheader("Crear rol")

    if "rol.crear" not in sesion.get("permisos", []):
        st.warning("No tienes permiso para crear roles.")
    else:
        with st.form("form_crear_rol"):
            nombre = st.text_input("Nombre del rol")
            descripcion = st.text_area("Descripción")
            permisos = st.multiselect("Permisos", options=permisos_disponibles)
            activo = st.checkbox("Activo", value=True)
            enviar = st.form_submit_button("Crear rol")

        if enviar:
            try:
                servicio.crear_rol(
                    {
                        "nombre": nombre.strip(),
                        "descripcion": descripcion.strip(),
                        "permisos": permisos,
                        "activo": activo,
                        "creado_por": sesion["usuario"],
                    },
                    permisos_usuario=sesion.get("permisos", [])
                )
                st.success("Rol creado correctamente")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    # SECCIÓN: CAMBIAR ESTADO
    st.divider()
    st.subheader("Cambiar estado")

    if "rol.desactivar" not in sesion.get("permisos", []):
        st.warning("No tienes permiso para cambiar estado de roles.")
    else:
        mapa_roles = {f"{r.get('nombre')}": r for r in roles}
        seleccion_estado = st.selectbox("Selecciona un rol para cambiar estado", options=list(mapa_roles.keys()), key="select_estado")
        rol_sel_estado = mapa_roles[seleccion_estado]

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Nombre:** {rol_sel_estado.get('nombre')}")
            st.write(f"**Descripción:** {rol_sel_estado.get('descripcion')}")
        with col2:
            st.write(f"**Estado:** {'Activo' if rol_sel_estado.get('activo') else 'Inactivo'}")
            if rol_sel_estado.get('activo'):
                if st.button("Desactivar rol", key=f"desactivar_rol_{rol_sel_estado.get('_id')}"):
                    try:
                        servicio.desactivar_rol(
                            str(rol_sel_estado.get("_id")),
                            permisos_usuario=sesion.get("permisos", []),
                            usuario_actual=sesion["usuario"]
                        )
                        st.success("Rol desactivado")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
            else:
                if st.button("Activar rol", key=f"activar_rol_{rol_sel_estado.get('_id')}"):
                    try:
                        servicio.activar_rol(
                            str(rol_sel_estado.get("_id")),
                            permisos_usuario=sesion.get("permisos", []),
                            usuario_actual=sesion["usuario"]
                        )
                        st.success("Rol activado")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))

    # SECCIÓN: EDITAR ROL
    st.divider()
    st.subheader("Editar rol")

    if "rol.editar" not in sesion.get("permisos", []):
        st.warning("No tienes permiso para editar roles.")
    else:
        mapa_roles = {f"{r.get('nombre')}": r for r in roles}
        seleccion_editar = st.selectbox("Selecciona un rol para editar", options=list(mapa_roles.keys()), key="select_editar")
        rol_sel_editar = mapa_roles[seleccion_editar]

        with st.form("form_editar_rol"):
            nombre_n = st.text_input("Nombre", value=rol_sel_editar.get("nombre"))
            descripcion_n = st.text_area("Descripción", value=rol_sel_editar.get("descripcion", ""))
            permisos_n = st.multiselect("Permisos", options=permisos_disponibles, default=rol_sel_editar.get("permisos", []))
            activo_n = st.checkbox("Activo", value=rol_sel_editar.get("activo", False))
            enviar_ed = st.form_submit_button("Guardar cambios")

        if enviar_ed:
            try:
                servicio.actualizar_rol(
                    str(rol_sel_editar.get("_id")),
                    {
                        "nombre": nombre_n.strip(),
                        "descripcion": descripcion_n.strip(),
                        "permisos": permisos_n,
                        "activo": activo_n,
                        "actualizado_por": sesion["usuario"],
                    },
                    permisos_usuario=sesion.get("permisos", [])
                )
                st.success("Rol actualizado correctamente")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
