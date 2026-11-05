from bson import ObjectId
import pytest
from pymongo.errors import DuplicateKeyError

from app.core.autorizacion import ValidacionAutorizacion
from app.services.asignacion_grupo_service import AsignacionGrupoService, ErrorAsignacionGrupo

ADMIN = ["grupo.gestionar_miembros"]
UID = ObjectId()
LIDER = ObjectId()
OTRO = ObjectId()


class FakeAsignaciones:
    def __init__(self):
        self.docs = []

    def obtener_activa(self, usuario_id, grupo_clave):
        return next((d for d in self.docs if str(d["usuario_id"]) == str(usuario_id)
                     and d["grupo_clave"] == grupo_clave and d["estado"] == "activo"), None)

    def insertar(self, doc):
        if doc["estado"] == "activo" and self.obtener_activa(doc["usuario_id"], doc["grupo_clave"]):
            raise DuplicateKeyError("dup")
        doc = {**doc, "_id": ObjectId()}
        self.docs.append(doc)
        return doc["_id"]

    def retirar(self, asignacion_id, cambios, entrada):
        for d in self.docs:
            if d["_id"] == asignacion_id and d["estado"] == "activo":
                d.update(cambios)
                d["trazabilidad"].append(entrada)
                return True
        return False

    def definir_lider(self, asignacion_id, es_lider, entrada):
        for d in self.docs:
            if d["_id"] == asignacion_id and d["estado"] == "activo":
                d["es_lider"] = es_lider
                d["trazabilidad"].append(entrada)
                return True
        return False

    def listar_por_grupo(self, grupo_clave, estado=None):
        return [d for d in self.docs if d["grupo_clave"] == grupo_clave and (not estado or d["estado"] == estado)]

    def listar_por_usuario(self, usuario_id, solo_activas=False):
        return [d for d in self.docs if str(d["usuario_id"]) == str(usuario_id)
                and (not solo_activas or d["estado"] == "activo")]

    def listar_activas(self):
        return [d for d in self.docs if d["estado"] == "activo"]


class FakeGrupos:
    def __init__(self, activo=True):
        self.activo = activo

    def obtener_por_clave(self, clave):
        return {"clave": clave, "nombre": clave.upper(), "activo": self.activo} if clave in ("permisos", "despacho") else None

    def listar(self, solo_activos=False):
        return [{"clave": c, "nombre": c.upper(), "activo": self.activo} for c in ("despacho", "permisos")]


class FakeUsuarios:
    def __init__(self, activo=True):
        self.activo = activo
        self.todos = {i: {"_id": i, "nombre_completo": n, "usuario": n.lower(), "activo": activo}
                      for i, n in ((UID, "Ana"), (LIDER, "Luis"), (OTRO, "Zoe"))}

    def buscar_por_id(self, usuario_id):
        return self.todos.get(ObjectId(usuario_id))

    def listar_por_ids(self, ids):
        return [self.todos[i] for i in ids if i in self.todos]

    def listar_por_grupo_trabajo(self, grupo):
        return [self.todos[UID]] if grupo == "permisos" else []


def crear(usuario_activo=True, grupo_activo=True):
    asig = FakeAsignaciones()
    return AsignacionGrupoService(asig, FakeGrupos(grupo_activo), FakeUsuarios(usuario_activo)), asig


def con_lider(grupo="permisos"):
    """Servicio con LIDER ya designado líder activo del grupo."""
    svc, asig = crear()
    svc.asignar(str(LIDER), grupo, "admin", ADMIN)
    svc.definir_lider(str(LIDER), grupo, True, "admin", ADMIN)
    return svc, asig


# ── Administrador ────────────────────────────────────────────────────────────
def test_admin_asigna_con_trazabilidad_y_sin_liderazgo():
    svc, asig = crear()
    svc.asignar(str(UID), "permisos", "admin", ADMIN, "Ingreso al equipo")
    doc = asig.docs[0]
    assert doc["estado"] == "activo" and doc["es_lider"] is False
    assert doc["trazabilidad"][0]["accion"] == "asignado"


def test_sin_permiso_ni_liderazgo_no_puede_asignar():
    svc, _ = crear()
    with pytest.raises(ValidacionAutorizacion):
        svc.asignar(str(UID), "permisos", "x", [], actor_id=str(OTRO))


def test_validaciones_de_negocio():
    svc, _ = crear()
    svc.asignar(str(UID), "permisos", "admin", ADMIN)
    with pytest.raises(ErrorAsignacionGrupo, match="ya pertenece"):
        svc.asignar(str(UID), "permisos", "admin", ADMIN)
    with pytest.raises(ErrorAsignacionGrupo, match="inactivo"):
        crear(usuario_activo=False)[0].asignar(str(UID), "permisos", "a", ADMIN)
    with pytest.raises(ErrorAsignacionGrupo, match="no existe"):
        crear()[0].asignar(str(UID), "otro", "a", ADMIN)
    with pytest.raises(ErrorAsignacionGrupo, match="inactivo"):
        crear(grupo_activo=False)[0].asignar(str(UID), "permisos", "a", ADMIN)
    with pytest.raises(ErrorAsignacionGrupo, match="inválido"):
        crear()[0].asignar("no-es-id", "permisos", "a", ADMIN)


