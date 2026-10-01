"""Cargue masivo de pagos de contratos desde el Excel de tesorería (balances de pago).

Ver docs/cargue_pagos_excel.md para el comportamiento vigente. El diseño original
(docs/superpowers/specs/2026-09-30-cargue-pagos-excel-design.md) era solo aditivo y
cargaba al contrato activo; hoy el contrato se toma del propio Excel y los pagos
existentes se sobrescriben.
"""

import math
import re
from datetime import datetime, timezone

import pandas as pd

from app.core.balance_contrato import calcular_balance_pagos
from app.repositories.usuario_repo import UsuarioRepositorio
from app.services.auditoria_service import AuditoriaService
from app.services.usuario_service import UsuarioService

MAX_PAGOS_POR_CONTRATO = 20

TIPO_IDENTIFICACION_CEDULA = "Cédula de Ciudadanía"

# Columna AW del Excel de tesorería: "<número de contrato>/<año del contrato>"
# (ej. "2570/2026"; también llega con guion, con prefijo "SA 0699/2026" o con el
# año mal digitado "2289/20255").
COLUMNA_CONTRATO = "Num Doc Soporte Compromiso"

COLUMNAS_REQUERIDAS = [
    "Tipo Identificacion",
    "Identificacion",
    "Numero Documento",
    "Fecha de pago",
    "Valor Bruto",
    "Valor Deducciones",
    "Valor Neto",
    COLUMNA_CONTRATO,
]

_PATRON_CONTRATO = re.compile(r"(\d+)\s*[/-]+\s*(\d{4})")

# Fechas del contrato cuyo año puede aparecer como "año del contrato" en tesorería
# (un contrato firmado en diciembre e iniciado en enero figura con el año de firma).
_CAMPOS_ANIO_CONTRATO = ("firma_cps_secop", "fecha_inicio")


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


def extraer_contrato_y_anio(crudo) -> tuple[str, int] | None:
    """Lee 'Num Doc Soporte Compromiso' ('<número>/<año>', ej. '2570/2026') y
    devuelve (número sin ceros a la izquierda, año), o None si no trae ese formato."""
    coincidencia = _PATRON_CONTRATO.search(_texto_o_vacio(crudo))
    if not coincidencia:
        return None
    return _numero_sin_ceros(coincidencia.group(1)), int(coincidencia.group(2))


CAT_VALIDO = "valido"
CAT_ACTUALIZA = "actualiza_existente"
CAT_DUPLICADO_INTERNO = "duplicado_interno"
CAT_USUARIO_NO_ENCONTRADO = "usuario_no_encontrado"
CAT_CONTRATO_NO_ENCONTRADO = "contrato_no_encontrado"
CAT_DATO_INVALIDO = "dato_invalido"
CAT_YA_EXISTE = "ya_existe_en_bd"
CAT_EXCEDE_LIMITE = "excede_limite_pagos"

# Únicas categorías que confirmar_carga escribe en la base de datos.
CATEGORIAS_CARGABLES = (CAT_VALIDO, CAT_ACTUALIZA)

MOTIVOS = {
    CAT_USUARIO_NO_ENCONTRADO: "No existe ningún usuario con esta cédula",
    CAT_CONTRATO_NO_ENCONTRADO: "El usuario no tiene registrado el contrato indicado en el Excel",
    CAT_DATO_INVALIDO: "Fecha o valores monetarios inválidos o incompletos",
    CAT_DUPLICADO_INTERNO: "Comprobante de pago repetido dentro del mismo archivo para el mismo contrato",
    CAT_YA_EXISTE: "El pago ya está registrado en el contrato con los mismos datos",
    CAT_EXCEDE_LIMITE: "El contrato superaría el límite de 20 pagos; no se agregan pagos nuevos de este lote",
    CAT_VALIDO: "Pago nuevo, listo para cargar",
    CAT_ACTUALIZA: "Sobrescribe un pago ya registrado en el contrato",
}


def _fecha_utc(fecha):
    """Normaliza un datetime a tz-aware UTC sin importar si llegó naive (como lo
    retorna PyMongo al leer una fecha de un documento existente, ya que el
    MongoClient de app/db/mongo.py no usa tz_aware=True) o ya tz-aware (como lo
    produce limpiar_fecha_pago para datos recién leídos del Excel). Mismo patrón
    que usuario_service.py y certificacion_service.py para esta misma situación."""
    if fecha is None:
        return None
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc)


