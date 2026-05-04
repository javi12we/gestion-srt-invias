"""Lógica de autorización y validación de permisos."""


class ValidacionAutorizacion(Exception):
    """Excepción lanzada cuando falla validación de autorización."""

    pass


def validar_permiso(permisos_usuario: list[str], permiso_requerido: str) -> None:
    """Valida que el usuario tiene un permiso específico.
    
    Args:
        permisos_usuario: lista de permisos del usuario
        permiso_requerido: permiso necesario para la operación
        
    Raises:
        ValidacionAutorizacion: si el usuario no tiene el permiso
    """
    if permiso_requerido not in permisos_usuario:
        raise ValidacionAutorizacion(f"Permiso requerido: {permiso_requerido}")


def validar_alguno(permisos_usuario: list[str], permisos_requeridos: list[str]) -> None:
    """Valida que el usuario tiene al menos uno de los permisos requeridos.
    
    Args:
        permisos_usuario: lista de permisos del usuario
        permisos_requeridos: lista de permisos, se requiere al menos uno
        
    Raises:
        ValidacionAutorizacion: si el usuario no tiene ninguno de los permisos
    """
    if not any(p in permisos_usuario for p in permisos_requeridos):
        raise ValidacionAutorizacion(f"Se requiere al menos uno de estos permisos: {permisos_requeridos}")
