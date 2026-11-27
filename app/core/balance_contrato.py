"""Cálculo del balance financiero de un contrato a partir de sus pagos.

Única fuente de la fórmula: la usan el guardado de contratos, el cargue masivo
de pagos, la pantalla de balance y los formatos de Balance General CPS.
"""


def calcular_balance_pagos(valor_contrato, pagos) -> tuple[int, int]:
    """Devuelve (valor_total_pagado, valor_total_por_pagar_contrato).

    - Valor total pagado: suma de los valores brutos de todos los pagos.
    - Valor total por pagar: valor total del contrato menos el valor total
      pagado (0 si los pagos ya superan el valor del contrato).
    """
    pagado = sum(int(p.get("valor_bruto_pago") or 0) for p in pagos or [])
    por_pagar = max(int(valor_contrato or 0) - pagado, 0)
    return pagado, por_pagar


def valor_total_contrato(contrato: dict) -> int:
    """Valor inicial del contrato más su adición, si la tiene."""
    adiciones = contrato.get("adiciones_contrato") or {}
    adicion = adiciones.get("valor_adicion") if adiciones.get("tiene_adiciones") else 0
    return int(contrato.get("valor") or 0) + int(adicion or 0)


def anios_contrato(contrato: dict) -> set:
    """Años a los que pertenece un contrato: el de su firma SECOP y el de su
    fecha de inicio. Las fechas de contrato se guardan a medianoche UTC, así que
    el año se lee sin convertir de zona horaria."""
    return {
        contrato[campo].year
        for campo in ("firma_cps_secop", "fecha_inicio")
        if contrato.get(campo)
    }
