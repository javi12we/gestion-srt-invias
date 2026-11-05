"""Gestión del catálogo de bancos (categoría 'banco' de opciones_configuracion).

Los bancos se agregan desde Parámetros. El usuario guarda la *clave* (slug) del banco;
la etiqueta visible se escribe en MAYÚSCULAS como el resto del catálogo.
"""

import re

from app.repositories.opciones_repo import OpcionesRepositorio, limpiar_cache_opciones
from app.repositories.usuario_repo import UsuarioRepositorio
from app.services.auditoria_service import AuditoriaService
from app.services.catalogo_service import _slug

CATEGORIA = "banco"
MIN_LONGITUD = 3
MAX_LONGITUD = 80


class BancosService:
    def __init__(self, repo=None, usuarios=None, auditoria=None) -> None:
        self.repo = repo or OpcionesRepositorio()
        self.usuarios = usuarios or UsuarioRepositorio()
        self.auditoria = auditoria or AuditoriaService()

    def listar(self) -> list[dict]:
        """Todos los bancos (activos e inactivos), ordenados por nombre."""
        doc = self.repo.obtener_por_categoria(CATEGORIA)
        opciones = (doc or {}).get("opciones") or []
        return sorted(opciones, key=lambda o: o.get("etiqueta", ""))

    def agregar(self, nombre: str, usuario: str = "sistema") -> dict:
        """Agrega un banco nuevo. Lanza ValueError si es inválido o ya existe."""
        etiqueta = re.sub(r"\s+", " ", (nombre or "").strip()).upper()
        if len(etiqueta) < MIN_LONGITUD:
            raise ValueError(f"El nombre del banco debe tener al menos {MIN_LONGITUD} caracteres.")
        if len(etiqueta) > MAX_LONGITUD:
            raise ValueError(f"El nombre del banco no puede superar {MAX_LONGITUD} caracteres.")
        clave = _slug(etiqueta)
        if not clave:
            raise ValueError("El nombre del banco debe contener letras o números.")

        if self.repo.obtener_por_categoria(CATEGORIA) is None:
            raise ValueError("El catálogo de bancos no está inicializado. Ejecuta init_db.")

        existente = next((o for o in self.listar() if o.get("clave") == clave), None)
        if existente:
            estado = "" if existente.get("activo") else " (está desactivado: reactívalo en la lista)"
            raise ValueError(f"Ese banco ya existe: {existente['etiqueta']}{estado}.")

        opcion = {"clave": clave, "etiqueta": etiqueta, "activo": True}
        if not self.repo.agregar_opcion(CATEGORIA, opcion):
            raise ValueError("Ese banco ya existe.")
        self.auditoria.registrar_accion(usuario, "crear", "banco", {"clave": clave, "etiqueta": etiqueta})
        limpiar_cache_opciones()
        return opcion

    def contar_usuarios(self, clave: str) -> int:
        """Cuántos usuarios tienen este banco guardado."""
        return self.usuarios.contar_por_banco(clave)

    def cambiar_estado(self, clave: str, activo: bool, usuario: str = "sistema") -> None:
        """Activa o desactiva un banco. Lanza ValueError si no existe."""
        if not self.repo.cambiar_estado_opcion(CATEGORIA, clave, bool(activo)):
            raise ValueError("El banco no existe.")
        self.auditoria.registrar_accion(
            usuario, "activar" if activo else "desactivar", "banco", {"clave": clave}
        )
        limpiar_cache_opciones()
