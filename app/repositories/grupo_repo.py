from datetime import datetime, timezone

from app.db.mongo import obtener_coleccion


class GrupoRepositorio:
    """Acceso a la colección 'grupos_trabajo' (catálogo de grupos)."""

    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("grupos_trabajo")

    def listar(self, solo_activos: bool = False) -> list[dict]:
        filtro = {"activo": True} if solo_activos else {}
        return list(self.coleccion.find(filtro).sort("orden", 1))

    def obtener_por_clave(self, clave: str):
        return self.coleccion.find_one({"clave": clave})

    def asegurar(self, grupo: dict) -> bool:
        """Inserta el grupo si no existe (no pisa ediciones). True si lo creó."""
        resultado = self.coleccion.update_one(
            {"clave": grupo["clave"]},
            {
                "$setOnInsert": {
                    **grupo,
                    "activo": True,
                    "creado_en": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        return resultado.upserted_id is not None
