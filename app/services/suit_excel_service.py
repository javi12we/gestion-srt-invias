"""Libro de Excel «DATOS DE OPERACIÓN SUIT»: corrige la plantilla y la rellena con datos.

Parte siempre de la plantilla original (hojas «Historico (consulta)» y «SUIT 2026») y la
edita por dentro, de modo que se conservan gráficos, comentarios y formatos. Cada
llamada devuelve un libro nuevo; nunca modifica la plantilla.

Contenido de ``datos``: ``{año: {trámite: {mes: {campo: entero}}}}`` con los campos de
``catalogos.CLAVES_CAMPOS_SUIT``. Un mes ausente significa «aún no cargado» (celda vacía),
distinto de un mes cargado con ceros.
"""

import re
from xml.sax.saxutils import escape

from app.core.catalogos import TRAMITES_SUIT
from app.core.xlsx_paquete import Hoja, Paquete, num_a_col

ANIO_PLANTILLA = 2026          # año con el que viene rotulada la hoja «SUIT 2026»
ANIO_INICIAL_HISTORICO = 2017
ANIO_FINAL_PLANTILLA = 2025    # último año con fila en la plantilla del histórico
NOMBRE_HISTORICO = "Historico (consulta)"

_HOJA_HISTORICO = "xl/worksheets/sheet1.xml"
_HOJA_SUIT = "xl/worksheets/sheet2.xml"

# Orden de los 7 bloques en la hoja «SUIT»: (trámite, fila con los nombres de mes).
_BLOQUES_SUIT = [
    ("carga_extradimensionada", 5),
    ("carga_indivisible_vcc", 24),
    ("concepto_estaciones_servicio", 44),
    ("cierre_vias", 62),
    ("uso_zona_via", 82),
    ("tarifa_diferencial_peajes", 101),
    ("obras_riberas_rios", 120),
]
# Filas de un bloque SUIT, relativas a la fila de meses.
_F_LINEA, _F_PRESENCIAL, _F_TOTAL, _F_PQRD, _F_RECIBIDAS = 1, 2, 3, 4, 5
_F_OTRAS, _F_QUEJAS, _F_RECLAMOS, _F_DENUNCIAS = 6, 7, 8, 9
_F_PCT_RESUELTAS, _F_PCT_QUEJAS, _F_PCT_RECLAMOS, _F_PCT_DENUNCIAS = 10, 11, 12, 13
_CAMPO_A_FILA = {
    "solicitudes_linea": _F_LINEA, "solicitudes_presencial": _F_PRESENCIAL,
    "otras_pqrd": _F_OTRAS, "quejas": _F_QUEJAS, "reclamos": _F_RECLAMOS, "denuncias": _F_DENUNCIAS,
}
# La fila 10 («Total solicitudes recibidas») es la suma de «en línea» y «presencial», y la fila 9
# («Número de PQRD recibidas») es la suma de las filas 10 a 14: ninguna se digita ni se guarda.
_COMPONENTES_PQRD = ("solicitudes_linea", "solicitudes_presencial", "otras_pqrd", "quejas", "reclamos", "denuncias")


def _pqrd_total(valores: dict) -> int:
    """«Número de PQRD recibidas» de un mes (para el histórico)."""
    return sum(int(valores.get(c, 0)) for c in _COMPONENTES_PQRD)

# Orden de los 7 bloques en «Historico (consulta)»: (trámite, fila de encabezado, gráfico de barras, gráfico de líneas).
_BLOQUES_HISTORICO = [
    ("concepto_estaciones_servicio", 3, 1, 2),
    ("cierre_vias", 37, 3, 4),
    ("uso_zona_via", 68, 5, 6),
    ("carga_extradimensionada", 99, 7, 8),
    ("carga_indivisible_vcc", 130, 9, 12),
    ("tarifa_diferencial_peajes", 161, 10, 11),
    ("obras_riberas_rios", 194, 13, 14),
]
_FILAS_ANIOS_PLANTILLA = ANIO_FINAL_PLANTILLA - ANIO_INICIAL_HISTORICO + 1   # 2017..2025 = 9 filas

_COL_MESES = range(2, 14)            # B..M
_COL_PQRD = range(21, 33)            # U..AF


# ── Lectura de la plantilla ───────────────────────────────────────────────────
def _numero(hoja: Hoja, ref: str) -> int | None:
    c = hoja.celda(ref)
    if c is None or c.formula is not None or c.valor is None or c.tipo in ("s", "str", "e"):
        return None
    try:
        return int(float(c.valor))
    except ValueError:
        return None


