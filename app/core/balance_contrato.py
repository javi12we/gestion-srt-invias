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
