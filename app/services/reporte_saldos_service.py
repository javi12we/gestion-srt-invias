"""Reporte de saldos de contratistas (Excel), exclusivo para administradores.

Hoja 'Resumen': una fila por contrato. Hoja 'Pagos': una fila por pago con el
saldo que queda después de cada uno.

Saldo a liberar = valor inicial + adición - suma de los valores brutos pagados.
Puede ser negativo: significa que los pagos superan el valor del contrato.
"""

import io
from datetime import datetime, timezone

import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

from app.core.autorizacion import ValidacionAutorizacion
from app.core.balance_contrato import anios_contrato, valor_total_contrato
from app.core.catalogos import TIPOS_CONTRATO
from app.core.zona_horaria import ZONA_BOGOTA
from app.repositories.usuario_repo import UsuarioRepositorio
from app.services.usuario_service import UsuarioService

ROLES_AUTORIZADOS = {"admin", "administrador"}

# (clave, encabezado, ancho, formato)
COLUMNAS_RESUMEN = [
    ("nombre", "Nombre", 36, "texto"),
    ("tipo_documento", "Tipo Doc.", 10, "texto"),
    ("cedula", "Cédula", 16, "texto"),
    ("numero_contrato", "Número de Contrato", 18, "texto"),
    ("anio", "Año", 12, "texto"),
    ("tipo_contrato", "Tipo de Contrato", 24, "texto"),
    ("fecha_inicio", "Fecha de Inicio", 14, "fecha"),
    ("fecha_fin", "Fecha de Fin", 14, "fecha"),
    ("estado", "Estado", 16, "texto"),
    ("valor_inicial", "Valor Inicial", 18, "moneda"),
    ("adicion", "Adición", 16, "moneda"),
    ("valor_total", "Valor Total del Contrato", 20, "moneda"),
    ("cantidad_pagos", "N.º de Pagos", 10, "numero"),
    ("total_bruto", "Total Pagado (Bruto)", 20, "moneda"),
    ("total_deducciones", "Total Deducciones", 18, "moneda"),
    ("total_neto", "Total Neto", 18, "moneda"),
    ("saldo", "Saldo a Liberar", 20, "moneda"),
    ("observaciones", "Observaciones", 46, "texto"),
]

COLUMNAS_PAGOS = [
    ("nombre", "Nombre", 36, "texto"),
    ("cedula", "Cédula", 16, "texto"),
    ("numero_contrato", "Número de Contrato", 18, "texto"),
    ("anio", "Año", 12, "texto"),
    ("valor_total", "Valor Total del Contrato", 20, "moneda"),
    ("numero_pago", "N.º de Pago", 18, "texto"),
    ("fecha_pago", "Fecha de Pago", 14, "fecha"),
    ("bruto", "Valor Bruto", 18, "moneda"),
    ("deducciones", "Deducciones", 16, "moneda"),
    ("neto", "Valor Neto", 18, "moneda"),
    ("saldo", "Saldo Después del Pago", 22, "moneda"),
]

_TOTALIZABLES_RESUMEN = (
    "valor_inicial", "adicion", "valor_total", "cantidad_pagos",
    "total_bruto", "total_deducciones", "total_neto", "saldo",
)
_TOTALIZABLES_PAGOS = ("bruto", "deducciones", "neto")


def _fecha_fin_efectiva(contrato: dict):
    prorroga = contrato.get("prorrogra_contrato") or {}
    if prorroga.get("tiene_prorroga") and prorroga.get("fecha_prorrogra"):
        return prorroga["fecha_prorrogra"]
    return contrato.get("fecha_fin")


def _estado_contrato(contrato: dict) -> str:
    if not _fecha_fin_efectiva(contrato):
        return "Sin fecha de fin"
    return "Finalizado" if UsuarioService._contrato_finalizado(contrato) else "Vigente"


def _entero(valor) -> int:
    return int(valor or 0)


