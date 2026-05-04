from functools import lru_cache

from pymongo import MongoClient

from app.config import configuracion


@lru_cache(maxsize=1)
def obtener_cliente() -> MongoClient:
    return MongoClient(configuracion.mongodb_uri)


def obtener_base_datos():
    return obtener_cliente()[configuracion.mongodb_db]


def obtener_coleccion(nombre: str):
    return obtener_base_datos()[nombre]