def extraer_datos_hoja_suit(plantilla: bytes) -> dict[str, dict[int, dict[str, int]]]:
    """Datos digitados en la hoja SUIT de la plantilla, con el modelo de la app.

    Las filas 8, 9 y 10 son totales (no se leen). Un mes cuenta como cargado si tiene algún dato.
    """
    hoja = Hoja(Paquete(plantilla).leer(_HOJA_SUIT))
    datos: dict[str, dict[int, dict[str, int]]] = {}
    for tramite, h in _BLOQUES_SUIT:
        meses: dict[int, dict[str, int]] = {}
        for col in _COL_MESES:
            c = num_a_col(col)
            crudos = {f: _numero(hoja, f"{c}{h + fila}") for f, fila in (
                ("linea", _F_LINEA), ("presencial", _F_PRESENCIAL), ("recibidas", _F_RECIBIDAS),
                ("otras", _F_OTRAS), ("quejas", _F_QUEJAS), ("reclamos", _F_RECLAMOS), ("denuncias", _F_DENUNCIAS))}
            if all(v is None for v in crudos.values()):
                continue
            v = {k: (x or 0) for k, x in crudos.items()}
            meses[col - 1] = {
                "solicitudes_linea": v["linea"], "solicitudes_presencial": v["presencial"],
                "otras_pqrd": v["otras"], "quejas": v["quejas"], "reclamos": v["reclamos"], "denuncias": v["denuncias"],
            }
        datos[tramite] = meses
    return datos


# ── Hoja «SUIT AAAA» ──────────────────────────────────────────────────────────
def _rellenar_hoja_suit(hoja: Hoja, datos_anio: dict[str, dict[int, dict[str, int]]]) -> None:
    for tramite, h in _BLOQUES_SUIT:
        meses = datos_anio.get(tramite, {})
        for col in _COL_MESES:
            c, mes = num_a_col(col), col - 1
            valores = meses.get(mes)
            for campo, fila in _CAMPO_A_FILA.items():
                hoja.poner_numero(f"{c}{h + fila}", None if valores is None else int(valores.get(campo, 0)))

            lin, pres = f"{c}{h + _F_LINEA}", f"{c}{h + _F_PRESENCIAL}"
            pq, rec = f"{c}{h + _F_PQRD}", f"{c}{h + _F_RECIBIDAS}"
            den = f"{c}{h + _F_DENUNCIAS}"
            hoja.poner_formula(f"{c}{h + _F_TOTAL}", f'IF(COUNT({lin}:{pres})=0,"",SUM({lin}:{pres}))')
            # Fila 10 = en línea + presencial; fila 9 = suma de las filas 10 a 14 (como en la plantilla).
            hoja.poner_formula(rec, f'IF(COUNT({lin}:{pres})=0,"",SUM({lin}:{pres}))')
            hoja.poner_formula(pq, f'IF(COUNT({rec}:{den})=0,"",SUM({rec}:{den}))')
            hoja.poner_formula(f"{c}{h + _F_PCT_RESUELTAS}", f'IFERROR(({lin}+{pres})/{rec},"")')
            hoja.poner_formula(f"{c}{h + _F_PCT_QUEJAS}", f'IFERROR({c}{h + _F_QUEJAS}/{rec},"")')
            hoja.poner_formula(f"{c}{h + _F_PCT_RECLAMOS}", f'IFERROR({c}{h + _F_RECLAMOS}/{rec},"")')
            hoja.poner_formula(f"{c}{h + _F_PCT_DENUNCIAS}", f'IFERROR({den}/{rec},"")')

    # Alerta: el total resuelto no puede superar las PQRD recibidas DEL MISMO MES.
    despues = hoja.despues
    for _, h in _BLOQUES_SUIT:
        despues = re.sub(
            rf'<conditionalFormatting sqref="B{h + _F_TOTAL}:M{h + _F_TOTAL}">.*?</conditionalFormatting>', "", despues, flags=re.S)
    prioridad = 200
    reglas = []
    for _, h in _BLOQUES_SUIT:
        t, p = h + _F_TOTAL, h + _F_PQRD
        reglas.append(
            f'<conditionalFormatting sqref="B{t}:M{t}"><cfRule type="expression" dxfId="41" priority="{prioridad}">'
            f'<formula>AND(ISNUMBER(B{p}),ISNUMBER(B{t}),B{t}&gt;B{p})</formula></cfRule></conditionalFormatting>')
        prioridad += 1
    ultimo = despues.rindex("</conditionalFormatting>") + len("</conditionalFormatting>")
    hoja.despues = despues[:ultimo] + "".join(reglas) + despues[ultimo:]