def test_retirar_exige_razon_y_guarda_historial_y_reingreso():
    svc, asig = crear()
    svc.asignar(str(UID), "permisos", "admin", ADMIN)
    with pytest.raises(ErrorAsignacionGrupo, match="razón"):
        svc.retirar(str(UID), "permisos", "ab", "admin", ADMIN)
    svc.retirar(str(UID), "permisos", "Fin de contrato", "admin", ADMIN)
    doc = asig.docs[0]
    assert doc["estado"] == "retirado" and doc["razon_retiro"] == "Fin de contrato"
    assert [t["accion"] for t in doc["trazabilidad"]] == ["asignado", "retirado"]
    with pytest.raises(ErrorAsignacionGrupo, match="no pertenece"):
        svc.retirar(str(UID), "permisos", "Fin de contrato", "admin", ADMIN)
    svc.asignar(str(UID), "permisos", "admin", ADMIN)
    assert [d["estado"] for d in asig.docs] == ["retirado", "activo"]


# ── Líder ────────────────────────────────────────────────────────────────────
def test_solo_admin_designa_lider():
    svc, asig = crear()
    svc.asignar(str(LIDER), "permisos", "admin", ADMIN)
    with pytest.raises(ValidacionAutorizacion):
        svc.definir_lider(str(LIDER), "permisos", True, "x", [])
    svc.definir_lider(str(LIDER), "permisos", True, "admin", ADMIN)
    assert asig.docs[0]["es_lider"] is True
    assert asig.docs[0]["trazabilidad"][-1]["accion"] == "lider_definido"
    svc.definir_lider(str(LIDER), "permisos", False, "admin", ADMIN)
    assert asig.docs[0]["es_lider"] is False


def test_lider_asigna_y_retira_en_su_grupo():
    svc, asig = con_lider("permisos")
    svc.asignar(str(UID), "permisos", "luis", [], actor_id=str(LIDER))
    assert asig.obtener_activa(UID, "permisos") is not None
    svc.retirar(str(UID), "permisos", "Cambio de funciones", "luis", [], actor_id=str(LIDER))
    assert asig.obtener_activa(UID, "permisos") is None


def test_lider_no_gestiona_otro_grupo():
    svc, _ = con_lider("permisos")
    with pytest.raises(ValidacionAutorizacion):
        svc.asignar(str(UID), "despacho", "luis", [], actor_id=str(LIDER))


def test_miembro_no_lider_no_gestiona():
    svc, _ = crear()
    svc.asignar(str(OTRO), "permisos", "admin", ADMIN)
    with pytest.raises(ValidacionAutorizacion):
        svc.asignar(str(UID), "permisos", "zoe", [], actor_id=str(OTRO))


def test_lider_no_puede_retirar_a_un_lider():
    svc, _ = con_lider("permisos")
    with pytest.raises(ErrorAsignacionGrupo, match="administrador"):
        svc.retirar(str(LIDER), "permisos", "Razón válida", "luis", [], actor_id=str(LIDER))
    svc.retirar(str(LIDER), "permisos", "Razón válida", "admin", ADMIN)


def test_grupos_gestionables():
    svc, _ = con_lider("permisos")
    assert svc.grupos_gestionables(ADMIN, None) == ["despacho", "permisos"]
    assert svc.grupos_gestionables([], str(LIDER)) == ["permisos"]
    assert svc.grupos_gestionables([], str(OTRO)) == []
    assert svc.grupos_gestionables([], None) == []


# ── Consulta / sesión / migración ────────────────────────────────────────────
def test_claves_de_usuario_para_la_sesion():
    svc, _ = con_lider("permisos")
    svc.asignar(str(LIDER), "despacho", "admin", ADMIN)
    r = svc.claves_de_usuario(str(LIDER))
    assert sorted(r["grupos"]) == ["despacho", "permisos"] and r["lider"] == ["permisos"]
    assert svc.nombres_grupos_texto(str(OTRO)) == "Sin grupo asignado"
    assert "PERMISOS" in svc.nombres_grupos_texto(str(LIDER))


def test_miembros_detalle_y_mapa():
    svc, _ = con_lider("permisos")
    svc.asignar(str(UID), "permisos", "admin", ADMIN)
    detalle = svc.miembros_detalle("permisos")
    assert [d["nombre"] for d in detalle] == ["Luis", "Ana"]  # el líder primero
    assert detalle[0]["es_lider"] is True
    assert {u["_id"] for u in svc.usuarios_de_grupo("permisos")} == {UID, LIDER}
    assert set(svc.mapa_grupos_activos()) == {str(UID), str(LIDER)}


def test_migracion_simula_aplica_y_es_idempotente():
    svc, asig = crear()
    r = svc.migrar_desde_usuarios(simular=True)
    assert r["a_crear"] == 1 and asig.docs == []
    r = svc.migrar_desde_usuarios(simular=False)
    assert r["creadas"] == 1 and asig.docs[0]["asignado_por"] == "migracion" and asig.docs[0]["es_lider"] is False
    r = svc.migrar_desde_usuarios(simular=False)
    assert r["creadas"] == 0 and r["ya_existian"] == 1 and len(asig.docs) == 1
