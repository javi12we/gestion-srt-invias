from functools import lru_cache
from typing import Optional

from app.db.mongo import obtener_coleccion


class OpcionesRepositorio:
    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("opciones_configuracion")

    def obtener_por_categoria(self, categoria: str) -> Optional[dict]:
        """Obtiene las opciones de una categoría específica."""
        return self.coleccion.find_one({"categoria": categoria})

    def obtener_todas(self) -> list:
        """Obtiene todas las categorías de opciones."""
        return list(self.coleccion.find())

    def obtener_opciones_activas(self, categoria: str) -> list:
        """Obtiene solo las opciones activas de una categoría."""
        resultado = self.obtener_por_categoria(categoria)
        if resultado:
            return [opt for opt in resultado.get("opciones", []) if opt.get("activo", False)]
        return []


# Función con caché para consultas frecuentes
@lru_cache(maxsize=128)
def obtener_opciones_cache(categoria: str) -> tuple:
    """
    Obtiene las opciones de una categoría con caché.
    
    Args:
        categoria: La categoría de opciones (tipo, grupo, clase_correspondencia, estados)
    
    Returns:
        Tupla con las opciones (inmutable para el caché)
    
    Ejemplo:
        opciones = obtener_opciones_cache("estados")
        for opcion in opciones:
            print(opcion["etiqueta"])
    """
    repo = OpcionesRepositorio()
    opciones = repo.obtener_opciones_activas(categoria)
    # Convertir a tupla para que sea hashable y cacheable
    return tuple(opciones) if opciones else ()


def obtener_opciones_activas(categoria: str) -> list:
    """
    Wrapper que retorna una lista en lugar de tupla.
    Usa caché internamente.
    """
    return list(obtener_opciones_cache(categoria))


def limpiar_cache_opciones():
    """Limpia el caché de opciones."""
    obtener_opciones_cache.cache_clear()
