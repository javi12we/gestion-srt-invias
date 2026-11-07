import pandas as pd
import streamlit as st

from app.core.autorizacion import ValidacionAutorizacion
from app.core.catalogos import TRAMITES_SUIT
from app.core.sesion import obtener_sesion
from app.core.ui_titulos import mostrar_titulo_decorado
from app.services.asignacion_grupo_service import AsignacionGrupoService
from app.services.suit_service import ErrorSuit, SuitService, permisos_efectivos


def _puede_gestionar(sesion: dict) -> bool:
    es_admin = any(r in {"admin", "administrador"} for r in sesion.get("roles", []))
    return es_admin or "permisos" in (sesion.get("grupos_lider") or [])


def _etiqueta(tramite: str) -> str:
    return TRAMITES_SUIT[tramite]["label_corto"]


@st.dialog("Roles Permisos", width="large")
def _modal_roles_permisos(usuario_doc: dict, sesion: dict, servicio: SuitService,
                          tramites_actuales: list[str], repartibles: list[str]) -> None:
    st.markdown(f"**Usuario:** {usuario_doc.get('nombre_completo', '')} (@{usuario_doc.get('usuario', '')})")
    st.caption(
        "Marca los trámites SUIT que esta persona puede ver y diligenciar. "
        "Solo puedes repartir los trámites que tú tienes asignados."
        if "grupo.gestionar_miembros" not in permisos_efectivos(sesion)
        else "Marca los trámites SUIT que esta persona puede ver y diligenciar."
    )

    fuera_de_alcance = [t for t in tramites_actuales if t not in repartibles]
    if fuera_de_alcance:
        st.caption("Otros trámites asignados (no los puedes modificar): "
                   + ", ".join(_etiqueta(t) for t in fuera_de_alcance))

    with st.form(f"form_permisos_suit_{usuario_doc['_id']}"):
        seleccion = st.multiselect(
            "Trámites SUIT",
            options=repartibles,
            default=[t for t in tramites_actuales if t in repartibles],
            format_func=lambda t: f"SUIT - {_etiqueta(t)}",
        )
        enviar = st.form_submit_button("💾 Guardar cambios", use_container_width=True, type="primary")

    if enviar:
        try:
            servicio.definir_tramites_usuario(
                str(usuario_doc["_id"]), seleccion,
                actor=sesion.get("usuario", "sistema"),
                permisos_actor=permisos_efectivos(sesion),
                actor_id=sesion.get("id"),
            )
        except (ErrorSuit, ValidacionAutorizacion) as e:
            st.warning(str(e))
            return
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
    st.caption("Administra qué usuarios del grupo de trabajo Permisos pueden cargar cada trámite SUIT.")

    if msg := st.session_state.pop("mensaje_exito_gestores_permisos", None):
        st.success(msg)

    servicio = SuitService()
    repartibles = servicio.tramites_repartibles(sesion.get("id"), permisos_efectivos(sesion))
    if not repartibles:
        st.info("Aún no tienes trámites SUIT asignados para repartir. Solicítalos a un administrador.")
        return

    usuarios = AsignacionGrupoService().usuarios_de_grupo("permisos")
    if not usuarios:
        st.info("Todavía no hay usuarios registrados en el grupo de trabajo de Permisos.")
        return

    mapa = servicio.mapa_tramites_activos()

    df = pd.DataFrame(
        [
            {
                "_id": str(u["_id"]),
                "Usuario": u.get("usuario", ""),
                "Nombre": u.get("nombre_completo", ""),
                "Correo": u.get("email", ""),
                "Estado": "Activo" if u.get("activo", False) else "Inactivo",
                "Roles": ", ".join(u.get("roles", [])),
                "Trámites asignados": ", ".join(_etiqueta(t) for t in mapa.get(str(u["_id"]), [])),
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
                _modal_roles_permisos(u_sel, sesion, servicio, mapa.get(id_sel, []), repartibles)
    else:
        st.session_state["last_opened_usuario_permiso_id"] = None

    st.caption(f"{len(df)} usuario(s) en el grupo de Permisos")
