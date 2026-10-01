"""Entrada de valores en pesos tolerante a números pegados con formato.

Un ``st.number_input`` deja la interpretación del texto pegado al navegador, y
este descarta la coma: pegar "1000,00" termina guardando 100000. Aquí el texto
se interpreta en Python, igual para todos los navegadores.
"""

import re
from decimal import Decimal, ROUND_HALF_UP

import streamlit as st

_SOLO_NUMERO = re.compile(r"[\d.,]*\d[\d.,]*")
_ADORNOS = re.compile(r"cop|\$|\s", re.IGNORECASE)


def interpretar_pesos(texto) -> int | None:
    """Convierte un valor digitado o pegado a pesos enteros.

    Los decimales se redondean ("1000,00" -> 1000, "1.000,50" -> 1001) y los
    separadores de miles se ignoran ("1.000.000", "1,000,000", "$ 1.000").
    Devuelve 0 para un texto vacío y None si el texto no es un número.

    Un separador seguido de exactamente tres dígitos se toma como de miles
    ("1.000" -> 1000): en pesos no se usan tres decimales.
    """
    if texto is None:
        return 0
    limpio = _ADORNOS.sub("", str(texto))
    if not limpio:
        return 0
    if not _SOLO_NUMERO.fullmatch(limpio):
        return None

    posicion = max(limpio.rfind(","), limpio.rfind("."))
    if posicion == -1:
        return int(limpio)

    cabeza = re.sub(r"[.,]", "", limpio[:posicion]) or "0"
    cola = limpio[posicion + 1:]
    unico_separador = limpio.count(",") + limpio.count(".") == 1

    if len(cola) == 3 or not cola:
        return int(cabeza + cola)
    if len(cola) <= 2 or unico_separador:
        return int(Decimal(f"{cabeza}.{cola}").quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return None


def formato_pesos(valor) -> str:
    return "$ " + f"{int(valor or 0):,}".replace(",", ".")


def clave_pesos(key: str) -> str:
    """Clave real del widget: distinta de ``key`` para no chocar con el estado
    entero que dejaron en sesiones abiertas los antiguos ``st.number_input``."""
    return f"{key}_pesos"


def entrada_pesos(
    label: str,
    *,
    key: str,
    value=0,
    minimo: int = 0,
    disabled: bool = False,
    label_visibility: str = "visible",
    help: str | None = None,
) -> int:
    """Campo de texto para un valor en pesos; devuelve siempre un entero.

    ``value`` es el valor inicial (el guardado). Si lo escrito no es un número,
    se avisa y se conserva ``value``.
    """
    inicial = max(int(value or 0), minimo)
    clave = clave_pesos(key)
    if clave not in st.session_state:
        st.session_state[clave] = str(inicial)

    texto = st.text_input(
        label, key=clave, disabled=disabled, label_visibility=label_visibility, help=help
    )

    valor = interpretar_pesos(texto)
    if valor is None:
        st.error(f"«{texto}» no es un valor válido; escribe solo números. Se conserva {formato_pesos(inicial)}.")
        return inicial

    valor = max(valor, minimo)
    if texto.strip() != str(valor):
        st.caption(f"Se toma como {formato_pesos(valor)}")
    return valor