def _texto_o_vacio(crudo) -> str:
    """Convierte una celda de texto del Excel a string limpio, tratando como
    vacío tanto None como un NaN de pandas (float) y la literal 'nan' que
    resultaría de hacer str() sobre ese NaN sin esta guarda."""
    if crudo is None:
        return ""
    if isinstance(crudo, float) and math.isnan(crudo):
        return ""
    texto = str(crudo).strip()
    if texto.lower() == "nan":
        return ""
    return texto


def _numero_sin_ceros(numero) -> str:
    return str(numero or "").strip().lstrip("0") or "0"


def _anios_contrato(contrato: dict) -> set:
    """Años en los que tesorería puede referenciar el contrato. Las fechas de
    contrato se guardan a medianoche UTC, así que el año se lee sin convertir de
    zona horaria (igual que los formatos de certificacion_service.py)."""
    return {contrato[campo].year for campo in _CAMPOS_ANIO_CONTRATO if contrato.get(campo)}


def _buscar_contrato(contratos: list, numero: str, anio: int) -> dict | None:
    """Contrato del usuario que corresponde al '<número>-<año>' del Excel, sin
    importar si está vigente, finalizado o en período de gracia. Un contrato sin
    ninguna fecha registrada se acepta solo por número."""
    for contrato in contratos:
        if _numero_sin_ceros(contrato.get("numero")) != numero:
            continue
        anios = _anios_contrato(contrato)
        if not anios or anio in anios:
            return contrato
    return None


def _pago_desde_fila(fila: dict) -> dict:
    return {
        "numero_pago": fila["numero_pago"],
        "fecha_pago": fila["fecha_pago"],
        "valor_bruto_pago": fila["valor_bruto_pago"],
        "deducciones_pago": fila["deducciones_pago"],
        "valor_neto_pago": fila["valor_neto_pago"],
    }


def _pagos_iguales(a: dict, b: dict) -> bool:
    return (
        a.get("numero_pago") == b.get("numero_pago")
        and _fecha_utc(a.get("fecha_pago")) == _fecha_utc(b.get("fecha_pago"))
        and a.get("valor_bruto_pago") == b.get("valor_bruto_pago")
        and a.get("deducciones_pago") == b.get("deducciones_pago")
        and a.get("valor_neto_pago") == b.get("valor_neto_pago")
    )


def _planear_merge(pagos_actuales: list, filas: list) -> list:
    """Para cada fila devuelve el índice del pago existente que sobrescribe, o
    None si es un pago nuevo. Un pago existente se reconoce solo por su
    numero_pago (el comprobante de tesorería): fecha + valor neto no sirve como
    identidad porque un contrato recibe varios comprobantes distintos el mismo
    día por el mismo valor. Cada pago existente se asigna a una sola fila."""
    destinos = [None] * len(filas)
    usados = set()

    for pos, fila in enumerate(filas):
        for i, pago in enumerate(pagos_actuales):
            if i not in usados and pago.get("numero_pago") == fila["numero_pago"]:
                destinos[pos] = i
                usados.add(i)
                break

    return destinos


def _clave_orden_pago(pago: dict):
    return _fecha_utc(pago.get("fecha_pago")) or datetime.min.replace(tzinfo=timezone.utc)


