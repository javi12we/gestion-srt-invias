import pandas as pd
import streamlit as st

from app.core.catalogos import PERMISOS_SUIT_CARGUE
from app.core.sesion import obtener_sesion
from app.core.ui_titulos import mostrar_titulo_decorado
from app.services.usuario_service import UsuarioService

_CLAVES_SUIT = [p["clave"] for p in PERMISOS_SUIT_CARGUE]
_LABELS_SUIT = {p["clave"]: p["label_corto"] for p in PERMISOS_SUIT_CARGUE}


def _puede_gestionar(sesion: dict) -> bool:
    roles = sesion.get("roles", [])
    es_admin = any(r in {"admin", "administrador"} for r in roles)
    es_lider_o_coordinador = any(r in {"coordinador", "lider"} for r in roles)
    return es_admin or (es_lider_o_coordinador and sesion.get("grupo_trabajo") == "permisos")


@st.dialog("Roles Permisos", width="large")
def _modal_roles_permisos(usuario_doc: dict, sesion: dict, servicio: UsuarioService) -> None:
    st.markdown(f"**Usuario:** {usuario_doc.get('nombre_completo', '')} (@{usuario_doc.get('usuario', '')})")
    st.caption("Marca los permisos SUIT que este usuario puede cargar. El resto de sus permisos no se modifica.")

    seleccion_actual = [c for c in usuario_doc.get("permisos_extra", []) if c in _CLAVES_SUIT]

    with st.form(f"form_permisos_suit_{usuario_doc['_id']}"):
        seleccion = st.multiselect(
            "Permisos de cargue SUIT",
            options=_CLAVES_SUIT,
            default=seleccion_actual,
            format_func=lambda c: f"SUIT - {_LABELS_SUIT.get(c, c)}",
        )
        enviar = st.form_submit_button("💾 Guardar cambios", use_container_width=True, type="primary")

    if enviar:
        servicio.actualizar_permisos_suit_usuario(
            str(usuario_doc["_id"]), seleccion, actor=sesion.get("usuario", "sistema")
        )
        st.session_state["mensaje_exito_gestores_permisos"] = "Permisos actualizados correctamente."
        st.session_state["last_opened_usuario_permiso_id"] = None
        st.rerun()


def render(sesion=None) -> None:
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    if not _puede_gestionar(sesion):
        st.error("No tienes permisos para ver este módulo.")
        st.stop()

    mostrar_titulo_decorado("Gestores Perm.")
    st.caption("Administra qué usuarios del grupo de trabajo Permisos pueden cargar cada tipo de permiso SUIT.")

    if msg := st.session_state.pop("mensaje_exito_gestores_permisos", None):
        st.success(msg)

    servicio = UsuarioService()
    usuarios = servicio.listar_usuarios_grupo_trabajo("permisos")

    if not usuarios:
        st.info("Todavía no hay usuarios registrados en el grupo de trabajo de Permisos.")
        return

    df = pd.DataFrame(
        [
            {
                "_id": str(u["_id"]),
                "Usuario": u.get("usuario", ""),
                "Nombre": u.get("nombre_completo", ""),
                "Correo": u.get("email", ""),
                "Estado": "Activo" if u.get("activo", False) else "Inactivo",
                "Roles": ", ".join(u.get("roles", [])),
                "Permisos asignados": ", ".join(
                    _LABELS_SUIT[c] for c in u.get("permisos_extra", []) if c in _LABELS_SUIT
                ),
            }
            for u in usuarios
        ]
    )

    st.subheader("Usuarios del grupo de trabajo Permisos")
    df_display = df.drop(columns=["_id"])
    altura = min(50 + len(df) * 35, 500)
    event = st.dataframe(
        df_display,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        height=altura,
    )

    if event.selection.rows:
        idx = event.selection.rows[0]
        id_sel = df.iloc[idx]["_id"]
        if st.session_state.get("last_opened_usuario_permiso_id") != id_sel:
            st.session_state["last_opened_usuario_permiso_id"] = id_sel
            u_sel = next((u for u in usuarios if str(u["_id"]) == id_sel), None)
            if u_sel:
                _modal_roles_permisos(u_sel, sesion, servicio)
    else:
        st.session_state["last_opened_usuario_permiso_id"] = None

    st.caption(f"{len(df)} usuario(s) en el grupo de Permisos")
