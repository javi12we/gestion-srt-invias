"""Servicio de parámetros del sistema editables por el administrador.

A diferencia de la configuración de infraestructura/secretos (que vive en `.env`
y se lee desde `Configuracion`), estos son parámetros de negocio que afectan el
comportamiento del sistema y pueden ajustarse en runtime desde el panel de admin.

Se almacenan en la colección `opciones_configuracion`, bajo la categoría
`parametros_sistema`, vía `ConfiguracionRepositorio`.

Cada parámetro se define de forma declarativa en PARAMETROS: agregar uno nuevo es
una sola entrada (clave, etiqueta, tipo, rango, default, descripción e impacto).
El código siempre conserva un default seguro: si el valor falta o es inválido en
la BD, se cae al `default` y nunca se rompe.
"""

from typing import Any, Dict

from app.repositories.opciones_repo import ConfiguracionRepositorio
from app.services.auditoria_service import AuditoriaService

# ── Registro declarativo de parámetros editables ──────────────────────────────
# Para agregar un parámetro nuevo, añade una entrada aquí. El panel de admin lo
# renderiza automáticamente con su validación e impacto.
PARAMETROS: Dict[str, dict] = {
    "dia_inicio_periodo_certificacion": {
        "etiqueta": "Día de inicio del período de certificación",
        "tipo": "int",
        "min": 1,
        "max": 31,
        "default": 29,
        "unidad": "Día del mes",
        "descripcion": (
            "Desde este día del mes, el sistema habilita la certificación del "
            "mes en curso (ventana normal). Antes de ese día se certifica el mes "
            "anterior (ventana para ponerse al día). Recomendado: 25–31."
        ),
        "impacto": (
            "Cambia qué mes queda habilitado para certificar hoy y la fecha en "
            "que se abre la ventana normal de firmas. Afecta a todos los "
            "contratistas y firmantes de inmediato."
        ),
    },
    "nombre_financiera_retefuente": {
        "etiqueta": "Responsable de la Subdirección Financiera - Retención en la Fuente",
        "tipo": "str",
        "default": "sin nombre_financiera_retefuente",
        "unidad": "Nombre completo",
        "descripcion": (
            "Nombre del responsable del Grupo Cuentas Por Pagar de la Subdirección "
            "Financiera encargado de recibir el formato de retención en la fuente."
        ),
        "impacto": (
            "Este nombre aparecía como destinatario (\"Doctor <nombre>\") en el encabezado "
            "de los formatos de retención en la fuente. Actualmente deshabilitado: esos "
            "formatos ya no muestran un destinatario con nombre propio (el saludo se "
            "dirige al Grupo Cuentas Por Pagar), por lo que este parámetro no tiene efecto."
        ),
        "habilitado": False,
    },
    "firma_extra_control_activa": {
        "etiqueta": "Firma Extra activa — Formato de control Corr-GD-SECOP",
        "tipo": "bool",
        "default": False,
        "unidad": "Activa",
        "descripcion": (
            "Si está activa, además de las firmas de Correspondencia, Gestión "
            "Documental y SECOP II se exige una Firma Extra designada para poder "
            "certificar este formato."
        ),
        "impacto": (
            "Mientras esté activa, ningún colaborador de este formato podrá "
            "certificarse sin la Firma Extra, sin importar que ya tenga las demás "
            "firmas completas. No afecta certificaciones ya aprobadas."
        ),
    },
    "firma_extra_acta_compromiso_activa": {
        "etiqueta": "Firma Extra activa — Acta de compromiso",
        "tipo": "bool",
        "default": False,
        "unidad": "Activa",
        "descripcion": (
            "Si está activa, además de la firma del Jefe se exige una Firma Extra "
            "designada para poder aprobar el Acta de compromiso."
        ),
        "impacto": (
            "Mientras esté activa, ningún Acta de compromiso podrá quedar "
            "aprobada sin la Firma Extra, sin importar que ya tenga las demás "
            "firmas completas. No afecta certificaciones ya aprobadas."
        ),
    },
    "firma_extra_balance_general_activa": {
        "etiqueta": "Firma Extra activa — Balance General CPS",
        "tipo": "bool",
        "default": False,
        "unidad": "Activa",
        "descripcion": (
            "Si está activa, además de las firmas Financiera, Jurídica y del Jefe "
            "se exige una Firma Extra designada para poder aprobar el Balance "
            "General CPS."
        ),
        "impacto": (
            "Mientras esté activa, ningún Balance General CPS podrá quedar "
            "aprobado sin la Firma Extra, sin importar que ya tenga las demás "
            "firmas completas. No afecta certificaciones ya aprobadas."
        ),
    },
    "firma_extra_acta_recibo_entrega_activa": {
        "etiqueta": "Firma Extra activa — Acta de recibo y entrega CPS",
        "tipo": "bool",
        "default": False,
        "unidad": "Activa",
        "descripcion": (
            "Si está activa, además de las firmas Financiera, Jurídica y del Jefe "
            "se exige una Firma Extra designada para poder aprobar el Acta de "
            "recibo y entrega CPS."
        ),
        "impacto": (
            "Mientras esté activa, ningún Acta de recibo y entrega CPS podrá "
            "quedar aprobada sin la Firma Extra, sin importar que ya tenga las "
            "demás firmas completas. No afecta certificaciones ya aprobadas."
        ),
    },
    "notificaciones_correo_modo": {
        "etiqueta": "Notificaciones por correo — momento del envío",
        "tipo": "opcion",
        "opciones": {
            "diario": "Una vez al día (resumen de la noche)",
            "al_momento": "Al momento del cambio (cuando se firma un formato)",
        },
        "default": "diario",
        "unidad": "Momento del envío",
        "descripcion": (
            "Define cuándo se le avisa por correo a un contratista que uno de sus "
            "formatos recibió una firma: en el resumen de la noche, o de inmediato "
            "cuando el firmante firma."
        ),
        "impacto": (
            "Solo cambia el aviso de avance de firmas. Los avisos de correspondencia "
            "vencida y de apertura de formatos dependen de la fecha, no de un cambio, "
            "y siempre salen en el resumen de la noche. En modo 'al momento' cada "
            "firma envía un correo desde la aplicación; si ese envío falla, el aviso "
            "sale igual en el resumen de la noche."
        ),
    },
}

