"""Caché de lecturas frecuentes para las páginas Streamlit.

Única capa donde se permite mezclar st.cache_data con servicios.
Las páginas consumen estas funciones en lugar de llamar servicios
directamente para datos de solo lectura que cambian poco.
"""

from typing import Optional

import streamlit as st


@st.cache_data(ttl=60, show_spinner=False)
def usuarios_activos_para_seleccion() -> dict:
    """Mapa str(id) -> nombre visible, solo usuarios activos, orden alfabético."""
    from app.services.usuario_service import UsuarioService

    usuarios = UsuarioService().listar_usuarios()
    activos = [u for u in usuarios if u.get("activo", True)]
    activos.sort(key=lambda u: (u.get("nombre_completo") or u.get("usuario", "")).lower())
    return {
        str(u["_id"]): u.get("nombre_completo") or u["usuario"]
        for u in activos
    }


@st.cache_data(ttl=60, show_spinner=False)
def admins_activos_para_seleccion() -> dict:
    """Mapa str(id) -> nombre visible, solo usuarios activos con rol admin."""
    from app.services.usuario_service import UsuarioService

    usuarios = UsuarioService().listar_usuarios()
    return {
        str(u["_id"]): u.get("nombre_completo") or u["usuario"]
        for u in usuarios
        if u.get("activo", True) and "admin" in u.get("roles", [])
    }


@st.cache_data(ttl=300, show_spinner=False)
def opciones_activas(categoria: str) -> list:
    """Opciones activas de un catálogo (lista de dicts con clave/etiqueta)."""
    from app.services.opciones_service import OpcionesService

    return OpcionesService().obtener_opciones(categoria)


@st.cache_data(ttl=300, show_spinner=False)
def parametro_admin(clave: str):
    """Valor de un parámetro configurable de admin (ParametrosService).

    Se consulta muy seguido desde puntos que antes hacían un find_one a Mongo
    por llamada (ej. `periodo_certificable()`, invocado varias veces por
    colaborador al listar empleados certificables, o `firma_extra_activa()`,
    invocado varias veces por render de página)."""
    from app.services.parametros_service import ParametrosService

    return ParametrosService().obtener(clave)


@st.cache_data(ttl=60, show_spinner=False)
def metricas_inicio(id_usuario: Optional[str]) -> dict:
    """Métricas del panel de inicio (pendientes/urgentes/recientes)."""
    from app.services.correspondencia_service import CorrespondenciaService

    return CorrespondenciaService().obtener_metricas_dashboard(id_usuario=id_usuario)


@st.cache_data(ttl=60, show_spinner=False)
def datos_dashboard_admin(
    usuario_id: Optional[str],
    tipo_id: Optional[str] = None,
    estado_id: Optional[str] = None,
) -> dict:
    """Todas las consultas del dashboard admin en una sola entrada de caché."""
    from app.services.reporte_service import ReporteService

    svc = ReporteService()
    return {
        "resumen": svc.resumen_operativo(usuario_id=usuario_id, tipo=tipo_id, estado=estado_id),
        "dist_estado": svc.distribucion_por_estado(usuario_id=usuario_id, tipo=tipo_id, estado=estado_id),
        "carga_usuarios": svc.carga_por_usuario(usuario_id=usuario_id, tipo=tipo_id, estado=estado_id),
        "vencimientos": svc.analisis_vencimiento(usuario_id=usuario_id, tipo=tipo_id, estado=estado_id),
        "tendencia_d": svc.tendencia_diaria(dias=30, usuario_id=usuario_id, tipo=tipo_id, estado=estado_id),
        "tiempos_resp": svc.analisis_tiempos_respuesta(usuario_id=usuario_id, tipo=tipo_id, estado=estado_id),
        "conteo_tipo": svc.conteo_por_tipo(usuario_id=usuario_id, tipo=tipo_id, estado=estado_id),
        "tendencia_m": svc.tendencia_mensual(meses=6, usuario_id=usuario_id, tipo=tipo_id, estado=estado_id),
        "por_dia_semana": svc.radicacion_por_dia_semana(usuario_id=usuario_id, tipo=tipo_id, estado=estado_id),
        "vencidos_resp": svc.vencidos_por_responsable(usuario_id=usuario_id, tipo=tipo_id, estado=estado_id),
    }


@st.cache_data(ttl=60, show_spinner=False)
def seguimiento_suit(anio: int, actor_id: Optional[str], permisos: tuple) -> dict:
    """Seguimiento SUIT del año (cumplimiento, indicadores, responsables). Valida acceso en el servicio."""
    from app.services.suit_service import SuitService

    return SuitService().seguimiento(anio, actor_id, list(permisos))


@st.cache_data(ttl=60, show_spinner=False)
def empleados_para_certificar(tipo_formato: Optional[str], año: int, mes: int) -> list:
    """Colaboradores con estado de firmas/contrato para 'Sup. Formatos' (panel de
    control y panel de actas). Internamente ya combina el estado de correspondencia,
    el listado completo de usuarios y las certificaciones del período."""
    from app.services.certificacion_service import CertificacionService

    return CertificacionService().obtener_empleados_para_certificar(
        tipo_formato=tipo_formato, año=año, mes=mes
    )


@st.cache_data(ttl=60, show_spinner=False)
def periodos_disponibles_global() -> list:
    """Períodos (año, mes) seleccionables en 'Sup. Formatos'."""
    from app.services.certificacion_service import CertificacionService

    return CertificacionService().periodos_disponibles_global()


@st.cache_data(ttl=60, show_spinner=False)
def periodos_disponibles_usuario(usuario_id: str) -> list:
    """Períodos (año, mes) seleccionables por un contratista en 'Formatos de contrato'."""
    from app.services.certificacion_service import CertificacionService

    return CertificacionService().periodos_disponibles_usuario(usuario_id)


def limpiar_cache_lecturas() -> None:
    """Limpia todo el caché de lecturas. Llamar tras escrituras y en botones Actualizar."""
    usuarios_activos_para_seleccion.clear()
    admins_activos_para_seleccion.clear()
    opciones_activas.clear()
    metricas_inicio.clear()
    datos_dashboard_admin.clear()
    seguimiento_suit.clear()
    empleados_para_certificar.clear()
    periodos_disponibles_global.clear()
    periodos_disponibles_usuario.clear()
    parametro_admin.clear()

    from app.repositories.opciones_repo import limpiar_cache_opciones

    limpiar_cache_opciones()