def construir_filas(usuarios: list, anio: int | None = None) -> tuple[list, list, int]:
    """Arma las filas de las dos hojas.

    Devuelve (resumen, pagos, contratos_sin_fecha). Con `anio` solo entran los
    contratos de ese año (firma SECOP o fecha de inicio); los que no tienen
    ninguna de las dos fechas quedan fuera y se cuentan en `contratos_sin_fecha`.
    """
    resumen = []
    detalle = []
    sin_fecha = 0

    for usuario in sorted(usuarios, key=lambda u: (u.get("nombre_completo") or "").lower()):
        contratos = sorted(
            usuario.get("contratos") or [],
            key=lambda c: (min(anios_contrato(c), default=0), str(c.get("numero") or "")),
        )
        for contrato in contratos:
            anios = anios_contrato(contrato)
            if anio is not None:
                if not anios:
                    sin_fecha += 1
                    continue
                if anio not in anios:
                    continue

            pagos = sorted(
                contrato.get("pagos") or [],
                key=lambda p: (p.get("fecha_pago") is not None, p.get("fecha_pago") or 0),
            )
            total = valor_total_contrato(contrato)
            valor_inicial = contrato.get("valor")
            adicion = total - _entero(valor_inicial)
            bruto = sum(_entero(p.get("valor_bruto_pago")) for p in pagos)
            saldo = total - bruto if valor_inicial else None

            observaciones = []
            if not valor_inicial:
                observaciones.append("Sin valor de contrato registrado")
            elif saldo < 0:
                observaciones.append("Los pagos superan el valor del contrato")
            if not pagos:
                if _entero(contrato.get("valor_total_pagado")) > 0:
                    observaciones.append(
                        "Tiene un total pagado guardado sin detalle de pagos (no se incluye)"
                    )
                else:
                    observaciones.append("Sin pagos registrados")
            if not usuario.get("numero_documento"):
                observaciones.append("Sin cédula registrada")

            base = {
                "nombre": usuario.get("nombre_completo") or "",
                "cedula": usuario.get("numero_documento") or "",
                "numero_contrato": contrato.get("numero") or "",
                "anio": " - ".join(str(a) for a in sorted(anios)),
                "valor_total": total if valor_inicial else None,
            }
            resumen.append({
                **base,
                "tipo_documento": usuario.get("tipo_documento") or "",
                "tipo_contrato": TIPOS_CONTRATO.get(contrato.get("tipo"), "") if contrato.get("tipo") else "",
                "fecha_inicio": contrato.get("fecha_inicio"),
                "fecha_fin": _fecha_fin_efectiva(contrato),
                "estado": _estado_contrato(contrato),
                "valor_inicial": _entero(valor_inicial) if valor_inicial else None,
                "adicion": adicion,
                "cantidad_pagos": len(pagos),
                "total_bruto": bruto,
                "total_deducciones": sum(_entero(p.get("deducciones_pago")) for p in pagos),
                "total_neto": sum(_entero(p.get("valor_neto_pago")) for p in pagos),
                "saldo": saldo,
                "observaciones": "; ".join(observaciones),
            })

            acumulado = 0
            for pago in pagos:
                acumulado += _entero(pago.get("valor_bruto_pago"))
                detalle.append({
                    **base,
                    "numero_pago": pago.get("numero_pago") or "",
                    "fecha_pago": pago.get("fecha_pago"),
                    "bruto": _entero(pago.get("valor_bruto_pago")),
                    "deducciones": _entero(pago.get("deducciones_pago")),
                    "neto": _entero(pago.get("valor_neto_pago")),
                    "saldo": total - acumulado if valor_inicial else None,
                })

    return resumen, detalle, sin_fecha


