"""SUIT: trámites de permisos, responsables y cargue mensual de contadores.

Reglas:
- Diligenciar un trámite: administrador, o quien tenga una asignación activa para ese
  trámite (colección 'suit_asignaciones'). Un usuario puede tener varios trámites.
- Asignar/retirar responsables: el administrador (cualquier trámite) o el líder del grupo
  'permisos', que solo puede repartir los trámites que él mismo tiene asignados.
- Los cargues son por (trámite, año, mes), nunca se bloquean y cada guardado deja
  trazabilidad.
"""

from datetime import date, datetime, timezone
from pathlib import Path

from pymongo.errors import DuplicateKeyError

from app.core.autorizacion import ValidacionAutorizacion
from app.core.catalogos import CLAVES_CAMPOS_SUIT, TRAMITES_SUIT
from app.core.zona_horaria import utc_a_bogota
from app.repositories.suit_asignacion_repo import SuitAsignacionRepositorio
from app.repositories.suit_cargue_repo import SIN_VERIFICAR, SuitCargueRepositorio
from app.repositories.usuario_repo import UsuarioRepositorio
from app.services.asignacion_grupo_service import PERMISO_GESTIONAR, AsignacionGrupoService
from app.services.suit_excel_service import ANIO_FINAL_PLANTILLA, construir_libro

GRUPO_PERMISOS = "permisos"
PERMISO_VER_SUIT = "grupo.permisos.ver"   # el mismo que muestra la categoría «Permisos» en el menú
PLANTILLA_EXCEL = Path(__file__).resolve().parents[1] / "assets" / "plantillas" / "plantilla_suit_original.xlsx"
_COMPONENTES_PQRD = ("otras_pqrd", "quejas", "reclamos", "denuncias")   # se suman a las solicitudes resueltas
ANIO_MINIMO = 2020
MESES_POR_TRIMESTRE = 3


class ErrorSuit(Exception):
    """Error de negocio del módulo SUIT (se muestra al usuario con st.warning)."""


class ErrorConflictoSuit(ErrorSuit):
    """El mes fue modificado por otra persona después de que el usuario lo abrió."""


def trimestre_de_mes(mes: int) -> int:
    return (mes - 1) // MESES_POR_TRIMESTRE + 1


def permisos_efectivos(sesion: dict) -> list[str]:
    """Permisos de la sesión; el rol admin cuenta siempre como gestor (como en el menú)."""
    permisos = list(sesion.get("permisos", []))
    if any(r in {"admin", "administrador"} for r in sesion.get("roles", [])):
        permisos.append(PERMISO_GESTIONAR)
    return permisos