CATEGORIA = "parametros_sistema"


class ParametrosService:
    def __init__(self) -> None:
        self.repo = ConfiguracionRepositorio()
        self.auditoria = AuditoriaService()

    def _validar(self, clave: str, valor: Any) -> Any:
        """Valida y normaliza un valor según el tipo y rango del parámetro.
        Lanza ValueError si es inválido."""
        meta = PARAMETROS[clave]
        if meta["tipo"] == "int":
            try:
                valor = int(valor)
            except (TypeError, ValueError):
                raise ValueError(f"{meta['etiqueta']} debe ser un número entero.")
            if not (meta["min"] <= valor <= meta["max"]):
                raise ValueError(
                    f"{meta['etiqueta']} debe estar entre {meta['min']} y {meta['max']}."
                )
            return valor
        if meta["tipo"] == "str":
            if not valor or not str(valor).strip():
                return meta["default"]
            return str(valor).strip()
        if meta["tipo"] == "opcion":
            if valor not in meta["opciones"]:
                raise ValueError(f"{meta['etiqueta']}: opción no válida.")
            return valor
        if meta["tipo"] == "bool":
            if isinstance(valor, bool):
                return valor
            if isinstance(valor, str):
                return valor.strip().lower() in ("true", "1", "si", "sí", "yes", "on")
            return bool(valor)
        return valor

    def obtener(self, clave: str) -> Any:
        """Devuelve el valor actual del parámetro (override de BD o default).
        Si el valor almacenado es inválido, cae al default de forma segura."""
        meta = PARAMETROS.get(clave)
        if not meta:
            raise ValueError(f"Parámetro desconocido: {clave}")
        doc = self.repo.obtener(CATEGORIA)
        valores = (doc.get("valores") or {}) if doc else {}
        if clave in valores:
            try:
                return self._validar(clave, valores[clave])
            except ValueError:
                return meta["default"]
        return meta["default"]

    def obtener_todos(self) -> Dict[str, Any]:
        """Devuelve {clave: valor_actual} para todos los parámetros registrados."""
        return {clave: self.obtener(clave) for clave in PARAMETROS}

    def actualizar(self, clave: str, valor: Any, usuario: str = "sistema") -> Any:
        """Valida y persiste el nuevo valor; registra el cambio en auditoría.
        Devuelve el valor normalizado. Lanza ValueError si es inválido."""
        meta = PARAMETROS.get(clave)
        if not meta:
            raise ValueError(f"Parámetro desconocido: {clave}")
        if not meta.get("habilitado", True):
            raise ValueError(f"'{meta['etiqueta']}' está deshabilitado y no admite cambios.")
        valor = self._validar(clave, valor)
        anterior = self.obtener(clave)
        self.repo.upsert(CATEGORIA, {f"valores.{clave}": valor})
        self.auditoria.registrar_accion(
            usuario,
            "editar",
            "parametro_sistema",
            {"parametro": clave, "valor_anterior": anterior, "valor_nuevo": valor},
        )
        return valor
