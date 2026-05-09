"""
Ejemplo de cómo usar el servicio de opciones de configuración en Streamlit.

Este archivo muestra patrones comunes para trabajar con los desplegables
de opciones centralizadas.
"""

import streamlit as st
from app.services.opciones_service import OpcionesService


def ejemplo_basico():
    """Ejemplo básico de uso del servicio de opciones."""
    service = OpcionesService()
    
    # Obtener opciones de una categoría
    estados = service.obtener_opciones("estados")
    
    # Mostrar como selectbox
    claves = [opt["clave"] for opt in estados]
    etiquetas = [opt["etiqueta"] for opt in estados]
    
    estado_seleccionado = st.selectbox(
        "Selecciona un estado",
        options=claves,
        format_func=lambda x: service.obtener_etiqueta_por_clave("estados", x)
    )
    
    st.write(f"Seleccionaste: {estado_seleccionado}")


def ejemplo_multiples_selectores():
    """Ejemplo con múltiples selectores."""
    service = OpcionesService()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        tipo = st.selectbox(
            "Tipo de correspondencia",
            service.obtener_opciones_para_formulario("tipo"),
            format_func=lambda x: x.get("label", "")
        )
    
    with col2:
        grupo = st.selectbox(
            "Grupo",
            service.obtener_opciones_para_formulario("grupo"),
            format_func=lambda x: x.get("label", "")
        )
    
    with col3:
        clase = st.selectbox(
            "Clase",
            service.obtener_opciones_para_formulario("clase_correspondencia"),
            format_func=lambda x: x.get("label", "")
        )


def ejemplo_todos_catalogos():
    """Muestra todos los catálogos disponibles."""
    service = OpcionesService()
    
    st.subheader("📚 Catálogos de Opciones")
    
    catalogos = service.obtener_todos_los_catalogos()
    
    for categoria, opciones in catalogos.items():
        with st.expander(f"**{categoria.upper()}** ({len(opciones)} opciones)"):
            for opt in opciones:
                status = "✅" if opt.get("activo") else "❌"
                st.write(f"{status} **{opt['etiqueta']}** (`{opt['clave']}`)")


def ejemplo_conversión_clave_etiqueta():
    """Ejemplo de convertir entre clave y etiqueta."""
    service = OpcionesService()
    
    # Tienes una clave y necesitas la etiqueta
    clave_estado = "en_tramite"
    etiqueta = service.obtener_etiqueta_por_clave("estados", clave_estado)
    
    st.write(f"Clave: {clave_estado} → Etiqueta: {etiqueta}")


if __name__ == "__main__":
    st.set_page_config(page_title="Ejemplo - Opciones de Configuración")
    
    st.title("📋 Ejemplo: Opciones de Configuración")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "Básico",
        "Múltiples",
        "Todos",
        "Conversión"
    ])
    
    with tab1:
        ejemplo_basico()
    
    with tab2:
        ejemplo_multiples_selectores()
    
    with tab3:
        ejemplo_todos_catalogos()
    
    with tab4:
        ejemplo_conversión_clave_etiqueta()
