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

    def agregar_opcion(self, categoria: str, opcion: dict) -> bool:
        """Agrega una opción solo si su clave no existe ya (atómico). True si la agregó."""
        resultado = self.coleccion.update_one(
            {"categoria": categoria, "opciones.clave": {"$ne": opcion["clave"]}},
            {"$push": {"opciones": opcion}},
        )
        return resultado.modified_count == 1

    def cambiar_estado_opcion(self, categoria: str, clave: str, activo: bool) -> bool:
        """Activa/desactiva una opción existente. True si la encontró."""
        resultado = self.coleccion.update_one(
            {"categoria": categoria, "opciones.clave": clave},
            {"$set": {"opciones.$.activo": activo}},
        )
        return resultado.matched_count == 1


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


class ConfiguracionRepositorio:
    """Repositorio para documentos de configuración arbitraria en opciones_configuracion."""

    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("opciones_configuracion")

    def obtener(self, categoria: str) -> Optional[dict]:
        return self.coleccion.find_one({"categoria": categoria})

    def upsert(self, categoria: str, campos: dict) -> None:
        """Actualiza campos en un doc de configuración; lo crea si no existe."""
        self.coleccion.update_one(
            {"categoria": categoria},
            {"$set": campos},
            upsert=True,
        )
