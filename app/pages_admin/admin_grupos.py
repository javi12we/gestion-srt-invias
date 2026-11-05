"""Gestión de grupos de trabajo: miembros, líderes e historial de retiros.

Accesible para el administrador (todos los grupos) y para el líder de cada grupo
(solo el suyo). La lógica vive en AsignacionGrupoService.
"""

import pandas as pd
import streamlit as st

from app.core.autorizacion import ValidacionAutorizacion
from app.core.cache_datos import usuarios_activos_para_seleccion
from app.core.sesion import obtener_sesion
from app.core.ui_titulos import mostrar_titulo_decorado
from app.core.zona_horaria import formato_fecha_bogota
from app.services.asignacion_grupo_service import (
    PERMISO_GESTIONAR,
    AsignacionGrupoService,
    ErrorAsignacionGrupo,
)

_MSG = "_grupos_msg"
_FECHA = "%d/%m/%Y"


def _ejecutar(accion, mensaje_ok: str) -> bool:
    """Ejecuta una operación del servicio mostrando los errores de negocio."""
    try:
        accion()
    except (ErrorAsignacionGrupo, ValidacionAutorizacion) as e:
        st.warning(str(e))
        return False
    except Exception:
        st.error("No se pudo completar la operación. Intenta de nuevo.")
        return False
    st.session_state[_MSG] = mensaje_ok
    return True


def render(sesion=None) -> None:
    sesion = sesion or obtener_sesion()
    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    servicio = AsignacionGrupoService()
    permisos = sesion.get("permisos", [])
    actor = sesion.get("usuario") or "sistema"
    actor_id = sesion.get("id")
    es_admin = PERMISO_GESTIONAR in permisos

    try:
        gestionables = servicio.grupos_gestionables(permisos, actor_id)
        nombres = {g["clave"]: g["nombre"] for g in servicio.listar_grupos()}
    except Exception:
        st.error("No se pudieron cargar los grupos de trabajo.")
        st.stop()

    if not gestionables:
        st.error("No tienes permiso para gestionar grupos de trabajo.")
        st.stop()

    mostrar_titulo_decorado("Grupos de trabajo")
    st.caption(
        "Solo el administrador o el líder de un grupo asigna y retira a sus miembros. "
        "El retiro exige una razón y queda en el historial."
    )
    if msg := st.session_state.pop(_MSG, None):
        st.success(msg)

    clave = st.selectbox(
        "Grupo de trabajo", gestionables, format_func=lambda c: nombres.get(c, c), key="grupos_sel"
    )
    nombre_grupo = nombres.get(clave, clave)

    try:
        activos = servicio.miembros_detalle(clave, "activo")
    except Exception:
        st.error("No se pudieron cargar los miembros del grupo.")
        st.stop()

    st.subheader(f"Miembros activos de {nombre_grupo} ({len(activos)})")
    if activos:
        st.dataframe(
            pd.DataFrame([
                {
                    "Nombre": m["nombre"],
                    "Usuario": m["usuario"],
                    "Líder": "⭐ Sí" if m["es_lider"] else "—",
                    "Ingreso": formato_fecha_bogota(m["fecha_ingreso"], _FECHA),
                    "Razón de ingreso": m["razon_ingreso"] or "—",
                }
                for m in activos
            ]),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Este grupo no tiene miembros activos.")

    titulos = ["➕ Agregar miembro", "➖ Retirar miembro"]
    if es_admin:
        titulos.append("⭐ Líder del grupo")
    titulos.append("🕘 Historial de retiros")
    tabs = st.tabs(titulos)
    tab_agregar, tab_retirar = tabs[0], tabs[1]
    tab_lider = tabs[2] if es_admin else None
    tab_historial = tabs[-1]

    etiqueta_miembro = {m["usuario_id"]: f"{m['nombre']}{' ⭐' if m['es_lider'] else ''}" for m in activos}

    with tab_agregar:
        ids_miembros = set(etiqueta_miembro)
        candidatos = {
            uid: n for uid, n in usuarios_activos_para_seleccion().items() if uid not in ids_miembros
        }
        with st.form(f"form_agregar_{clave}", clear_on_submit=True):
            uid = st.selectbox(
                "Persona", list(candidatos), format_func=lambda i: candidatos[i],
                index=None, placeholder="Selecciona una persona",
            )
            razon = st.text_input("Razón de ingreso (opcional)", max_chars=200)
            enviar = st.form_submit_button("Agregar al grupo", type="primary")
        if enviar:
            if not uid:
                st.warning("Selecciona una persona.")
            elif _ejecutar(
                lambda: servicio.asignar(uid, clave, actor, permisos, razon, actor_id),
                f"{candidatos[uid]} fue agregado(a) a {nombre_grupo}.",
            ):
                st.rerun()

    with tab_retirar:
        if not activos:
            st.info("No hay miembros para retirar.")
        else:
            with st.form(f"form_retirar_{clave}", clear_on_submit=True):
                uid = st.selectbox(
                    "Miembro", list(etiqueta_miembro), format_func=lambda i: etiqueta_miembro[i],
                    index=None, placeholder="Selecciona un miembro",
                )
                razon = st.text_area("Razón del retiro (obligatoria)", max_chars=300)
                enviar = st.form_submit_button("Retirar del grupo", type="primary")
            if enviar:
                if not uid:
                    st.warning("Selecciona un miembro.")
                elif _ejecutar(
                    lambda: servicio.retirar(uid, clave, razon, actor, permisos, actor_id),
                    f"{etiqueta_miembro[uid]} fue retirado(a) de {nombre_grupo}.",
                ):
                    st.rerun()

    if tab_lider is not None:
        with tab_lider:
            st.caption(
                "El líder puede agregar y retirar miembros de este grupo. "
                "Solo el administrador designa líderes o retira a un líder."
            )
            if not activos:
                st.info("No hay miembros en el grupo.")
            else:
                uid = st.selectbox(
                    "Miembro", list(etiqueta_miembro), format_func=lambda i: etiqueta_miembro[i],
                    index=None, placeholder="Selecciona un miembro", key=f"lider_sel_{clave}",
                )
                if uid:
                    es_lider = next(m["es_lider"] for m in activos if m["usuario_id"] == uid)
                    etiqueta = "Quitar liderazgo" if es_lider else "Designar como líder"
                    if st.button(etiqueta, key=f"btn_lider_{clave}", type="primary"):
                        if _ejecutar(
                            lambda: servicio.definir_lider(uid, clave, not es_lider, actor, permisos),
                            "Liderazgo actualizado.",
                        ):
                            st.rerun()

    with tab_historial:
        retirados = servicio.miembros_detalle(clave, "retirado")
        if not retirados:
            st.info("Todavía no hay retiros registrados en este grupo.")
        else:
            st.dataframe(
                pd.DataFrame([
                    {
                        "Nombre": m["nombre"],
                        "Usuario": m["usuario"],
                        "Ingreso": formato_fecha_bogota(m["fecha_ingreso"], _FECHA),
                        "Retiro": formato_fecha_bogota(m["fecha_retiro"], _FECHA),
                        "Razón del retiro": m["razon_retiro"] or "—",
                        "Retirado por": m["retirado_por"] or "—",
                    }
                    for m in retirados
                ]),
                width="stretch",
                hide_index=True,
            )
