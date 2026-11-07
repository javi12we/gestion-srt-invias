"""Cargue masivo de respuestas de correspondencia.

Actualiza radicados YA existentes y abiertos (pendiente, en_tramite, en_revision)
a respondido / archivado / traslado_competencia desde un archivo Excel, CSV o TXT.
Nunca crea radicados ni toca los ya cerrados. Cada cambio queda en la
trazabilidad del radicado con el nombre de quien subió el archivo.
"""

import io
import re
import unicodedata
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from app.core.autorizacion import validar_permiso
from app.core.zona_horaria import utc_a_bogota
from app.repositories.correspondencia_repo import CorrespondenciaRepositorio
from app.services.correspondencia_service import CorrespondenciaService

PERMISO_CARGUE_MASIVO = "correspondencia.cargue_masivo"

COLUMNAS = ["Radicado", "Fecha respuesta", "Estado", "Comentario"]
MAX_FILAS = 1000
ESTADOS_ABIERTOS = {"pendiente", "en_tramite", "en_revision"}
PREFIJO_COMENTARIO = "[Cargue masivo]"

_PATRON_CODIGO = re.compile(r"^[A-Z0-9\-_.]+$")
_SEP_ESTADO = re.compile(r"[\s;,]+")
_SEP_RADICADO = re.compile(r"[\r\n;,]+")
_FORMATOS_FECHA = (
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
)

ACCION_RESPUESTA = "respuesta"
ACCION_ARCHIVAR = "archivar"
ACCION_TRASLADO = "traslado"
ACCION_OMITIR = "omitir"
ACCION_ERROR = "error"


class ErrorFormatoCargue(Exception):
    """El archivo no cumple el formato: se rechaza completo."""


def _sin_tildes(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalizar_encabezado(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_tildes(str(texto)).strip().lower())


_ENCABEZADOS_ESPERADOS = {_normalizar_encabezado(c): c for c in COLUMNAS}


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float):
        if pd.isna(valor):
            return ""
        if valor.is_integer():
            return str(int(valor))
    return str(valor).strip()


def clasificar_estado(texto: str):
    """Interpreta la celda Estado.

    Retorna (accion, valor, mensaje). Lanza ErrorFormatoCargue si la celda
    trae más de un código (se rechaza todo el archivo).
    """
    t = _texto(texto)
    if not t:
        return ACCION_OMITIR, None, "Estado vacío"
    norm = _sin_tildes(t).lower()
    if norm.startswith("borrador"):
        return ACCION_OMITIR, None, "Borrador"
    if norm.startswith("archiv"):
        return ACCION_ARCHIVAR, None, None
    if norm.startswith("traslad"):
        return ACCION_TRASLADO, None, None

    codigos = [c for c in _SEP_ESTADO.split(t) if c]
    if len(codigos) > 1:
        raise ErrorFormatoCargue("trae más de un código en la celda Estado")
    codigo = codigos[0].upper()
    if not _PATRON_CODIGO.match(codigo) or not any(ch.isdigit() for ch in codigo):
        return (
            ACCION_ERROR, None,
            f"Estado no reconocido: «{t}». Use Archivado, Traslado por competencia, "
            "Borrador, vacío o el número de radicado de salida (debe contener números)",
        )
    return ACCION_RESPUESTA, codigo, None


