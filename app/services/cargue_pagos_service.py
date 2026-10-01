"""Cargue masivo de pagos de contratos desde el Excel de tesorería (balances de pago).

Ver docs/superpowers/specs/2026-09-30-cargue-pagos-excel-design.md para el diseño completo.
"""

import math
from datetime import datetime

from app.services.usuario_service import UsuarioService

MAX_PAGOS_POR_CONTRATO = 20

TIPO_IDENTIFICACION_CEDULA = "Cédula de Ciudadanía"

COLUMNAS_REQUERIDAS = [
    "Tipo Identificacion",
    "Identificacion",
    "Numero Documento",
    "Fecha de pago",
    "Valor Bruto",
    "Valor Deducciones",
    "Valor Neto",
]


def limpiar_cedula(crudo) -> str | None:
    """Normaliza una cédula leída del Excel a solo dígitos, sin puntos/espacios
    ni el '.0' que deja pandas al leer una columna numérica con nulos."""
    if crudo is None:
        return None
    texto = str(crudo).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    texto = texto.replace(".", "").replace(",", "").replace(" ", "")
    if not texto:
        return None
    try:
        return UsuarioService._normalizar_numero_documento(texto)
    except ValueError:
        return None


def limpiar_numero_pago(crudo) -> str | None:
    """El 'Numero Documento' del Excel (identificador del comprobante de pago,
    no la cédula) se guarda tal cual como numero_pago, solo como string limpio."""
    if crudo is None:
        return None
    texto = str(crudo).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto or None


def limpiar_valor_monetario(crudo) -> int | None:
    """Limpia 'Valor Bruto'/'Valor Deducciones'/'Valor Neto': texto con comas de
    miles y dos decimales (ej. '26,026,880.00') a un entero en pesos."""
    if crudo is None:
        return None
    if isinstance(crudo, float) and math.isnan(crudo):
        return None
    texto = str(crudo).strip().replace(",", "")
    if texto == "" or texto.lower() == "nan":
        return None
    try:
        return round(float(texto))
    except ValueError:
        return None


def limpiar_fecha_pago(crudo) -> datetime | None:
    """'Fecha de pago' llega como texto con hora (ej. '2026-03-31 03:41:42');
    se descarta la hora y se normaliza a medianoche UTC con el mismo helper
    que usa el resto de fechas de contrato."""
    if crudo is None:
        return None
    texto = str(crudo).strip()
    if not texto:
        return None
    try:
        fecha = datetime.strptime(texto[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return UsuarioService._fecha_a_datetime(fecha)
