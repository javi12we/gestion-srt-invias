"""Edición mínima de libros .xlsx por dentro (zip + XML), sin dependencias externas.

Sirve para rellenar plantillas de Excel que tienen gráficos, comentarios y formatos
condicionales que librerías como openpyxl degradan al guardar. Solo se toca lo que se
pide; el resto del paquete se conserva byte a byte.

- ``Paquete``: lectura/escritura del zip.
- ``Hoja``: modelo de ``<sheetData>`` (filas y celdas) con operaciones para poner
  valores y fórmulas, desagrupar fórmulas compartidas y desplazar filas.
"""

import io
import re
import zipfile
from dataclasses import dataclass, field
from xml.sax.saxutils import escape


# ── Columnas ──────────────────────────────────────────────────────────────────
def col_a_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def num_a_col(n: int) -> str:
    texto = ""
    while n:
        n, resto = divmod(n - 1, 26)
        texto = chr(65 + resto) + texto
    return texto


def separar_ref(ref: str) -> tuple[int, int]:
    """'AH12' -> (fila 12, columna 34)."""
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    return int(m.group(2)), col_a_num(m.group(1))


_REF = re.compile(r"(\$?)([A-Z]{1,3})(\$?)(\d+)(?![\d(])")


def trasladar_formula(formula: str, dfila: int, dcol: int) -> str:
    """Desplaza las referencias relativas de una fórmula (las ancladas con $ no se mueven)."""
    def cambiar(m: re.Match) -> str:
        ca, col, ra, fila = m.groups()
        c = col_a_num(col) + (0 if ca else dcol)
        f = int(fila) + (0 if ra else dfila)
        return f"{ca}{num_a_col(c)}{ra}{f}"
    return _REF.sub(cambiar, formula)


# ── Paquete ───────────────────────────────────────────────────────────────────
class Paquete:
    """Contenido de un .xlsx como {nombre_de_parte: bytes}, conservando el orden."""

    def __init__(self, datos: bytes) -> None:
        with zipfile.ZipFile(io.BytesIO(datos)) as zf:
            self._orden = zf.namelist()
            self._partes = {n: zf.read(n) for n in self._orden}

    def existe(self, nombre: str) -> bool:
        return nombre in self._partes

    def leer(self, nombre: str) -> str:
        return self._partes[nombre].decode("utf-8")

    def escribir(self, nombre: str, texto: str) -> None:
        if nombre not in self._partes:
            self._orden.append(nombre)
        self._partes[nombre] = texto.encode("utf-8")

    def eliminar(self, nombre: str) -> None:
        if nombre in self._partes:
            self._orden.remove(nombre)
            del self._partes[nombre]

    def a_bytes(self) -> bytes:
        salida = io.BytesIO()
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as zf:
            for nombre in self._orden:
                zf.writestr(nombre, self._partes[nombre])
        return salida.getvalue()


# ── Hoja ──────────────────────────────────────────────────────────────────────
@dataclass
class Celda:
    col: int
    estilo: str | None = None
    tipo: str | None = None          # t="s" (texto compartido), "inlineStr", "str", "e", "b"
    formula: str | None = None       # texto de <f> ya escapado para XML
    f_attrs: str = ""                # atributos de <f> (t="shared" ref=... si=...)
    valor: str | None = None         # contenido de <v> (ya escapado)
    inline: str | None = None        # contenido de <is> para inlineStr
    otros: str = ""                  # atributos extra de <c> (cm, vm, ...)

    def a_xml(self, fila: int) -> str:
        ref = f"{num_a_col(self.col)}{fila}"
        attrs = f' r="{ref}"'
        if self.estilo is not None:
            attrs += f' s="{self.estilo}"'
        if self.tipo:
            attrs += f' t="{self.tipo}"'
        attrs += self.otros
        cuerpo = ""
        if self.formula is not None:
            cuerpo += f"<f{self.f_attrs}>{self.formula}</f>" if self.formula != "" else f"<f{self.f_attrs}/>"
        if self.inline is not None:
            cuerpo += f"<is><t>{self.inline}</t></is>"
        if self.valor is not None:
            cuerpo += f"<v>{self.valor}</v>"
        return f"<c{attrs}>{cuerpo}</c>" if cuerpo else f"<c{attrs}/>"


@dataclass
class Fila:
    attrs: str = ""                  # atributos de <row> distintos de r
    celdas: dict[int, Celda] = field(default_factory=dict)