# ── Hoja «Historico (consulta)» ───────────────────────────────────────────────
def _formulas_fila_historico(hoja: Hoja, fila: int) -> None:
    sol, pq = f"B{fila}:M{fila}", f"U{fila}:AF{fila}"
    hoja.poner_formula(f"N{fila}", f'IF(COUNT({sol})=0,"",SUM({sol}))')
    hoja.poner_formula(f"O{fila}", f'IF(COUNT({sol})=0,"",MIN({sol}))')
    hoja.poner_formula(f"P{fila}", f'IF(COUNT({sol})=0,"",MAX({sol}))')
    hoja.poner_formula(f"Q{fila}", f'IF(COUNT({sol})=0,"",AVERAGE({sol}))')
    hoja.poner_formula(f"AG{fila}", f'IF(COUNT({pq})=0,"",SUM({pq}))')
    hoja.poner_formula(f"AH{fila}", f'IFERROR(AG{fila}/N{fila},"")')


def _rellenar_hoja_historico(hoja: Hoja, anio: int, datos: dict) -> tuple:
    """Corrige las fórmulas, agrega las filas de los años siguientes a 2025 y devuelve
    ``(mapa_filas, filas_por_bloque)`` para ajustar gráficos y dibujo."""
    # La plantilla trae cálculos sueltos y sin rótulo en la columna AI (algunos apuntan a la
    # fila equivocada); no pertenecen a ninguna tabla, así que se descartan.
    for fila in hoja.filas.values():
        for col in [c for c in fila.celdas if c > _COL_PQRD[-1] + 2]:
            del fila.celdas[col]

    extra = anio - ANIO_FINAL_PLANTILLA
    ultimas = [h + _FILAS_ANIOS_PLANTILLA for _, h, _, _ in _BLOQUES_HISTORICO]   # fila 2025 de cada bloque

    def mapa(r: int) -> int:
        return r + extra * sum(1 for p in ultimas if r > p)

    # Estilos de «fila intermedia» y «última fila» (la última lleva borde inferior grueso).
    plantillas = {}
    for ultima in ultimas:
        medio, final = hoja.filas[ultima - 1], hoja.filas[ultima]
        plantillas[ultima] = (
            (medio.attrs, {c: (x.estilo, x.otros) for c, x in medio.celdas.items()}),
            (final.attrs, {c: (x.estilo, x.otros) for c, x in final.celdas.items()}),
        )

    hoja.renumerar_filas(mapa)

    filas_por_bloque = []
    for (tramite, h, _, _), ultima in zip(_BLOQUES_HISTORICO, ultimas):
        primera = mapa(h + 1)
        fin_2025 = mapa(ultima)
        (attrs_m, est_m), (attrs_f, est_f) = plantillas[ultima]
        for k in range(1, extra + 1):                    # filas nuevas (2026 en adelante) con estilo de «última»
            hoja.clonar_fila(fin_2025, fin_2025 + k)
        if extra:                                        # la que era última ahora es intermedia
            for r in range(fin_2025, fin_2025 + extra):
                hoja.filas[r].attrs = attrs_m
                for c, (estilo, otros) in est_m.items():
                    if c in hoja.filas[r].celdas:
                        hoja.filas[r].celdas[c].estilo, hoja.filas[r].celdas[c].otros = estilo, otros
        ultima_fila = fin_2025 + extra
        hoja.filas[ultima_fila].attrs = attrs_f

        for i in range(_FILAS_ANIOS_PLANTILLA + extra):
            r, a = primera + i, ANIO_INICIAL_HISTORICO + i
            hoja.poner_numero(f"A{r}", a)
            hoja.poner_texto(f"T{r}", f"Pqrd {a}")
            if a >= ANIO_FINAL_PLANTILLA:                # 2025 en adelante vienen de la app
                meses = datos.get(a, {}).get(tramite, {})
                for col_s, col_p in zip(_COL_MESES, _COL_PQRD):
                    v = meses.get(col_s - 1)
                    hoja.poner_numero(f"{num_a_col(col_s)}{r}",
                                      None if v is None else int(v["solicitudes_linea"]) + int(v["solicitudes_presencial"]))
                    hoja.poner_numero(f"{num_a_col(col_p)}{r}", None if v is None else _pqrd_total(v))
            _formulas_fila_historico(hoja, r)
        filas_por_bloque.append((tramite, mapa(h), primera, ultima_fila))

    # Combinaciones de celdas (títulos), saltos de página y rango usado.
    def desplazar_rango(m: re.Match) -> str:
        return f'{m.group(1)}{mapa(int(m.group(2)))}{m.group(3)}{mapa(int(m.group(4)))}'
    hoja.despues = re.sub(r'(<mergeCell ref="[A-Z]+)(\d+)(:[A-Z]+)(\d+)', desplazar_rango, hoja.despues)
    hoja.despues = re.sub(
        r"<rowBreaks.*?</rowBreaks>",
        lambda bloque: re.sub(r'<brk id="(\d+)"', lambda m: f'<brk id="{mapa(int(m.group(1)))}"', bloque.group(0)),
        hoja.despues, flags=re.S)
    hoja.antes = re.sub(r'<dimension ref="A1:AI(\d+)"', lambda m: f'<dimension ref="A1:AI{mapa(int(m.group(1)))}"', hoja.antes)

    # Escala de color de la columna «%»: una regla por bloque, sobre todas sus filas.
    modelo = re.search(r'<cfRule type="colorScale" priority="\d+">(.*?)</cfRule>', hoja.despues, re.S).group(1)
    hoja.despues = re.sub(r'<conditionalFormatting sqref="AH[^"]*">.*?</conditionalFormatting>', "", hoja.despues, flags=re.S)
    reglas = "".join(
        f'<conditionalFormatting sqref="AH{primera}:AH{ultima}"><cfRule type="colorScale" priority="{n}">{modelo}</cfRule>'
        f'</conditionalFormatting>' for n, (_, _, primera, ultima) in enumerate(filas_por_bloque, start=1))
    punto = re.search(r"<printOptions|<pageMargins", hoja.despues).start()
    hoja.despues = hoja.despues[:punto] + reglas + hoja.despues[punto:]
    return mapa, filas_por_bloque