def _parsear_fecha(valor) -> Optional[date]:
    """Devuelve la fecha, None si viene vacía; lanza ValueError si es inválida."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (datetime, pd.Timestamp)):
        return valor.date()
    if isinstance(valor, date):
        return valor
    t = _texto(valor)
    if not t:
        return None
    for fmt in _FORMATOS_FECHA:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha de respuesta inválida: «{t}» (use dd/mm/aaaa)")


class CargueMasivoCorrespondenciaService:
    def __init__(self) -> None:
        self.repo = CorrespondenciaRepositorio()
        self.corr = CorrespondenciaService()

    # ------------------------------------------------------------------
    # Lectura y validación del archivo (todo o nada)
    # ------------------------------------------------------------------
    def leer_archivo(self, nombre_archivo: str, contenido: bytes) -> List[Dict]:
        """Lee y valida el archivo. Lanza ErrorFormatoCargue si algo del formato falla."""
        if not contenido:
            raise ErrorFormatoCargue("El archivo está vacío.")
        ext = (nombre_archivo or "").lower().rsplit(".", 1)[-1]
        try:
            if ext in ("xlsx", "xlsm"):
                df = self._leer_excel(contenido)
            elif ext in ("csv", "txt"):
                df = self._leer_texto(contenido)
            else:
                raise ErrorFormatoCargue("Formato no soportado. Use .xlsx, .csv o .txt.")
        except ErrorFormatoCargue:
            raise
        except Exception:
            raise ErrorFormatoCargue("No se pudo leer el archivo. Verifique que no esté dañado y que use el formato de la plantilla.")

        df = self._validar_columnas(df)
        df = df[~df.apply(lambda f: all(_texto(v) == "" for v in f), axis=1)]
        if df.empty:
            raise ErrorFormatoCargue("El archivo no tiene filas con datos.")
        if len(df) > MAX_FILAS:
            raise ErrorFormatoCargue(f"El archivo tiene {len(df)} filas; el máximo por cargue es {MAX_FILAS}.")

        filas: List[Dict] = []
        multiples: List[str] = []
        for idx, fila in df.iterrows():
            n_fila = int(idx) + 2  # fila real en el archivo (encabezado = 1)
            radicado_crudo = _texto(fila["Radicado"])
            try:
                if len([c for c in _SEP_RADICADO.split(radicado_crudo) if c.strip()]) > 1:
                    raise ErrorFormatoCargue("trae más de un radicado en la celda Radicado")
                accion, valor, mensaje = clasificar_estado(fila["Estado"])
            except ErrorFormatoCargue as e:
                multiples.append(f"fila {n_fila}: {e}")
                continue
            filas.append({
                "fila": n_fila,
                "radicado": radicado_crudo,
                "fecha_raw": fila["Fecha respuesta"],
                "accion": accion,
                "valor": valor,
                "mensaje": mensaje,
                "comentario": _texto(fila["Comentario"]),
            })
        if multiples:
            detalle = "; ".join(multiples[:10]) + ("…" if len(multiples) > 10 else "")
            raise ErrorFormatoCargue(
                "Archivo rechazado: cada celda debe tener un solo código. Corrija y vuelva a subirlo. " + detalle
            )
        return filas

    @staticmethod
    def _leer_excel(contenido: bytes) -> pd.DataFrame:
        xls = pd.ExcelFile(io.BytesIO(contenido))
        hoja = "Formato" if "Formato" in xls.sheet_names else xls.sheet_names[0]
        return pd.read_excel(xls, sheet_name=hoja, dtype=object, na_filter=False)

    @staticmethod
    def _leer_texto(contenido: bytes) -> pd.DataFrame:
        try:
            texto = contenido.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = contenido.decode("latin-1")
        return pd.read_csv(io.StringIO(texto), sep=None, engine="python", dtype=str, na_filter=False)

    @staticmethod
    def _validar_columnas(df: pd.DataFrame) -> pd.DataFrame:
        # Descarta columnas sin encabezado y sin datos (típico de Excel)
        vacias = [c for c in df.columns if str(c).startswith("Unnamed") and all(_texto(v) == "" for v in df[c])]
        df = df.drop(columns=vacias)
        mapa, desconocidas = {}, []
        for col in df.columns:
            clave = _normalizar_encabezado(col)
            if clave in _ENCABEZADOS_ESPERADOS:
                mapa[col] = _ENCABEZADOS_ESPERADOS[clave]
            else:
                desconocidas.append(str(col))
        faltan = [c for c in COLUMNAS if c not in mapa.values()]
        if faltan or desconocidas or len(mapa) != len(df.columns):
            partes = []
            if faltan:
                partes.append("faltan las columnas: " + ", ".join(faltan))
            if desconocidas:
                partes.append("columnas no reconocidas: " + ", ".join(desconocidas))
            raise ErrorFormatoCargue(
                "El formato del archivo no es correcto (" + "; ".join(partes) + "). "
                "Debe tener exactamente las columnas: " + ", ".join(COLUMNAS) + ". Descargue la plantilla."
            )
        return df.rename(columns=mapa).reset_index(drop=True)

    # ------------------------------------------------------------------
    # Aplicación
    # ------------------------------------------------------------------
    def procesar(
        self,
        filas: List[Dict],
        permisos_usuario: List[str],
        usuario_nombre: str,
        usuario_id: Optional[str],
    ) -> Dict:
        validar_permiso(permisos_usuario, PERMISO_CARGUE_MASIVO)

        hoy_bogota = utc_a_bogota(datetime.now(timezone.utc)).date()
        resumen = {"leidas": len(filas), "actualizados": 0, "errores": [], "omitidos": []}
        vistos = set()

        def error(f, motivo):
            resumen["errores"].append({"Fila": f["fila"], "Radicado": f["radicado"], "Motivo": motivo})

        def omitido(f, motivo):
            resumen["omitidos"].append({"Fila": f["fila"], "Radicado": f["radicado"], "Motivo": motivo})

        for f in filas:
            try:
                if f["accion"] == ACCION_OMITIR:
                    omitido(f, f["mensaje"])
                    continue
                if f["accion"] == ACCION_ERROR:
                    error(f, f["mensaje"])
                    continue
                if not f["radicado"]:
                    error(f, "Radicado vacío")
                    continue

                numero = f["radicado"].replace(" ", "").upper()
                if numero in vistos:
                    error(f, "Radicado repetido en el archivo")
                    continue
                vistos.add(numero)

                doc = self.repo.buscar_por_radicado(numero)
                if not doc:
                    error(f, "El radicado no existe en el sistema")
                    continue
                estado = doc.get("estado_actual")
                if estado not in ESTADOS_ABIERTOS:
                    omitido(f, f"Ya cerrado ({estado.replace('_', ' ')})")
                    continue

                id_doc = str(doc["_id"])
                if f["accion"] == ACCION_RESPUESTA:
                    try:
                        fecha = _parsear_fecha(f["fecha_raw"]) or hoy_bogota
                    except ValueError as e:
                        error(f, str(e))
                        continue
                    if fecha > hoy_bogota:
                        error(f, "La fecha de respuesta no puede ser futura")
                        continue
                    fecha_dt = datetime(fecha.year, fecha.month, fecha.day, tzinfo=timezone.utc)
                    base = f["comentario"] or "Se da respuesta"
                    comentario = (
                        f"{PREFIJO_COMENTARIO} {base} (respuesta {f['valor']}, "
                        f"fecha de respuesta {fecha.strftime('%d/%m/%Y')})"
                    )
                    ok = self.corr.dar_respuesta(
                        id_doc, f["valor"], usuario_nombre, comentario,
                        fecha_respuesta=fecha_dt, usuario_ejecutor_id=usuario_id,
                    )
                elif f["accion"] == ACCION_ARCHIVAR:
                    comentario = f"{PREFIJO_COMENTARIO} {f['comentario'] or 'Se archivó el radicado'}"
                    ok = self.corr.archivar(id_doc, usuario_nombre, comentario, usuario_ejecutor_id=usuario_id)
                else:
                    comentario = f"{PREFIJO_COMENTARIO} {f['comentario'] or 'Traslado por competencia'}"
                    ok = self.corr.cambiar_estado(
                        id_doc, "traslado_competencia", usuario_nombre, comentario, usuario_ejecutor_id=usuario_id
                    )

                if ok:
                    resumen["actualizados"] += 1
                else:
                    error(f, "No se pudo actualizar el radicado")
            except Exception as e:  # una fila con problemas no frena las demás
                error(f, f"Error inesperado: {e}")
        return resumen

    # ------------------------------------------------------------------
    # Plantilla de muestra
    # ------------------------------------------------------------------
    @staticmethod
    def plantilla_excel() -> bytes:
        import xlsxwriter

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        encab = wb.add_format({"bold": True, "bg_color": "#FF8C00", "font_color": "#FFFFFF", "border": 1})
        texto = wb.add_format({"num_format": "@", "border": 1, "text_wrap": True, "valign": "top"})
        negrita = wb.add_format({"bold": True})
        envuelto = wb.add_format({"text_wrap": True, "valign": "top"})

        ws = wb.add_worksheet("Formato")
        for i, c in enumerate(COLUMNAS):
            ws.write(0, i, c, encab)
        ejemplos = [
            ("2026-EJEMPLO-001", "05/11/2026", "2026_VUVRAZ_200000", "Respuesta enviada al peticionario"),
            ("2026-EJEMPLO-002", "", "Archivado", "Se archiva por solicitud del peticionario"),
            ("2026-EJEMPLO-003", "", "Traslado por competencia", "Se traslada al Ministerio de Transporte"),
            ("2026-EJEMPLO-004", "", "Borrador", "Aún en elaboración: este renglón se omite"),
            ("2026-EJEMPLO-005", "", "", "Estado vacío: este renglón se omite"),
        ]
        for r, fila in enumerate(ejemplos, start=1):
            for c, v in enumerate(fila):
                ws.write_string(r, c, v, texto)
        ws.set_column(0, 0, 24)
        ws.set_column(1, 1, 18)
        ws.set_column(2, 2, 30)
        ws.set_column(3, 3, 55)
        ws.freeze_panes(1, 0)

        wi = wb.add_worksheet("Instrucciones")
        wi.set_column(0, 0, 110)
        lineas = [
            ("INSTRUCCIONES DEL CARGUE MASIVO DE CORRESPONDENCIA", negrita),
            ("", None),
            ("1. Use la hoja «Formato». Conserve exactamente los 4 encabezados: Radicado, Fecha respuesta, Estado, Comentario. Borre las filas de ejemplo antes de subir su información.", envuelto),
            ("2. Radicado: debe ser un radicado que ya exista en el sistema y esté abierto (pendiente, en trámite o en revisión). Los inexistentes dan error; los ya cerrados se ignoran y se informan.", envuelto),
            ("3. Fecha respuesta: opcional, formato dd/mm/aaaa. Solo se usa cuando hay respuesta. Si va vacía se usa la fecha de hoy. No puede ser futura.", envuelto),
            ("4. Estado, según lo que escriba:", negrita),
            ("   • Un número de radicado de salida (ej. 2026_VUVRAZ_200000) → el radicado queda RESPONDIDO con ese número. Debe contener números y ser un solo código.", envuelto),
            ("   • Archivado → el radicado queda ARCHIVADO.", envuelto),
            ("   • Traslado / Traslado competencia / Traslado por competencia → queda TRASLADADO POR COMPETENCIA.", envuelto),
            ("   • Borrador (o vacío) → el renglón se omite y no se actualiza nada.", envuelto),
            ("5. Comentario: texto libre. Se guarda en el historial del radicado. Si va vacío se usa uno por defecto.", envuelto),
            ("6. Una celda NUNCA puede traer dos códigos (separados por Enter, espacio, coma o punto y coma). Si ocurre, se rechaza el archivo completo hasta que se corrija.", envuelto),
            ("7. Si faltan columnas, sobran columnas o los encabezados no coinciden, se rechaza el archivo completo.", envuelto),
            ("8. Máximo 1.000 filas por cargue. Se aceptan .xlsx, .csv y .txt.", envuelto),
            ("9. Cada actualización queda registrada en la trazabilidad del radicado con su nombre y la fecha y hora del cargue.", envuelto),
        ]
        for r, (txt, fmt) in enumerate(lineas):
            if fmt:
                wi.write(r, 0, txt, fmt)
        wb.close()
        return buf.getvalue()
