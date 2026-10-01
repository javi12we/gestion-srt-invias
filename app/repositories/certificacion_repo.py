from datetime import datetime, timezone

from bson import ObjectId

from app.db.mongo import obtener_coleccion

TIPOS_FIRMA = ("corr", "gd", "secop")


class CertificacionRepositorio:
    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("certificaciones")

    def buscar_por_usuario_periodo(self, usuario_id: str, año: int, mes: int, tipo_formato: str = None):
        query = {
            "usuario_id": ObjectId(usuario_id),
            "año": año,
            "mes": mes,
        }
        if tipo_formato:
            query["tipo_formato"] = tipo_formato
        else:
            query["tipo_formato"] = {"$in": [None, "gestion_correspondencia"]}
        return self.coleccion.find_one(query)

    def listar_por_usuario(self, usuario_id: str):
        return list(
            self.coleccion.find({"usuario_id": ObjectId(usuario_id)})
            .sort([("año", -1), ("mes", -1)])
        )

    def listar_por_periodo(self, año: int, mes: int, tipo_formato: str = None):
        query = {
            "año": año,
            "mes": mes,
        }
        if tipo_formato:
            query["tipo_formato"] = tipo_formato
        else:
            query["tipo_formato"] = {"$in": [None, "gestion_correspondencia"]}
        return list(self.coleccion.find(query))

    def listar_con_firmas_desde(self, fecha, roles: list):
        """Certificaciones en las que alguno de `roles` firmó desde `fecha`."""
        return list(
            self.coleccion.find({"$or": [{f"firmas.{rol}.fecha": {"$gte": fecha}} for rol in roles]})
        )

    def buscar_por_hash(self, hash_code: str):
        return self.coleccion.find_one({"hash_verificacion": hash_code, "estado": "aprobado"})

    def crear(self, datos: dict):
        return self.coleccion.insert_one(datos).inserted_id

    def actualizar(self, id_cert: str, campos: dict):
        return self.coleccion.update_one(
            {"_id": ObjectId(id_cert)},
            {"$set": campos},
        )

    def registrar_firma(
        self,
        usuario_id: str,
        nombre_usuario: str,
        año: int,
        mes: int,
        tipo: str,
        firmante_id: str,
        firmante_nombre: str,
        comentario: str | None = None,
    ) -> bool:
        ahora = datetime.now(timezone.utc)
        self.coleccion.update_one(
            {
                "usuario_id": ObjectId(usuario_id),
                "año": año,
                "mes": mes,
                "tipo_formato": {"$in": [None, "gestion_correspondencia"]},
            },
            {
                "$set": {
                    f"firmas.{tipo}": {
                        "firmante_id": ObjectId(firmante_id),
                        "firmante_nombre": firmante_nombre,
                        "fecha": ahora,
                        "comentario": comentario.strip() if comentario and comentario.strip() else None,
                    }
                },
                "$setOnInsert": {
                    "nombre_usuario": nombre_usuario,
                    "estado": "pendiente",
                    "tipo_formato": "gestion_correspondencia",
                    "creado_en": ahora,
                },
            },
            upsert=True,
        )
        return True

    def revocar_firma(self, usuario_id: str, año: int, mes: int, tipo: str) -> bool:
        self.coleccion.update_one(
            {
                "usuario_id": ObjectId(usuario_id),
                "año": año,
                "mes": mes,
                "tipo_formato": {"$in": [None, "gestion_correspondencia"]},
            },
            {"$unset": {f"firmas.{tipo}": ""}},
        )
        return True

    def registrar_firma_actas(
        self,
        usuario_id: str,
        año: int,
        mes: int,
        tipo_formato: str,
        rol: str,
        firmante_id: str,
        firmante_nombre: str,
        comentario: str | None = None,
    ) -> None:
        """Guarda la firma de un rol (financiera/abogado/jefe) sobre el documento
        exacto (usuario_id, año, mes, tipo_formato) que ya debe existir."""
        ahora = datetime.now(timezone.utc)
        self.coleccion.update_one(
            {
                "usuario_id": ObjectId(usuario_id),
                "año": año,
                "mes": mes,
                "tipo_formato": tipo_formato,
            },
            {
                "$set": {
                    f"firmas.{rol}": {
                        "firmante_id": ObjectId(firmante_id),
                        "firmante_nombre": firmante_nombre,
                        "fecha": ahora,
                        "comentario": comentario.strip() if comentario and comentario.strip() else None,
                    }
                }
            },
        )

    def revocar_firmas_actas(
        self, usuario_id: str, año: int, mes: int, tipo_formato: str, roles: list
    ) -> None:
        """Borra las firmas de los roles indicados (el revocado + los posteriores en cascada)."""
        if not roles:
            return
        self.coleccion.update_one(
            {
                "usuario_id": ObjectId(usuario_id),
                "año": año,
                "mes": mes,
                "tipo_formato": tipo_formato,
            },
            {"$unset": {f"firmas.{r}": "" for r in roles}},
        )

    def agregar_evento_actas(
        self, usuario_id: str, año: int, mes: int, tipo_formato: str, evento: dict
    ) -> None:
        """Agrega una entrada a la bitácora `eventos` del documento (ej. revocación en cascada)."""
        self.coleccion.update_one(
            {
                "usuario_id": ObjectId(usuario_id),
                "año": año,
                "mes": mes,
                "tipo_formato": tipo_formato,
            },
            {"$push": {"eventos": evento}},
        )

    def buscar_por_id(self, cert_id: str):
        return self.coleccion.find_one({"_id": ObjectId(cert_id)})

    def registrar_firma_actas_por_id(
        self,
        cert_id: str,
        rol: str,
        firmante_id: str,
        firmante_nombre: str,
        comentario: str | None = None,
    ) -> None:
        ahora = datetime.now(timezone.utc)
        self.coleccion.update_one(
            {"_id": ObjectId(cert_id)},
            {
                "$set": {
                    f"firmas.{rol}": {
                        "firmante_id": ObjectId(firmante_id),
                        "firmante_nombre": firmante_nombre,
                        "fecha": ahora,
                        "comentario": comentario.strip() if comentario and comentario.strip() else None,
                    }
                }
            },
        )

    def revocar_firmas_actas_por_id(self, cert_id: str, roles: list) -> None:
        if not roles:
            return
        self.coleccion.update_one(
            {"_id": ObjectId(cert_id)},
            {"$unset": {f"firmas.{r}": "" for r in roles}},
        )

    def agregar_evento_actas_por_id(self, cert_id: str, evento: dict) -> None:
        self.coleccion.update_one(
            {"_id": ObjectId(cert_id)},
            {"$push": {"eventos": evento}},
        )