# ── Gráficos del histórico ────────────────────────────────────────────────────
_ACENTOS = [("accent1", ""), ("accent2", ""), ("accent3", ""), ("accent4", ""), ("accent5", ""), ("accent6", "")]


def _color(i: int) -> str:
    acento = _ACENTOS[i % 6][0]
    vuelta = i // 6
    if vuelta == 0:
        return f'<a:schemeClr val="{acento}"/>'
    if vuelta == 1:
        return f'<a:schemeClr val="{acento}"><a:lumMod val="60000"/></a:schemeClr>'
    return f'<a:schemeClr val="{acento}"><a:lumMod val="80000"/><a:lumOff val="20000"/></a:schemeClr>'


def _serie(linea: bool, i: int, fila: int, hdr: int, c1: str, c2: str) -> str:
    q = f"'{NOMBRE_HISTORICO}'!"
    nombre = f"<c:tx><c:strRef><c:f>{q}$A${fila}</c:f></c:strRef></c:tx>"
    cat = f"<c:cat><c:strRef><c:f>{q}${c1}${hdr}:${c2}${hdr}</c:f></c:strRef></c:cat>"
    val = f"<c:val><c:numRef><c:f>{q}${c1}${fila}:${c2}${fila}</c:f></c:numRef></c:val>"
    if linea:
        sp = f'<c:spPr><a:ln w="28575" cap="rnd"><a:solidFill>{_color(i)}</a:solidFill><a:round/></a:ln><a:effectLst/></c:spPr><c:marker><c:symbol val="none"/></c:marker>'
        return f'<c:ser><c:idx val="{i}"/><c:order val="{i}"/>{nombre}{sp}{cat}{val}<c:smooth val="0"/></c:ser>'
    sp = f'<c:spPr><a:solidFill>{_color(i)}</a:solidFill><a:ln><a:noFill/></a:ln><a:effectLst/></c:spPr><c:invertIfNegative val="0"/>'
    return f'<c:ser><c:idx val="{i}"/><c:order val="{i}"/>{nombre}{sp}{cat}{val}</c:ser>'


def _grafico(esqueleto: str, linea: bool, titulo: str, hdr: int, filas: range) -> str:
    c1, c2 = ("U", "AF") if linea else ("B", "M")
    series = "".join(_serie(linea, i, fila, hdr, c1, c2) for i, fila in enumerate(filas))
    xml = re.sub(r"<c:ser>.*</c:ser>", lambda _: series, esqueleto, count=1, flags=re.S)
    # Título: se conserva el formato del párrafo y se reemplazan sus textos.
    def reemplazar_titulo(m: re.Match) -> str:
        parrafo = m.group(0)
        formato = re.search(r"<a:pPr>.*?</a:pPr>", parrafo, re.S).group(0)
        return f'<a:p>{formato}<a:r><a:rPr lang="es-CO"/><a:t>{escape(titulo)}</a:t></a:r></a:p>'
    cabecera, resto = xml.split("</c:title>", 1)
    cabecera = re.sub(r"<a:p>(?:(?!<a:p>).)*?</a:p>", reemplazar_titulo, cabecera, count=1, flags=re.S)
    return cabecera + "</c:title>" + resto