_RE_FILA = re.compile(r'<row r="(\d+)"([^>]*?)(?:/>|>(.*?)</row>)', re.S)
_RE_CELDA = re.compile(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', re.S)
_RE_ATTR = re.compile(r'(\w+(?::\w+)?)="([^"]*)"')
_RE_F = re.compile(r'<f([^>]*?)(?:/>|>(.*?)</f>)', re.S)


class Hoja:
    """Hoja de cálculo: ``antes`` + <sheetData> + ``despues`` (se conservan como texto)."""

    def __init__(self, xml: str) -> None:
        inicio = xml.index("<sheetData")
        fin = xml.index("</sheetData>") + len("</sheetData>")
        self.antes = xml[:inicio]
        self.despues = xml[fin:]
        self.filas: dict[int, Fila] = {}
        cuerpo = xml[inicio:fin]
        for m in _RE_FILA.finditer(cuerpo):
            fila = Fila(attrs=m.group(2))
            for c in _RE_CELDA.finditer(m.group(3) or ""):
                celda = Celda(col=col_a_num(c.group(1)))
                otros = []
                for nombre, valor in _RE_ATTR.findall(c.group(2)):
                    if nombre == "s":
                        celda.estilo = valor
                    elif nombre == "t":
                        celda.tipo = valor
                    else:
                        otros.append(f' {nombre}="{valor}"')
                celda.otros = "".join(otros)
                interior = c.group(3) or ""
                f = _RE_F.search(interior)
                if f:
                    celda.f_attrs = f.group(1)
                    celda.formula = f.group(2) or ""
                v = re.search(r"<v>(.*?)</v>", interior, re.S)
                if v:
                    celda.valor = v.group(1)
                i = re.search(r"<is><t[^>]*>(.*?)</t></is>", interior, re.S)
                if i:
                    celda.inline = i.group(1)
                fila.celdas[celda.col] = celda
            self.filas[int(m.group(1))] = fila

    # ── Acceso ────────────────────────────────────────────────────────────────
    def celda(self, ref: str, crear: bool = False) -> Celda | None:
        fila, col = separar_ref(ref)
        f = self.filas.get(fila)
        if f is None:
            if not crear:
                return None
            f = self.filas[fila] = Fila()
        c = f.celdas.get(col)
        if c is None and crear:
            c = f.celdas[col] = Celda(col=col)
        return c

    def _limpiar(self, c: Celda) -> None:
        c.tipo = c.formula = c.valor = c.inline = None
        c.f_attrs = ""

    def poner_numero(self, ref: str, numero: int | float | None) -> None:
        """Deja un número (o la celda vacía si es None), conservando el estilo."""
        c = self.celda(ref, crear=numero is not None)
        if c is None:
            return
        self._limpiar(c)
        if numero is not None:
            c.valor = repr(numero) if isinstance(numero, float) else str(int(numero))

    def poner_formula(self, ref: str, formula: str) -> None:
        """Pone una fórmula sin valor en caché (Excel la calcula al abrir)."""
        c = self.celda(ref, crear=True)
        self._limpiar(c)
        c.formula = escape(formula)

    def poner_texto(self, ref: str, texto: str) -> None:
        c = self.celda(ref, crear=True)
        self._limpiar(c)
        c.tipo = "inlineStr"
        c.inline = escape(texto)

    def estilo(self, ref: str) -> str | None:
        c = self.celda(ref)
        return c.estilo if c else None

    def poner_estilo(self, ref: str, estilo: str | None) -> None:
        self.celda(ref, crear=True).estilo = estilo

    # ── Fórmulas compartidas ──────────────────────────────────────────────────
    def desagrupar_formulas(self) -> None:
        """Convierte las fórmulas compartidas en fórmulas explícitas, celda por celda."""
        maestras: dict[str, tuple[int, int, str]] = {}
        for nfila, fila in self.filas.items():
            for celda in fila.celdas.values():
                if celda.formula and 't="shared"' in celda.f_attrs and celda.formula != "":
                    si = re.search(r'si="(\d+)"', celda.f_attrs).group(1)
                    maestras[si] = (nfila, celda.col, celda.formula)
        for nfila, fila in self.filas.items():
            for celda in fila.celdas.values():
                if celda.formula is not None and 't="shared"' in celda.f_attrs:
                    si = re.search(r'si="(\d+)"', celda.f_attrs).group(1)
                    mf, mc, texto = maestras[si]
                    if celda.formula == "":
                        celda.formula = trasladar_formula(texto, nfila - mf, celda.col - mc)
                    celda.f_attrs = ""

    def quitar_valores_de_formulas(self) -> None:
        """Quita el valor en caché de las fórmulas (podría estar obsoleto)."""
        for fila in self.filas.values():
            for c in fila.celdas.values():
                if c.formula is not None:
                    c.valor = None
                    if c.tipo in ("e", "str", "b", "n"):
                        c.tipo = None

    # ── Estructura ────────────────────────────────────────────────────────────
    def renumerar_filas(self, nueva_fila) -> None:
        """Mueve cada fila de ``r`` a ``nueva_fila(r)`` (función creciente)."""
        self.filas = {nueva_fila(r): f for r, f in sorted(self.filas.items())}

    def clonar_fila(self, origen: int, destino: int) -> Fila:
        """Copia estilos y atributos de una fila (sin valores ni fórmulas)."""
        base = self.filas[origen]
        nueva = Fila(attrs=base.attrs)
        for col, c in base.celdas.items():
            nueva.celdas[col] = Celda(col=col, estilo=c.estilo, otros=c.otros)
        self.filas[destino] = nueva
        return nueva

    def a_xml(self) -> str:
        partes = ["<sheetData>"]
        for nfila in sorted(self.filas):
            fila = self.filas[nfila]
            celdas = "".join(fila.celdas[c].a_xml(nfila) for c in sorted(fila.celdas))
            partes.append(f'<row r="{nfila}"{fila.attrs}>{celdas}</row>' if celdas else f'<row r="{nfila}"{fila.attrs}/>')
        partes.append("</sheetData>")
        return self.antes + "".join(partes) + self.despues