def _escribir_hoja(libro, nombre: str, columnas: list, filas: list, totalizables: tuple) -> None:
    hoja = libro.add_worksheet(nombre)
    borde = {"border": 1, "valign": "vcenter", "font_size": 10}
    encabezado = libro.add_format({
        **borde, "bold": True, "font_color": "white", "bg_color": "#E26B0A",
        "align": "center", "text_wrap": True,
    })
    formatos_num = {"moneda": '"$" #,##0;[Red]-"$" #,##0', "fecha": "dd/mm/yyyy", "numero": "0"}
    formatos = {"texto": libro.add_format({**borde, "text_wrap": True})}
    totales = {"texto": libro.add_format({**borde, "bold": True, "bg_color": "#FDE9D9"})}
    for tipo, patron in formatos_num.items():
        formatos[tipo] = libro.add_format({**borde, "num_format": patron})
        totales[tipo] = libro.add_format(
            {**borde, "num_format": patron, "bold": True, "bg_color": "#FDE9D9"}
        )

    posicion = {clave: i for i, (clave, *_) in enumerate(columnas)}
    hoja.set_row(0, 32)
    for col, (_, titulo, ancho, _tipo) in enumerate(columnas):
        hoja.set_column(col, col, ancho)
        hoja.write_string(0, col, titulo, encabezado)

    for fila_num, fila in enumerate(filas, start=1):
        for col, (clave, _, _, tipo) in enumerate(columnas):
            valor = fila.get(clave)
            formato = formatos[tipo]
            if valor is None or valor == "":
                hoja.write_blank(fila_num, col, None, formato)
            elif tipo == "texto":
                # write_string evita que un texto que empiece por '=' se ejecute como fórmula.
                hoja.write_string(fila_num, col, str(valor), formato)
            elif tipo == "fecha":
                hoja.write_datetime(fila_num, col, valor.replace(tzinfo=None), formato)
            elif nombre == "Resumen" and clave in ("valor_total", "saldo"):
                # Se dejan como fórmula para que la cifra se pueda auditar en Excel.
                izquierda, derecha, signo = (
                    ("valor_inicial", "adicion", "+")
                    if clave == "valor_total"
                    else ("valor_total", "total_bruto", "-")
                )
                formula = (
                    f"={xl_rowcol_to_cell(fila_num, posicion[izquierda])}"
                    f"{signo}{xl_rowcol_to_cell(fila_num, posicion[derecha])}"
                )
                hoja.write_formula(fila_num, col, formula, formato, valor)
            else:
                hoja.write_number(fila_num, col, valor, formato)

    if filas:
        hoja.autofilter(0, 0, len(filas), len(columnas) - 1)
        fila_total = len(filas) + 1
        for col, (clave, _, _, tipo) in enumerate(columnas):
            if clave in totalizables:
                rango = f"{xl_rowcol_to_cell(1, col)}:{xl_rowcol_to_cell(len(filas), col)}"
                # SUBTOTAL(9) suma solo las filas visibles al filtrar.
                hoja.write_formula(
                    fila_total, col, f"=SUBTOTAL(9,{rango})", totales[tipo],
                    sum(f.get(clave) or 0 for f in filas),
                )
            else:
                hoja.write_string(fila_total, col, "TOTAL" if col == 0 else "", totales["texto"])
    hoja.freeze_panes(1, 1)


class ReporteSaldosService:
    def __init__(self, repositorio=None):
        self.repositorio = repositorio or UsuarioRepositorio()

    @staticmethod
    def _validar_admin(roles: list) -> None:
        if not ROLES_AUTORIZADOS.intersection(roles or []):
            raise ValidacionAutorizacion("El reporte de saldos es exclusivo para administradores.")

    def anios_disponibles(self, roles: list) -> list:
        """Años con contratos registrados, del más reciente al más antiguo."""
        self._validar_admin(roles)
        anios = set()
        for usuario in self.repositorio.listar_con_contratos():
            for contrato in usuario.get("contratos") or []:
                anios |= anios_contrato(contrato)
        return sorted(anios, reverse=True)

    def generar_excel(self, roles: list, anio: int | None = None) -> dict:
        """Devuelve {buffer, nombre, contratos, pagos, sin_fecha}."""
        self._validar_admin(roles)
        resumen, pagos, sin_fecha = construir_filas(self.repositorio.listar_con_contratos(), anio)

        buffer = io.BytesIO()
        libro = xlsxwriter.Workbook(buffer, {"in_memory": True})
        _escribir_hoja(libro, "Resumen", COLUMNAS_RESUMEN, resumen, _TOTALIZABLES_RESUMEN)
        _escribir_hoja(libro, "Pagos", COLUMNAS_PAGOS, pagos, _TOTALIZABLES_PAGOS)
        libro.close()
        buffer.seek(0)

        hoy = datetime.now(timezone.utc).astimezone(ZONA_BOGOTA).strftime("%Y-%m-%d")
        periodo = str(anio) if anio is not None else "Todos"
        return {
            "buffer": buffer,
            "nombre": f"Saldos Contratistas {periodo} {hoy}.xlsx",
            "contratos": len(resumen),
            "pagos": len(pagos),
            "sin_fecha": sin_fecha,
        }
