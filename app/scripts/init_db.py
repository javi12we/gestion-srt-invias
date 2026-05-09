"""Script de inicialización de la base de datos Mongo.

Ejecuta:
- aseguramiento de colecciones e índices (MongoBootstrapService)
- inserción de roles y permisos base (CatalogoService)
- creación del admin inicial si ADMIN_INICIAL_PASSWORD está definido

Usage:
    python -m app.scripts.init_db
"""

from app.services.mongo_bootstrap_service import MongoBootstrapService
from app.services.catalogo_service import CatalogoService
from app.services.usuario_service import UsuarioService
from app.db.mongo import obtener_base_datos


def main():
    print("Arrancando bootstrap de MongoDB...")
    mb = MongoBootstrapService()
    mb.asegurar_estructura()
    print("Estructura y validadores asegurados.")

    cs = CatalogoService()
    cs.asegurar_catalogos_base()
    print("Catálogos base asegurados (roles y permisos).")

    us = UsuarioService()
    resultado = us.asegurar_usuario_admin_inicial()
    if resultado:
        print(f"Usuario admin creado con id: {resultado}")
    else:
        print("Usuario admin ya existente o ADMIN_INICIAL_PASSWORD no definido.")

    # Resumen de conteos
    db = obtener_base_datos()
    print("Conteos por colección:")
    for nombre in ["usuarios", "roles", "permisos", "sesiones", "opciones_configuracion"]:
        try:
            print(f" - {nombre}: {db[nombre].count_documents({})}")
        except Exception as e:
            print(f" - {nombre}: error al contar -> {e}")


if __name__ == "__main__":
    main()
