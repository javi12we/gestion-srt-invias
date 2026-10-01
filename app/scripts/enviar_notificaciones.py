"""Envía el resumen diario de notificaciones por correo y termina.

No forma parte de la app Streamlit: se ejecuta una vez al día por fuera (ver
.github/workflows/notificaciones.yml y docs/notificaciones_correo.md).

Usage:
    python -m app.scripts.enviar_notificaciones                 # envía y registra
    python -m app.scripts.enviar_notificaciones --simular       # solo cuenta, no envía
    python -m app.scripts.enviar_notificaciones --simular --guardar-en vista_previa
    python -m app.scripts.enviar_notificaciones --prueba-a yo@ejemplo.com
    python -m app.scripts.enviar_notificaciones --limpiar       # limpieza semanal del registro
"""

import argparse
import os
import sys

from app.services.notificacion_service import MAX_CORREOS_DE_PRUEBA, NotificacionService


def _guardar_vistas_previas(servicio: NotificacionService, carpeta: str) -> int:
    """Escribe el HTML de cada resumen en `carpeta` (el logo embebido no se ve
    al abrir el archivo suelto: solo existe dentro del correo)."""
    os.makedirs(carpeta, exist_ok=True)
    resumenes = servicio.construir_resumenes()
    for indice, resumen in enumerate(resumenes, start=1):
        _, html, _ = servicio.renderizar(resumen)
        with open(os.path.join(carpeta, f"correo_{indice:03d}.html"), "w", encoding="utf-8") as archivo:
            archivo.write(html)
    return len(resumenes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resumen diario de notificaciones por correo (SRTI).")
    parser.add_argument("--simular", action="store_true", help="No envía ni registra nada; solo informa cuántos correos saldrían.")
    parser.add_argument("--guardar-en", metavar="CARPETA", help="Con --simular: guarda el HTML de cada correo en esa carpeta.")
    parser.add_argument(
        "--prueba-a", metavar="CORREO",
        help=f"Envía hasta {MAX_CORREOS_DE_PRUEBA} resúmenes reales a esta dirección, sin registrarlos como enviados.",
    )
    parser.add_argument(
        "--limpiar", action="store_true",
        help="No envía nada: borra de la base de datos las marcas de avisos ya enviados que no hacen falta.",
    )
    args = parser.parse_args()

    servicio = NotificacionService()

    if args.limpiar:
        borradas = servicio.limpiar_registro()
        print(f"[LIMPIEZA] {servicio.hoy.isoformat()} · marcas de avisos borradas: {borradas}")
        return 0

    if not args.simular and not servicio.correo.configurado():
        print("ERROR: falta configurar CORREO_REMITENTE y CORREO_PASSWORD_APP.")
        return 1

    if args.simular and args.guardar_en:
        total = _guardar_vistas_previas(servicio, args.guardar_en)
        print(f"Vistas previas guardadas: {total}")

    try:
        resultado = servicio.ejecutar(simular=args.simular, prueba_a=args.prueba_a)
    except Exception as e:
        print(f"ERROR: no se pudo completar el envío ({type(e).__name__}: {e}).")
        return 1

    # Solo totales: el registro de ejecución puede ser visible para terceros, así
    # que no se imprimen nombres ni direcciones de correo.
    modo = "SIMULACIÓN" if args.simular else ("PRUEBA" if args.prueba_a else "ENVÍO")
    print(f"[{modo}] {servicio.hoy.isoformat()}")
    print(f"Usuarios con algo que avisar: {resultado['usuarios_con_aviso']}")
    print(f"  con correspondencia vencida o por vencer: {resultado['correspondencia']}")
    print(f"  con aviso de apertura de formatos: {resultado['formatos']}")
    print(f"  con avance de firmas: {resultado['firmas']}")
    print(f"Correos enviados: {resultado['enviados']} · fallidos: {resultado['fallidos']}")
    if resultado["errores"]:
        print("Tipos de error: " + ", ".join(sorted(set(resultado["errores"]))))
    return 1 if resultado["fallidos"] else 0


if __name__ == "__main__":
    sys.exit(main())