class SuitService:
    def __init__(self, repo_asignaciones=None, repo_cargues=None, repo_usuarios=None,
                 servicio_grupos=None) -> None:
        self.asignaciones = repo_asignaciones or SuitAsignacionRepositorio()
        self.cargues = repo_cargues or SuitCargueRepositorio()
        self.usuarios = repo_usuarios or UsuarioRepositorio()
        self.grupos = servicio_grupos or AsignacionGrupoService()

    # ── Autorización ──────────────────────────────────────────────────────────
    @staticmethod
    def _es_admin(permisos_actor: list[str] | None) -> bool:
        return PERMISO_GESTIONAR in (permisos_actor or [])

    def _es_apto(self, usuario_id: str) -> bool:
        """Una asignación solo vale si el usuario sigue activo y en el grupo Permisos."""
        usuario = self.usuarios.buscar_por_id(usuario_id)
        return bool(
            usuario and usuario.get("activo", False)
            and self.grupos.asignaciones.obtener_activa(usuario_id, GRUPO_PERMISOS)
        )

    def _ids_aptos(self, ids) -> set:
        """De los ``ids`` (ObjectId), los de usuarios activos y miembros del grupo Permisos."""
        ids = set(ids)
        if not ids:
            return set()
        miembros = {a["usuario_id"] for a in self.grupos.asignaciones.listar_por_grupo(GRUPO_PERMISOS, "activo")}
        activos = {u["_id"] for u in self.usuarios.listar_por_ids(list(ids)) if u.get("activo", False)}
        return ids & miembros & activos

    def tramites_de_usuario(self, usuario_id: str) -> list[str]:
        """Trámites que el usuario tiene asignados (activos), en el orden del catálogo.

        Vacío si el usuario fue desactivado o retirado del grupo Permisos: sus asignaciones
        se conservan (historial) pero dejan de dar acceso.
        """
        if not self._es_apto(usuario_id):
            return []
        propios = {a["tramite"] for a in self.asignaciones.listar_activas_por_usuario(usuario_id)}
        return [t for t in TRAMITES_SUIT if t in propios]

    def tramites_visibles(self, usuario_id: str, permisos_actor: list[str]) -> list[str]:
        """Trámites que el usuario puede abrir y diligenciar (todos si es administrador)."""
        if self._es_admin(permisos_actor):
            return list(TRAMITES_SUIT)
        return self.tramites_de_usuario(usuario_id)

    def tramites_repartibles(self, actor_id: str | None, permisos_actor: list[str]) -> list[str]:
        """Trámites que el actor puede asignar a otros: todos (admin) o los suyos (líder de Permisos)."""
        if self._es_admin(permisos_actor):
            return list(TRAMITES_SUIT)
        if actor_id and self.grupos.es_lider_de(actor_id, GRUPO_PERMISOS):
            return self.tramites_de_usuario(actor_id)
        return []

    # ── Responsables ──────────────────────────────────────────────────────────
    def mapa_tramites_activos(self) -> dict[str, list[str]]:
        """{str(usuario_id): [trámites activos]} para el tablero de gestores."""
        mapa: dict[str, list[str]] = {}
        for a in self.asignaciones.listar_activas():
            mapa.setdefault(str(a["usuario_id"]), []).append(a["tramite"])
        return {u: [t for t in TRAMITES_SUIT if t in ts] for u, ts in mapa.items()}

    def responsables(self, tramite: str) -> list[dict]:
        """Personas encargadas hoy del trámite: [{'nombre', 'usuario'}]."""
        asignadas = self.asignaciones.listar_activas_por_tramite(tramite)
        aptos = self._ids_aptos(a["usuario_id"] for a in asignadas)
        asignadas = [a for a in asignadas if a["usuario_id"] in aptos]
        usuarios = {u["_id"]: u for u in self.usuarios.listar_por_ids([a["usuario_id"] for a in asignadas])}
        return [
            {
                "nombre": usuarios.get(a["usuario_id"], {}).get("nombre_completo") or "(usuario eliminado)",
                "usuario": usuarios.get(a["usuario_id"], {}).get("usuario", ""),
            }
            for a in asignadas
        ]

    def definir_tramites_usuario(self, usuario_id: str, tramites: list[str], actor: str,
                                 permisos_actor: list[str], actor_id: str | None = None) -> dict:
        """Deja al usuario con ``tramites`` dentro del alcance del actor.

        Solo se agregan o retiran trámites que el actor puede repartir; los demás
        quedan como estaban. Devuelve {'asignados': [...], 'retirados': [...]}.
        """
        alcance = set(self.tramites_repartibles(actor_id, permisos_actor))
        if not alcance:
            raise ValidacionAutorizacion(
                "Solo el administrador o el líder del grupo Permisos pueden asignar trámites SUIT."
            )
        desconocidos = set(tramites) - set(TRAMITES_SUIT)
        if desconocidos:
            raise ErrorSuit(f"Trámite SUIT desconocido: {', '.join(sorted(desconocidos))}")

        usuario = self.usuarios.buscar_por_id(usuario_id)
        if not usuario or not usuario.get("activo", False):
            raise ErrorSuit("El usuario no existe o está inactivo.")
        if not self.grupos.asignaciones.obtener_activa(usuario_id, GRUPO_PERMISOS):
            raise ErrorSuit("El usuario debe pertenecer al grupo de trabajo Permisos.")

        deseados = set(tramites) & alcance
        actuales = {a["tramite"]: a for a in self.asignaciones.listar_activas_por_usuario(usuario_id)}
        ahora = datetime.now(timezone.utc)
        resultado = {"asignados": [], "retirados": []}

        for tramite in [t for t in TRAMITES_SUIT if t in deseados and t not in actuales]:
            try:
                self.asignaciones.insertar({
                    "usuario_id": usuario["_id"],
                    "tramite": tramite,
                    "estado": "activo",
                    "fecha_asignacion": ahora,
                    "asignado_por": actor,
                    "fecha_retiro": None,
                    "razon_retiro": None,
                    "retirado_por": None,
                    "trazabilidad": [{"fecha": ahora, "accion": "asignado", "usuario": actor, "detalle": None}],
                })
                resultado["asignados"].append(tramite)
            except DuplicateKeyError:
                continue

        for tramite in [t for t in TRAMITES_SUIT if t in actuales and t in alcance and t not in deseados]:
            razon = f"Retirado por {actor}"
            retirada = self.asignaciones.retirar(
                actuales[tramite]["_id"],
                {"estado": "retirado", "fecha_retiro": ahora, "razon_retiro": razon, "retirado_por": actor},
                {"fecha": ahora, "accion": "retirado", "usuario": actor, "detalle": razon},
            )
            if retirada:
                resultado["retirados"].append(tramite)
        return resultado

    # ── Cargue mensual ────────────────────────────────────────────────────────
    @staticmethod
    def totales(valores: dict) -> dict:
        """Totales calculados del mes (no se guardan).

        ``total_resueltas`` = en línea + presenciales (es también la fila 10 del formato).
        ``pqrd_recibidas`` = ``total_resueltas`` + otras PQRD + quejas + reclamos + denuncias.
        """
        resueltas = valores.get("solicitudes_linea", 0) + valores.get("solicitudes_presencial", 0)
        return {
            "total_resueltas": resueltas,
            "pqrd_recibidas": resueltas + sum(valores.get(c, 0) for c in _COMPONENTES_PQRD),
        }

    @staticmethod
    def _validar_periodo(anio: int, mes: int) -> None:
        anio_max = datetime.now(timezone.utc).year + 1
        if not isinstance(anio, int) or not ANIO_MINIMO <= anio <= anio_max:
            raise ErrorSuit(f"El año debe estar entre {ANIO_MINIMO} y {anio_max}.")
        if not isinstance(mes, int) or not 1 <= mes <= 12:
            raise ErrorSuit("El mes debe estar entre 1 y 12.")

    def obtener_mes(self, tramite: str, anio: int, mes: int) -> dict | None:
        return self.cargues.obtener(tramite, anio, mes)

    def guardar_mes(self, tramite: str, anio: int, mes: int, valores: dict, actor: str,
                    permisos_actor: list[str], actor_id: str | None = None,
                    version_esperada=SIN_VERIFICAR) -> str:
        """Crea o actualiza el cargue del mes. Devuelve 'creado' o 'actualizado'.

        ``version_esperada`` es el ``actualizado_en`` que el usuario vio al abrir el mes (None si
        aún no existía). Si otra persona guardó mientras tanto lanza ``ErrorConflictoSuit`` y no
        escribe nada, para no pisar sus cambios.
        """
        if tramite not in TRAMITES_SUIT:
            raise ErrorSuit("Trámite SUIT desconocido.")
        if not (self._es_admin(permisos_actor)
                or (actor_id and tramite in self.tramites_de_usuario(actor_id))):
            raise ValidacionAutorizacion("No tienes asignado este trámite SUIT.")
        self._validar_periodo(anio, mes)

        limpios = {}
        for campo in CLAVES_CAMPOS_SUIT:
            valor = valores.get(campo, 0)
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
                raise ErrorSuit("Todos los valores deben ser números enteros mayores o iguales a cero.")
            limpios[campo] = valor

        accion = "actualizado" if self.cargues.obtener(tramite, anio, mes) else "creado"
        guardado = self.cargues.guardar(
            tramite, anio, mes, trimestre_de_mes(mes), limpios, actor,
            datetime.now(timezone.utc), accion, version_esperada,
        )
        if not guardado:
            raise ErrorConflictoSuit(
                "Otra persona modificó este mes mientras lo editabas. "
                "Recarga los valores guardados para no perder sus cambios."
            )
        return accion

    # ── Avance (semáforo) ─────────────────────────────────────────────────────
    def progreso(self, tramite: str, anio: int, hoy: date | None = None) -> dict:
        """Avance del cargue del año para el semáforo del formulario.

        Un mes cuenta como cargado si se guardó. El semáforo es rojo o verde según FALTE
        o no un cargue ya vencido (mes terminado); si aún no vence ningún mes queda
        «por_vencer» (neutro). Devuelve::

            {'trimestres': {1: {'meses_cargados', 'porcentaje', 'faltan': [meses], 'estado'}, ...},
             'anual': porcentaje, 'faltan': [meses], 'estado': 'pendiente'|'al_dia'|'por_vencer'}
        """
        hoy = hoy or utc_a_bogota(datetime.now(timezone.utc)).date()
        vencidos = self._meses_vencidos(anio, hoy)
        cargados = {c["mes"] for c in self.cargues.listar_por_tramite_anio(tramite, anio)}

        def estado(faltan: list[int], hay_vencidos: bool) -> str:
            if faltan:
                return "pendiente"
            return "al_dia" if hay_vencidos else "por_vencer"

        trimestres = {}
        for t in range(1, 5):
            meses = range((t - 1) * MESES_POR_TRIMESTRE + 1, t * MESES_POR_TRIMESTRE + 1)
            n = sum(1 for m in meses if m in cargados)
            faltan = [m for m in meses if m <= vencidos and m not in cargados]
            trimestres[t] = {
                "meses_cargados": n,
                "porcentaje": round(100 * n / MESES_POR_TRIMESTRE),
                "faltan": faltan,
                "estado": estado(faltan, any(m <= vencidos for m in meses)),
            }
        faltan_anio = [m for m in range(1, vencidos + 1) if m not in cargados]
        return {
            "trimestres": trimestres,
            "anual": round(100 * len(cargados) / 12),
            "meses": sorted(cargados),
            "faltan": faltan_anio,
            "estado": estado(faltan_anio, vencidos > 0),
        }

    # ── Seguimiento (solo lectura, para quien ve el SUIT) ───────────────
    def puede_ver_suit(self, actor_id: str | None, permisos_actor: list[str]) -> bool:
        """Quien ve la página SUIT en el menú: administrador, miembro activo del grupo Permisos
        o cualquier rol/permiso con ``grupo.permisos.ver``; tenga o no trámites asignados."""
        if self._es_admin(permisos_actor) or PERMISO_VER_SUIT in (permisos_actor or []):
            return True
        return bool(actor_id and self.grupos.asignaciones.obtener_activa(actor_id, GRUPO_PERMISOS))

    @staticmethod
    def _meses_vencidos(anio: int, hoy: date) -> int:
        """Meses completamente transcurridos: ya debieron estar cargados."""
        if anio < hoy.year:
            return 12
        return hoy.month - 1 if anio == hoy.year else 0

    @staticmethod
    def _serie_mensual(docs_por_mes: dict[int, list[dict]]) -> dict:
        """Suma de cada contador por mes; None en los meses sin cargue (no es lo mismo que 0)."""
        serie = {campo: [] for campo in CLAVES_CAMPOS_SUIT}
        for mes in range(1, 13):
            docs = docs_por_mes.get(mes, [])
            for campo in CLAVES_CAMPOS_SUIT:
                serie[campo].append(sum(d["valores"].get(campo, 0) for d in docs) if docs else None)
        # «PQRD recibidas» es un total calculado, no un dato guardado.
        serie["pqrd_recibidas"] = [
            None if serie["solicitudes_linea"][i] is None
            else serie["solicitudes_linea"][i] + serie["solicitudes_presencial"][i]
            + sum(serie[c][i] for c in _COMPONENTES_PQRD)
            for i in range(12)
        ]
        return serie

    def seguimiento(self, anio: int, actor_id: str | None, permisos_actor: list[str],
                    hoy: date | None = None) -> dict:
        """Estado del cargue SUIT del año: cumplimiento por trámite y mes, indicadores y responsables.

        Un mes está 'cargado' si se guardó, 'pendiente' si ya transcurrió sin cargue y
        'futuro' si aún no termina.
        """
        if not self.puede_ver_suit(actor_id, permisos_actor):
            raise ValidacionAutorizacion("No tienes acceso al seguimiento SUIT.")
        hoy = hoy or utc_a_bogota(datetime.now(timezone.utc)).date()
        self._validar_periodo(anio, 1)
        vencidos = self._meses_vencidos(anio, hoy)

        docs: dict[str, dict[int, dict]] = {t: {} for t in TRAMITES_SUIT}
        for c in self.cargues.listar_por_anio(anio):
            if c["tramite"] in docs:
                docs[c["tramite"]][c["mes"]] = c

        asignadas = self.asignaciones.listar_activas()
        aptos = self._ids_aptos(a["usuario_id"] for a in asignadas)
        asignadas = [a for a in asignadas if a["usuario_id"] in aptos]
        usuarios = {u["_id"]: u for u in self.usuarios.listar_por_ids(list(aptos))}
        responsables: dict[str, list[str]] = {t: [] for t in TRAMITES_SUIT}
        for a in asignadas:
            u = usuarios.get(a["usuario_id"], {})
            if a["tramite"] in responsables:
                responsables[a["tramite"]].append(u.get("nombre_completo") or u.get("usuario") or "(usuario eliminado)")

        tramites = []
        for t, meta in TRAMITES_SUIT.items():
            cargados = docs[t]
            estados = ["cargado" if m in cargados else ("pendiente" if m <= vencidos else "futuro")
                       for m in range(1, 13)]
            cargados_vencidos = sum(1 for m in cargados if m <= vencidos)
            ultimos = [c["actualizado_en"] for c in cargados.values() if c.get("actualizado_en")]
            tramites.append({
                "tramite": t,
                "nombre": meta["label_corto"],
                "estados": estados,
                "cargados": len(cargados),
                "cargados_vencidos": cargados_vencidos,
                "pendientes": estados.count("pendiente"),
                "avance": round(100 * len(cargados) / 12),
                "cumplimiento": round(100 * cargados_vencidos / vencidos) if vencidos else None,
                "responsables": responsables[t],
                "ultimo_guardado": max(ultimos) if ultimos else None,
            })

        total_cargados = sum(x["cargados"] for x in tramites)
        indicadores = {"todos": self._serie_mensual({
            m: [d[m] for d in docs.values() if m in d] for m in range(1, 13)
        })}
        for t in TRAMITES_SUIT:
            indicadores[t] = self._serie_mensual({m: [d] for m, d in docs[t].items()})

        return {
            "anio": anio,
            "meses_vencidos": vencidos,
            "tramites": tramites,
            "indicadores": indicadores,
            "kpis": {
                "avance_anual": round(100 * total_cargados / (12 * len(TRAMITES_SUIT))),
                "cumplimiento": (round(100 * sum(x["cargados_vencidos"] for x in tramites)
                                       / (vencidos * len(TRAMITES_SUIT))) if vencidos else None),
                "pendientes_vencidos": sum(x["pendientes"] for x in tramites),
                "sin_responsable": sum(1 for x in tramites if not x["responsables"]),
            },
        }

    # ── Reporte en Excel ──────────────────────────────────────────────────────
    def generar_reporte_excel(self, anio: int, actor_id: str | None, permisos_actor: list[str]) -> bytes:
        """Libro «DATOS DE OPERACIÓN SUIT» del año: hoja «SUIT {anio}» e histórico con gráficos.

        Lo puede descargar cualquiera que vea el SUIT. El histórico incluye todos los años
        cargados desde 2025.
        """
        if not self.puede_ver_suit(actor_id, permisos_actor):
            raise ValidacionAutorizacion("No tienes acceso al reporte SUIT.")
        if anio < ANIO_FINAL_PLANTILLA:
            raise ErrorSuit(f"Los reportes SUIT están disponibles desde {ANIO_FINAL_PLANTILLA}.")
        self._validar_periodo(anio, 1)

        datos: dict[int, dict[str, dict[int, dict]]] = {}
        for a in range(ANIO_FINAL_PLANTILLA, anio + 1):
            por_tramite: dict[str, dict[int, dict]] = {}
            for c in self.cargues.listar_por_anio(a):
                if c["tramite"] in TRAMITES_SUIT:
                    por_tramite.setdefault(c["tramite"], {})[c["mes"]] = c["valores"]
            datos[a] = por_tramite
        return construir_libro(PLANTILLA_EXCEL.read_bytes(), anio, datos)

    # ── Migración desde usuarios.permisos_extra ───────────────────────────────
    def migrar_desde_permisos_extra(self, simular: bool = True) -> dict:
        """Convierte las claves 'suit.ver_*' que hoy están en usuarios.permisos_extra en asignaciones.

        Idempotente; no modifica 'usuarios'.
        """
        resumen = {"a_crear": 0, "creadas": 0, "ya_existian": 0}
        claves = {p["clave"]: p["tramite"] for p in TRAMITES_SUIT.values()}
        ahora = datetime.now(timezone.utc)
        for usuario in self.usuarios.listar_con_permisos_extra(list(claves)):
            for clave in usuario.get("permisos_extra", []):
                tramite = claves.get(clave)
                if not tramite:
                    continue
                if self.asignaciones.obtener_activa(str(usuario["_id"]), tramite):
                    resumen["ya_existian"] += 1
                    continue
                resumen["a_crear"] += 1
                if simular:
                    continue
                detalle = "Migración inicial desde usuarios.permisos_extra"
                try:
                    self.asignaciones.insertar({
                        "usuario_id": usuario["_id"], "tramite": tramite, "estado": "activo",
                        "fecha_asignacion": ahora, "asignado_por": "migracion",
                        "fecha_retiro": None, "razon_retiro": None, "retirado_por": None,
                        "trazabilidad": [
                            {"fecha": ahora, "accion": "asignado", "usuario": "migracion", "detalle": detalle}
                        ],
                    })
                    resumen["creadas"] += 1
                except DuplicateKeyError:
                    resumen["ya_existian"] += 1
        return resumen
