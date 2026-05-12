import pandas as pd
import streamlit as st

from app.core.autorizacion import validar_permiso, ValidacionAutorizacion
from app.core.sesion import obtener_sesion
from app.core.streamlit_compat import show_dataframe
from app.services.usuario_service import UsuarioService


def render(sesion=None):
    servicio = UsuarioService()
    sesion = sesion or obtener_sesion()

    st.title("Administración de usuarios")

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    try:
        validar_permiso(sesion.get("permisos", []), "usuario.ver")
    except ValidacionAutorizacion:
        st.error("No tienes permisos para ver este módulo.")
        st.stop()

    # Tracking de vistas removido

    usuarios = servicio.listar_usuarios()
    datos = []
    for usuario in usuarios:
        datos.append(
            {
                "usuario": usuario.get("usuario", ""),
                "nombre_completo": usuario.get("nombre_completo", ""),
                "email": usuario.get("email", ""),
                "activo": usuario.get("activo", False),
                "roles": ", ".join(usuario.get("roles", [])),
            }
        )

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.subheader("Listado de usuarios")
    with col_h2:
        if st.button("🔄 Actualizar", use_container_width=True, key="refresh_usuarios"):
            st.rerun()

    show_dataframe(pd.DataFrame(datos), hide_index=True)

    if not usuarios:
        st.info("Todavía no hay usuarios registrados.")
        st.stop()

    # Cargar datos comunes
    roles_disponibles = [rol.get("nombre", "") for rol in servicio.repositorio.listar_roles()]
    permisos_disponibles = [permiso.get("clave", "") for permiso in servicio.repositorio.listar_permisos()]

    # SECCIÓN: CAMBIAR ESTADO
    st.divider()
    st.subheader("Cambiar estado")

    if "usuario.desactivar" not in sesion.get("permisos", []):
        st.warning("No tienes permiso para cambiar estado de usuarios.")
    else:
        mapa_usuarios = {
            f"{usuario.get('usuario', '')} - {usuario.get('nombre_completo', '')}": usuario for usuario in usuarios
        }
        seleccion = st.selectbox("Selecciona un usuario para cambiar estado", options=list(mapa_usuarios.keys()), key="select_estado")
        usuario_seleccionado = mapa_usuarios[seleccion]

        col_estado, col_accion = st.columns(2)
        with col_estado:
            st.write(f"**Estado actual:** {'Activo' if usuario_seleccionado.get('activo', False) else 'Inactivo'}")
        with col_accion:
            if usuario_seleccionado.get('activo', False):
                if st.button("Desactivar usuario", key=f"desactivar_usuario_{usuario_seleccionado.get('_id')}"):
                    try:
                        servicio.desactivar_usuario(
                            str(usuario_seleccionado["_id"]),
                            permisos_usuario=sesion.get("permisos", []),
                            usuario_actual=sesion["usuario"]
                        )
                        st.success("Usuario desactivado")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
            else:
                if st.button("Activar usuario", key=f"activar_usuario_{usuario_seleccionado.get('_id')}"):
                    try:
                        servicio.activar_usuario(
                            str(usuario_seleccionado["_id"]),
                            permisos_usuario=sesion.get("permisos", []),
                            usuario_actual=sesion["usuario"]
                        )
                        st.success("Usuario activado")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))

    # SECCIÓN: CREAR USUARIO
    st.divider()
    st.subheader("Crear usuario")

    if "usuario.crear" not in sesion.get("permisos", []):
        st.warning("No tienes permiso para crear usuarios.")
    else:
        with st.form("form_crear_usuario"):
            usuario = st.text_input("Usuario")
            nombre_completo = st.text_input("Nombre completo")
            email = st.text_input("Correo electrónico")
            password = st.text_input("Contraseña", type="password")
            activo = st.checkbox("Activo", value=True)
            roles = st.multiselect("Roles", options=roles_disponibles)
            permisos_extra = st.multiselect("Permisos extra", options=permisos_disponibles)
            enviar = st.form_submit_button("Crear")

        if enviar:
            try:
                servicio.crear_usuario(
                    {
                        "usuario": usuario.strip(),
                        "nombre_completo": nombre_completo.strip(),
                        "email": email.strip(),
                        "password": password,
                        "activo": activo,
                        "roles": roles,
                        "permisos_extra": permisos_extra,
                        "creado_por": sesion["usuario"],
                    },
                    permisos_usuario=sesion.get("permisos", [])
                )
                st.success("Usuario creado correctamente")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

    # SECCIÓN: EDITAR USUARIO
    st.divider()
    st.subheader("Editar usuario")

    if "usuario.editar" not in sesion.get("permisos", []):
        st.warning("No tienes permiso para editar usuarios.")
    else:
        mapa_usuarios = {
            f"{usuario.get('usuario', '')} - {usuario.get('nombre_completo', '')}": usuario for usuario in usuarios
        }
        seleccion_editar = st.selectbox("Selecciona un usuario para editar", options=list(mapa_usuarios.keys()), key="select_editar")
        usuario_seleccionado_editar = mapa_usuarios[seleccion_editar]

        with st.form("form_editar_usuario"):
            usuario_editado = st.text_input("Usuario", value=usuario_seleccionado_editar.get("usuario", ""))
            nombre_editado = st.text_input("Nombre completo", value=usuario_seleccionado_editar.get("nombre_completo", ""))
            email_editado = st.text_input("Correo electrónico", value=usuario_seleccionado_editar.get("email", ""))
            password_nueva = st.text_input("Nueva contraseña (opcional)", type="password")
            activo_editado = st.checkbox("Activo", value=usuario_seleccionado_editar.get("activo", False))
            roles_seleccionados = st.multiselect(
                "Roles",
                options=roles_disponibles,
                default=usuario_seleccionado_editar.get("roles", []),
            )
            permisos_seleccionados = st.multiselect(
                "Permisos extra",
                options=permisos_disponibles,
                default=usuario_seleccionado_editar.get("permisos_extra", []),
            )
            enviar_edicion = st.form_submit_button("Guardar cambios")

        if enviar_edicion:
            try:
                servicio.actualizar_usuario(
                    str(usuario_seleccionado_editar["_id"]),
                    {
                        "usuario": usuario_editado.strip(),
                        "nombre_completo": nombre_editado.strip(),
                        "email": email_editado.strip(),
                        "password": password_nueva,
                        "activo": activo_editado,
                        "roles": roles_seleccionados,
                        "permisos_extra": permisos_seleccionados,
                        "actualizado_por": sesion["usuario"],
                    },
                    permisos_usuario=sesion.get("permisos", [])
                )
                st.success("Usuario actualizado correctamente")
                st.rerun()
            except ValueError as error:
                st.error(str(error))
