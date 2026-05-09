from typing import Dict, List

from app.repositories.opciones_repo import (
    OpcionesRepositorio,
    obtener_opciones_activas,
    limpiar_cache_opciones,
)


class OpcionesService:
    """
    Servicio para gestionar opciones de configuración con caché.
    
    Ejemplo de uso:
        service = OpcionesService()
        estados = service.obtener_opciones("estados")
        tipos = service.obtener_opciones("tipo")
    """

    def __init__(self) -> None:
        self.repo = OpcionesRepositorio()

    def obtener_opciones(self, categoria: str) -> List[Dict]:
        """
        Obtiene las opciones activas de una categoría con caché.
        
        Args:
            categoria: Una de "tipo", "grupo", "clase_correspondencia", "estados"
        
        Returns:
            Lista de diccionarios con: clave, etiqueta, activo
        """
        return obtener_opciones_activas(categoria)

    def obtener_todos_los_catalogos(self) -> Dict[str, List[Dict]]:
        """
        Obtiene todos los catálogos de opciones.
        
        Returns:
            Diccionario con categorías como claves y listas de opciones como valores
        """
        categorias = ["tipo", "grupo", "clase_correspondencia", "estados"]
        resultado = {}
        for categoria in categorias:
            resultado[categoria] = self.obtener_opciones(categoria)
        return resultado

    def obtener_opciones_para_formulario(self, categoria: str) -> List[Dict]:
        """
        Obtiene opciones formateadas para uso en componentes de formulario.
        
        Retorna lista compatible con componentes como selectbox de Streamlit.
        
        Args:
            categoria: Una de "tipo", "grupo", "clase_correspondencia", "estados"
        
        Returns:
            Lista de diccionarios con claves compatibles con UI
        """
        opciones = self.obtener_opciones(categoria)
        return [{"label": opt["etiqueta"], "value": opt["clave"]} for opt in opciones]

    def obtener_etiqueta_por_clave(self, categoria: str, clave: str) -> str:
        """
        Obtiene la etiqueta de una opción usando su clave.
        
        Args:
            categoria: La categoría de opciones
            clave: La clave de la opción
        
        Returns:
            La etiqueta correspondiente o la clave si no se encuentra
        """
        opciones = self.obtener_opciones(categoria)
        for opt in opciones:
            if opt["clave"] == clave:
                return opt["etiqueta"]
        return clave

    def limpiar_cache(self) -> None:
        """Limpia el caché de opciones. Útil después de actualizaciones."""
        limpiar_cache_opciones()
