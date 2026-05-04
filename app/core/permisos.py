def tiene_permiso(permisos_usuario: list[str], permiso_requerido: str) -> bool:
    return permiso_requerido in permisos_usuario


def tiene_alguno(permisos_usuario: list[str], permisos_requeridos: list[str]) -> bool:
    return any(permiso in permisos_usuario for permiso in permisos_requeridos)
