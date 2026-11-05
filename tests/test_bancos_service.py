import pytest

from app.services.bancos_service import BancosService


class FakeRepo:
    def __init__(self, con_categoria=True):
        self.doc = {"categoria": "banco", "opciones": [
            {"clave": "bancolombia", "etiqueta": "BANCOLOMBIA", "activo": True},
            {"clave": "banco_union", "etiqueta": "BANCO UNIÓN", "activo": False},
        ]} if con_categoria else None

    def obtener_por_categoria(self, categoria):
        return self.doc

    def agregar_opcion(self, categoria, opcion):
        if any(o["clave"] == opcion["clave"] for o in self.doc["opciones"]):
            return False
        self.doc["opciones"].append(opcion)
        return True

    def cambiar_estado_opcion(self, categoria, clave, activo):
        for o in self.doc["opciones"]:
            if o["clave"] == clave:
                o["activo"] = activo
                return True
        return False


class FakeUsuarios:
    def contar_por_banco(self, clave):
        return 3 if clave == "bancolombia" else 0


class FakeAuditoria:
    def __init__(self):
        self.registros = []

    def registrar_accion(self, usuario, accion, recurso, detalle=None, exito=True):
        self.registros.append((usuario, accion, recurso, detalle))


def crear(con_categoria=True):
    aud = FakeAuditoria()
    return BancosService(FakeRepo(con_categoria), FakeUsuarios(), aud), aud


def test_agregar_normaliza_a_mayusculas_y_genera_clave():
    svc, aud = crear()
    op = svc.agregar("  banco   nuevo ñandú ", "admin")
    assert op == {"clave": "banco_nuevo_nandu", "etiqueta": "BANCO NUEVO ÑANDÚ", "activo": True}
    assert aud.registros[0][:3] == ("admin", "crear", "banco")
    assert any(b["clave"] == "banco_nuevo_nandu" for b in svc.listar())


def test_agregar_duplicado_aunque_difiera_en_tildes_o_mayusculas():
    svc, _ = crear()
    with pytest.raises(ValueError, match="ya existe"):
        svc.agregar("bancolombia")
    with pytest.raises(ValueError, match="desactivado"):
        svc.agregar("Banco Unión")


@pytest.mark.parametrize("nombre", ["", "  ", "ab", "x" * 81, "***"])
def test_agregar_rechaza_nombres_invalidos(nombre):
    svc, _ = crear()
    with pytest.raises(ValueError):
        svc.agregar(nombre)


def test_agregar_sin_catalogo_inicializado():
    svc, _ = crear(con_categoria=False)
    with pytest.raises(ValueError, match="init_db"):
        svc.agregar("Banco Nuevo")


def test_cambiar_estado_y_auditoria():
    svc, aud = crear()
    svc.cambiar_estado("bancolombia", False, "admin")
    assert next(b for b in svc.listar() if b["clave"] == "bancolombia")["activo"] is False
    svc.cambiar_estado("bancolombia", True, "admin")
    assert [r[1] for r in aud.registros] == ["desactivar", "activar"]
    with pytest.raises(ValueError, match="no existe"):
        svc.cambiar_estado("inexistente", True)


def test_contar_usuarios():
    svc, _ = crear()
    assert svc.contar_usuarios("bancolombia") == 3
    assert svc.contar_usuarios("banco_union") == 0
