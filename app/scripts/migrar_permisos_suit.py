"""Migra las claves suit.ver_* de usuarios.permisos_extra a la colección suit_asignaciones.

Por defecto SOLO SIMULA (no escribe). Usa --aplicar para crear las asignaciones.
Es idempotente y no modifica la colección 'usuarios'.

Usage:
    python -m app.scripts.migrar_permisos_suit            # simulación
    python -m app.scripts.migrar_permisos_suit --aplicar  # escribe
"""

import argparse

from app.db.mongo import obtener_base_datos
from app.services.suit_service import SuitService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aplicar", action="store_true", help="Escribe en la BD (por defecto solo simula)")
    args = parser.parse_args()

    print(f"Base de datos: {obtener_base_datos().name}")
    resumen = SuitService().migrar_desde_permisos_extra(simular=not args.aplicar)
    print("MODO:", "APLICAR" if args.aplicar else "SIMULACION (no se escribió nada)")
    print(f" - A crear:     {resumen['a_crear']}")
    print(f" - Creadas:     {resumen['creadas']}")
    print(f" - Ya existían: {resumen['ya_existian']}")


if __name__ == "__main__":
    main()
