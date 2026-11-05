"""Migra usuarios.informacion_laboral.grupo_trabajo a la colección asignaciones_grupo.

Por defecto SOLO SIMULA (no escribe). Usa --aplicar para crear las asignaciones.
Es idempotente y no modifica la colección 'usuarios'.

Usage:
    python -m app.scripts.migrar_grupos_usuarios            # simulación
    python -m app.scripts.migrar_grupos_usuarios --aplicar  # escribe
"""

import argparse

from app.db.mongo import obtener_base_datos
from app.services.asignacion_grupo_service import AsignacionGrupoService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aplicar", action="store_true", help="Escribe en la BD (por defecto solo simula)")
    args = parser.parse_args()

    print(f"Base de datos: {obtener_base_datos().name}")
    resumen = AsignacionGrupoService().migrar_desde_usuarios(simular=not args.aplicar)
    print("MODO:", "APLICAR" if args.aplicar else "SIMULACION (no se escribió nada)")
    print(f" - A crear:     {resumen['a_crear']}")
    print(f" - Creadas:     {resumen['creadas']}")
    print(f" - Ya existían: {resumen['ya_existian']}")
    print(f" - De usuarios inactivos (incluidos): {resumen['inactivos']}")
    for grupo, n in sorted(resumen["por_grupo"].items()):
        print(f"   · {grupo}: {n}")


if __name__ == "__main__":
    main()
