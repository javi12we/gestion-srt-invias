import streamlit as st


CLAVE_SESION = "usuario_autenticado"


def iniciar_sesion(usuario: dict) -> None:
    st.session_state[CLAVE_SESION] = usuario


def obtener_sesion():
    usuario_sesion = st.session_state.get(CLAVE_SESION)
    if usuario_sesion and "id" in usuario_sesion:
        try:
            from app.repositories.usuario_repo import UsuarioRepositorio
            repo = UsuarioRepositorio()
            registro = repo.buscar_por_id(usuario_sesion["id"])
            if registro:
                # Recargar roles
                usuario_sesion["roles"] = registro.get("roles", [])
                # Recargar permisos (permisos_extra + permisos de sus roles)
                permisos = set(registro.get("permisos_extra", []))
                roles = registro.get("roles", [])
                if roles:
                    roles_docs = list(repo.roles.find({"nombre": {"$in": roles}, "activo": True}))
                    for r in roles_docs:
                        permisos.update(r.get("permisos", []))
                usuario_sesion["permisos"] = sorted(permisos)
                # Recargar grupos de trabajo (pertenencia y liderazgo) desde asignaciones_grupo
                from app.services.asignacion_grupo_service import AsignacionGrupoService
                grupos = AsignacionGrupoService().claves_de_usuario(usuario_sesion["id"])
                usuario_sesion["grupos"] = grupos["grupos"]
                usuario_sesion["grupos_lider"] = grupos["lider"]
                # Trámites SUIT que puede diligenciar (todos si es administrador)
                from app.services.suit_service import SuitService, permisos_efectivos
                usuario_sesion["suit_tramites"] = SuitService().tramites_visibles(
                    usuario_sesion["id"], permisos_efectivos(usuario_sesion)
                )
                st.session_state[CLAVE_SESION] = usuario_sesion
        except Exception:
            pass
    return usuario_sesion


def cerrar_sesion() -> None:
    st.session_state.pop(CLAVE_SESION, None)


def sesion_activa() -> bool:
    return obtener_sesion() is not None