def _regenerar_graficos(paquete: Paquete, filas_por_bloque: list) -> None:
    barras = paquete.leer("xl/charts/chart1.xml")
    lineas = paquete.leer("xl/charts/chart2.xml")
    for (tramite, hdr, primera, ultima), (_, _, n_barras, n_lineas) in zip(filas_por_bloque, _BLOQUES_HISTORICO):
        nombre = TRAMITES_SUIT[tramite]["label_corto"]
        filas = range(primera, ultima + 1)
        paquete.escribir(f"xl/charts/chart{n_barras}.xml", _grafico(barras, False, f"Solicitudes mensuales - {nombre}", hdr, filas))
        paquete.escribir(f"xl/charts/chart{n_lineas}.xml", _grafico(lineas, True, f"PQRD mensuales - {nombre}", hdr, filas))


# ── Paquete ───────────────────────────────────────────────────────────────────
def _ajustar_paquete(paquete: Paquete, anio: int, mapa) -> None:
    # El dibujo del histórico: filas de anclaje de los gráficos.
    dibujo = paquete.leer("xl/drawings/drawing1.xml")
    dibujo = re.sub(r"(<xdr:(?:from|to)>.*?<xdr:row>)(\d+)(</xdr:row>)",
                    lambda m: f"{m.group(1)}{mapa(int(m.group(2)) + 1) - 1}{m.group(3)}", dibujo, flags=re.S)
    paquete.escribir("xl/drawings/drawing1.xml", dibujo)

    # Rótulo del año: nombre de la hoja, rangos de los gráficos, títulos impresos y encabezado.
    if anio != ANIO_PLANTILLA:
        viejo, nuevo = f"SUIT {ANIO_PLANTILLA}", f"SUIT {anio}"
        for nombre in ["xl/workbook.xml", "docProps/app.xml"] + [f"xl/charts/chart{n}.xml" for n in range(15, 22)]:
            paquete.escribir(nombre, paquete.leer(nombre).replace(viejo, nuevo))
        textos = paquete.leer("xl/sharedStrings.xml")
        paquete.escribir("xl/sharedStrings.xml", re.sub(rf"(–SUIT-\s+){ANIO_PLANTILLA}", rf"\g<1>{anio}", textos))

    # Sin cadena de cálculo (Excel la reconstruye) y con recálculo completo al abrir.
    paquete.eliminar("xl/calcChain.xml")
    tipos = re.sub(r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "", paquete.leer("[Content_Types].xml"))
    paquete.escribir("[Content_Types].xml", tipos)
    rels = re.sub(r'<Relationship [^>]*Target="calcChain.xml"[^>]*/>', "", paquete.leer("xl/_rels/workbook.xml.rels"))
    paquete.escribir("xl/_rels/workbook.xml.rels", rels)
    libro = paquete.leer("xl/workbook.xml")
    paquete.escribir("xl/workbook.xml", re.sub(r"<calcPr [^>]*/>", '<calcPr calcId="191028" fullCalcOnLoad="1"/>', libro))


# ── API ───────────────────────────────────────────────────────────────────────
def construir_libro(plantilla: bytes, anio: int, datos: dict[int, dict[str, dict[int, dict[str, int]]]]) -> bytes:
    """Libro corregido con los datos de ``anio`` en la hoja «SUIT {anio}» y el histórico 2017 a ``anio``."""
    if anio < ANIO_FINAL_PLANTILLA:
        raise ValueError(f"El año debe ser {ANIO_FINAL_PLANTILLA} o posterior.")
    paquete = Paquete(plantilla)

    suit = Hoja(paquete.leer(_HOJA_SUIT))
    suit.desagrupar_formulas()
    _rellenar_hoja_suit(suit, datos.get(anio, {}))
    suit.quitar_valores_de_formulas()
    paquete.escribir(_HOJA_SUIT, suit.a_xml())

    historico = Hoja(paquete.leer(_HOJA_HISTORICO))
    historico.desagrupar_formulas()
    mapa, filas_por_bloque = _rellenar_hoja_historico(historico, anio, datos)
    historico.quitar_valores_de_formulas()
    paquete.escribir(_HOJA_HISTORICO, historico.a_xml())

    _regenerar_graficos(paquete, filas_por_bloque)
    _ajustar_paquete(paquete, anio, mapa)
    return paquete.a_bytes()
