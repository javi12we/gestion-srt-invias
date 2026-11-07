from pymongo.errors import DuplicateKeyError

from app.db.mongo import obtener_coleccion

SIN_VERIFICAR = object()   # «no comprobar si el mes cambió» (por defecto al guardar)


class SuitCargueRepositorio:
    """Acceso a 'suit_cargues' (un documento por trámite, año y mes)."""

    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("suit_cargues")

    def obtener(self, tramite: str, anio: int, mes: int):
        return self.coleccion.find_one({"tramite": tramite, "anio": anio, "mes": mes})

    def listar_por_tramite_anio(self, tramite: str, anio: int) -> list[dict]:
        return list(
            self.coleccion.find({"tramite": tramite, "anio": anio}, {"trazabilidad": 0}).sort("mes", 1)
        )

    def listar_por_anio(self, anio: int) -> list[dict]:
        """Todos los cargues del año (sin trazabilidad) para el seguimiento."""
        return list(self.coleccion.find({"anio": anio}, {"trazabilidad": 0}))

    def guardar(self, tramite: str, anio: int, mes: int, trimestre: int, valores: dict,
                usuario: str, ahora, accion: str, version_esperada=SIN_VERIFICAR) -> bool:
        """Crea o actualiza el mes y agrega la entrada de trazabilidad en una sola operación.

        Con ``version_esperada`` (el ``actualizado_en`` que el usuario vio al abrir el mes, o None
        si el mes no existía) solo escribe si nadie lo modificó desde entonces: devuelve False
        en caso de conflicto. Sin ella, sobrescribe sin verificar.
        """
        filtro = {"tramite": tramite, "anio": anio, "mes": mes}
        if version_esperada is not SIN_VERIFICAR:
            filtro["actualizado_en"] = version_esperada
        try:
            self._upsert(filtro, trimestre, valores, usuario, ahora, accion)
        except DuplicateKeyError:
            # El filtro no encontró el mes (cambió o ya existe) y el upsert chocó con el índice único.
            return False
        return True

    def _upsert(self, filtro: dict, trimestre: int, valores: dict, usuario: str, ahora, accion: str) -> None:
        self.coleccion.update_one(
            filtro,
            {
                "$set": {
                    "trimestre": trimestre,
                    "valores": valores,
                    "actualizado_por": usuario,
                    "actualizado_en": ahora,
                },
                "$setOnInsert": {"creado_por": usuario, "creado_en": ahora},
                "$push": {
                    "trazabilidad": {"fecha": ahora, "accion": accion, "usuario": usuario, "valores": valores}
                },
            },
            upsert=True,
        )
