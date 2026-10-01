from app.core.catalogos import PERMISOS_BASE, ROLES_BASE


def test_permiso_pago_cargar_existe():
    claves = {p["clave"] for p in PERMISOS_BASE}
    assert "pago.cargar" in claves


def test_solo_admin_tiene_pago_cargar_por_defecto():
    admin = next(r for r in ROLES_BASE if r["nombre"] == "admin")
    assert "pago.cargar" in admin["permisos"]

    otros_roles = [r for r in ROLES_BASE if r["nombre"] != "admin"]
    for rol in otros_roles:
        assert "pago.cargar" not in rol["permisos"], f"El rol {rol['nombre']} no debería tener pago.cargar por defecto"
