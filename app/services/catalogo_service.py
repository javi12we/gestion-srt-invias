from app.core.catalogos import PERMISOS_BASE, ROLES_BASE
from app.db.mongo import obtener_coleccion


OPCIONES_BASE = [
    {
        "categoria": "tipo",
        "opciones": [
            {"clave": "memorandos", "etiqueta": "Memorandos", "activo": True},
            {"clave": "pqrds", "etiqueta": "PQRDS", "activo": True},
        ],
    },
    {
        "categoria": "grupo",
        "opciones": [
            {"clave": "permisos", "etiqueta": "Permisos", "activo": True},
            {"clave": "despacho", "etiqueta": "Despacho", "activo": True},
            {"clave": "innovacion", "etiqueta": "Innovación", "activo": True},
            {"clave": "normativa", "etiqueta": "Normativa", "activo": True},
        ],
    },
    {
        "categoria": "clase_correspondencia",
        "opciones": [
            {"clave": "solicitudes_info", "etiqueta": "Solicitudes de información", "activo": True},
            {"clave": "respuestas", "etiqueta": "Respuestas", "activo": True},
            {"clave": "observaciones", "etiqueta": "Observaciones / Revisiones", "activo": True},
            {"clave": "permisos", "etiqueta": "Permisos", "activo": True},
            {"clave": "contratos", "etiqueta": "Contratos", "activo": True},
            {"clave": "informes", "etiqueta": "Informes", "activo": True},
            {"clave": "radicado_general", "etiqueta": "Radicado General", "activo": True},
            {"clave": "conceptos", "etiqueta": "Conceptos", "activo": True},
            {"clave": "aprobaciones", "etiqueta": "Aprobaciones", "activo": True},
            {"clave": "devoluciones_dinero", "etiqueta": "Devoluciones de dinero", "activo": True},
            {"clave": "doc_administrativo", "etiqueta": "Documento administrativo", "activo": True},
            {"clave": "derechos_peticion", "etiqueta": "Derechos de petición", "activo": True},
            {"clave": "doc_informativo", "etiqueta": "Documento informativo", "activo": True},
            {"clave": "traslado_competencia", "etiqueta": "Traslado por competencia", "activo": True},
            {"clave": "subsanaciones", "etiqueta": "Subsanaciones", "activo": True},
            {"clave": "disciplinarios", "etiqueta": "Disciplinarios", "activo": True},
            {"clave": "informativo", "etiqueta": "Informativo", "activo": True},
        ],
    },
    {
        "categoria": "estados",
        "opciones": [
            {"clave": "recibido", "etiqueta": "Recibido", "activo": True},
            {"clave": "en_tramite", "etiqueta": "En Trámite", "activo": True},
            {"clave": "en_revision", "etiqueta": "En Revisión", "activo": True},
            {"clave": "respondido", "etiqueta": "Respondido", "activo": True},
            {"clave": "archivado", "etiqueta": "Archivado", "activo": True},
            {"clave": "traslado_competencia", "etiqueta": "Traslado por Competencia", "activo": True},
        ],
    },
]


class CatalogoService:
    def __init__(self) -> None:
        self.coleccion_permisos = obtener_coleccion("permisos")
        self.coleccion_roles = obtener_coleccion("roles")
        self.coleccion_opciones = obtener_coleccion("opciones_configuracion")

    def asegurar_catalogos_base(self) -> None:
        for permiso in PERMISOS_BASE:
            self.coleccion_permisos.update_one(
                {"clave": permiso["clave"]},
                {"$setOnInsert": permiso},
                upsert=True,
            )

        for rol in ROLES_BASE:
            self.coleccion_roles.update_one(
                {"nombre": rol["nombre"]},
                {"$set": rol},
                upsert=True,
            )

        for opcion in OPCIONES_BASE:
            self.coleccion_opciones.update_one(
                {"categoria": opcion["categoria"]},
                {"$set": opcion},
                upsert=True,
            )