class CarguePagosService:
    def __init__(self, repositorio=None):
        self.repositorio = repositorio or UsuarioRepositorio()
        self.auditoria = AuditoriaService()

    def procesar_archivo(self, archivo) -> dict:
        df = pd.read_excel(archivo, header=0, engine="openpyxl")
        faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
        if faltantes:
            raise ValueError(
                "El archivo no tiene las columnas esperadas. Faltan: " + ", ".join(faltantes)
            )

        usuarios = self.repositorio.listar()
        por_cedula = {u["numero_documento"]: u for u in usuarios if u.get("numero_documento")}

        filas = []
        vistos_internos = set()
        candidatos_por_grupo = {}

        for _, registro in df.iterrows():
            tipo_identificacion = _texto_o_vacio(registro.get("Tipo Identificacion"))
            if tipo_identificacion != TIPO_IDENTIFICACION_CEDULA:
                continue

            cedula = limpiar_cedula(registro.get("Identificacion"))
            numero_pago = limpiar_numero_pago(registro.get("Numero Documento"))
            fecha_pago = limpiar_fecha_pago(registro.get("Fecha de pago"))
            valor_bruto = limpiar_valor_monetario(registro.get("Valor Bruto"))
            deducciones = limpiar_valor_monetario(registro.get("Valor Deducciones"))
            valor_neto = limpiar_valor_monetario(registro.get("Valor Neto"))
            contrato_excel = _texto_o_vacio(registro.get(COLUMNA_CONTRATO))
            fecha_hora_pago = _texto_o_vacio(registro.get("Fecha de pago"))
            concepto = (
                _texto_o_vacio(registro.get("Concepto Pago"))
                or _texto_o_vacio(registro.get("Objeto del Compromiso"))
            )

            fila = {
                "id": len(filas),
                "cedula": cedula,
                "nombre": None,
                "id_usuario": None,
                "numero_contrato": None,
                "contrato_excel": contrato_excel,
                "categoria": None,
                "motivo": None,
                "numero_pago": numero_pago,
                "fecha_pago": fecha_pago,
                # 'YYYY-MM-DD HH:MM:SS' tal como llega: ordena los pagos de un mismo día.
                "orden_pago": fecha_hora_pago,
                "estado": _texto_o_vacio(registro.get("Estado")),
                "valor_bruto_pago": valor_bruto,
                "deducciones_pago": deducciones,
                "valor_neto_pago": valor_neto,
                "concepto": concepto,
                "seleccionable": False,
            }
            filas.append(fila)

            if (
                cedula is None
                or numero_pago is None
                or fecha_pago is None
                or valor_bruto is None
                or deducciones is None
                or valor_neto is None
                or valor_bruto < 0
                or deducciones < 0
                or valor_neto < 0
            ):
                fila["categoria"] = CAT_DATO_INVALIDO
                fila["motivo"] = MOTIVOS[CAT_DATO_INVALIDO]
                continue

            usuario = por_cedula.get(cedula)
            if not usuario:
                fila["categoria"] = CAT_USUARIO_NO_ENCONTRADO
                fila["motivo"] = MOTIVOS[CAT_USUARIO_NO_ENCONTRADO]
                continue
            fila["nombre"] = usuario.get("nombre_completo")
            fila["id_usuario"] = str(usuario["_id"])

            referencia = extraer_contrato_y_anio(contrato_excel)
            if not referencia:
                fila["categoria"] = CAT_CONTRATO_NO_ENCONTRADO
                fila["motivo"] = (
                    f"'{COLUMNA_CONTRATO}' no trae un contrato con formato número/año"
                )
                continue
            numero_excel, anio_excel = referencia
            contrato = _buscar_contrato(usuario.get("contratos") or [], numero_excel, anio_excel)
            if not contrato:
                fila["categoria"] = CAT_CONTRATO_NO_ENCONTRADO
                fila["motivo"] = (
                    f"El usuario no tiene registrado el contrato {numero_excel} de {anio_excel}"
                )
                continue
            fila["numero_contrato"] = contrato["numero"]

            grupo = (fila["id_usuario"], fila["numero_contrato"])
            clave_interna = (grupo, numero_pago)
            if clave_interna in vistos_internos:
                fila["categoria"] = CAT_DUPLICADO_INTERNO
                fila["motivo"] = MOTIVOS[CAT_DUPLICADO_INTERNO]
                continue
            vistos_internos.add(clave_interna)

            candidatos_por_grupo.setdefault(
                grupo, {"pagos_actuales": contrato.get("pagos") or [], "filas": []}
            )
            candidatos_por_grupo[grupo]["filas"].append(fila)

        for info in candidatos_por_grupo.values():
            pagos_actuales = info["pagos_actuales"]
            destinos = _planear_merge(pagos_actuales, info["filas"])
            total_tras_merge = len(pagos_actuales) + destinos.count(None)
            excede = total_tras_merge > MAX_PAGOS_POR_CONTRATO

            for fila, destino in zip(info["filas"], destinos):
                if destino is None:
                    categoria = CAT_EXCEDE_LIMITE if excede else CAT_VALIDO
                elif _pagos_iguales(pagos_actuales[destino], _pago_desde_fila(fila)):
                    categoria = CAT_YA_EXISTE
                else:
                    categoria = CAT_ACTUALIZA
                fila["categoria"] = categoria
                fila["motivo"] = MOTIVOS[categoria]
                fila["seleccionable"] = categoria in CATEGORIAS_CARGABLES

        resumen = {}
        for fila in filas:
            resumen[fila["categoria"]] = resumen.get(fila["categoria"], 0) + 1

        return {"resumen": resumen, "filas": filas}

    def confirmar_carga(
        self, filas_seleccionadas: list[dict], usuario_que_carga: str, nombre_archivo: str = ""
    ) -> dict:
        candidatas = [f for f in filas_seleccionadas if f["categoria"] in CATEGORIAS_CARGABLES]

        grupos = {}
        for fila in candidatas:
            clave = (fila["id_usuario"], fila["numero_contrato"])
            grupos.setdefault(clave, []).append(fila)

        ok = []
        fallidos = []

        for (id_usuario, numero_contrato), filas_grupo in grupos.items():
            try:
                usuario = self.repositorio.buscar_por_id(id_usuario)
                if not usuario:
                    raise ValueError("El usuario ya no existe.")
                contrato = next(
                    (c for c in usuario.get("contratos") or [] if c.get("numero") == numero_contrato),
                    None,
                )
                if not contrato:
                    raise ValueError("El contrato ya no existe para este usuario.")

                # Se replanea contra el estado actual de la BD (no el de la vista
                # previa), por si los pagos del contrato cambiaron en el ínterin.
                pagos_actuales = contrato.get("pagos") or []
                filas_grupo = sorted(filas_grupo, key=lambda f: f.get("orden_pago") or "")
                destinos = _planear_merge(pagos_actuales, filas_grupo)

                pagos_final = list(pagos_actuales)
                agregados = 0
                actualizados = 0
                for fila, destino in zip(filas_grupo, destinos):
                    pago = _pago_desde_fila(fila)
                    if destino is None:
                        pagos_final.append(pago)
                        agregados += 1
                    elif not _pagos_iguales(pagos_actuales[destino], pago):
                        pagos_final[destino] = {**pagos_actuales[destino], **pago}
                        actualizados += 1

                if not agregados and not actualizados:
                    continue  # todos ya estaban idénticos; nada que hacer, no es un fallo

                if len(pagos_final) > MAX_PAGOS_POR_CONTRATO:
                    raise ValueError(
                        f"El contrato superaría el límite de {MAX_PAGOS_POR_CONTRATO} pagos."
                    )

                # La fecha de pago define el orden de los pagos del contrato (el
                # orden es estable: los de un mismo día conservan su hora de pago).
                pagos_final.sort(key=_clave_orden_pago)

                contrato_actualizado = dict(contrato)
                contrato_actualizado["pagos"] = pagos_final
                (
                    contrato_actualizado["valor_total_pagado"],
                    contrato_actualizado["valor_total_por_pagar_contrato"],
                ) = calcular_balance_pagos(contrato.get("valor"), pagos_final)

                self.repositorio.editar_contrato_en_usuario(id_usuario, numero_contrato, contrato_actualizado)
                self.auditoria.registrar_accion(
                    usuario=usuario_que_carga,
                    accion="cargue_pagos_excel",
                    recurso=f"usuario:{id_usuario}:contrato:{numero_contrato}",
                    detalle={
                        "pagos_agregados": agregados,
                        "pagos_actualizados": actualizados,
                        "archivo": nombre_archivo,
                    },
                )
                ok.append({
                    "id_usuario": id_usuario,
                    "numero_contrato": numero_contrato,
                    "agregados": agregados,
                    "actualizados": actualizados,
                })
            except Exception as e:
                fallidos.append({
                    "id_usuario": id_usuario,
                    "numero_contrato": numero_contrato,
                    "motivo": str(e),
                })

        return {"ok": ok, "fallidos": fallidos}
