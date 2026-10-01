"""Cargue masivo de pagos de contratos desde el Excel de tesorería (balances de pago).

Ver docs/superpowers/specs/2026-09-30-cargue-pagos-excel-design.md para el diseño completo.
"""

import math
from datetime import datetime, timezone

import pandas as pd

from app.repositories.usuario_repo import UsuarioRepositorio
from app.services.auditoria_service import AuditoriaService
from app.services.certificacion_service import CertificacionService
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


CAT_VALIDO = "valido"
CAT_DUPLICADO_INTERNO = "duplicado_interno"
CAT_USUARIO_NO_ENCONTRADO = "usuario_no_encontrado"
CAT_SIN_CONTRATO_ACTIVO = "sin_contrato_activo"
CAT_DATO_INVALIDO = "dato_invalido"
CAT_YA_EXISTE = "ya_existe_en_bd"
CAT_EXCEDE_LIMITE = "excede_limite_pagos"

MOTIVOS = {
    CAT_USUARIO_NO_ENCONTRADO: "No existe ningún usuario con esta cédula",
    CAT_SIN_CONTRATO_ACTIVO: "El usuario no tiene ningún contrato activo",
    CAT_DATO_INVALIDO: "Fecha o valores monetarios inválidos o incompletos",
    CAT_DUPLICADO_INTERNO: "Fila duplicada dentro del mismo archivo (misma cédula, fecha y valor neto)",
    CAT_YA_EXISTE: "Ya existe un pago igual registrado en este contrato",
    CAT_EXCEDE_LIMITE: "El contrato superaría el límite de 20 pagos; no se carga ninguno de este lote",
    CAT_VALIDO: "Listo para cargar",
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


def _ultimo_contrato_activo(contratos: list) -> dict:
    """Contrato activo hoy del usuario (incluye período de gracia), usando el
    classmethod puro CertificacionService._contrato_vigente para no instanciar el
    servicio ni forzar una conexión a Mongo.

    A diferencia de CertificacionService._ultimo_contrato_usuario (que hace fallback
    al contrato más reciente para generar formatos históricos), aquí NO se hace ese
    fallback: un contrato vencido no es apto para recibir pagos nuevos, así que debe
    clasificarse como sin_contrato_activo."""
    return CertificacionService._contrato_vigente(contratos)


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
                "categoria": None,
                "motivo": None,
                "numero_pago": numero_pago,
                "fecha_pago": fecha_pago,
                "valor_bruto_pago": valor_bruto,
                "deducciones_pago": deducciones,
                "valor_neto_pago": valor_neto,
                "concepto": concepto,
                "seleccionable": False,
            }

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
                filas.append(fila)
                continue

            clave_interna = (cedula, fecha_pago, valor_neto)
            if clave_interna in vistos_internos:
                fila["categoria"] = CAT_DUPLICADO_INTERNO
                fila["motivo"] = MOTIVOS[CAT_DUPLICADO_INTERNO]
                filas.append(fila)
                continue
            vistos_internos.add(clave_interna)

            usuario = por_cedula.get(cedula)
            if not usuario:
                fila["categoria"] = CAT_USUARIO_NO_ENCONTRADO
                fila["motivo"] = MOTIVOS[CAT_USUARIO_NO_ENCONTRADO]
                filas.append(fila)
                continue
            fila["nombre"] = usuario.get("nombre_completo")
            fila["id_usuario"] = str(usuario["_id"])

            contrato = _ultimo_contrato_activo(usuario.get("contratos") or [])
            if not contrato or not contrato.get("numero"):
                fila["categoria"] = CAT_SIN_CONTRATO_ACTIVO
                fila["motivo"] = MOTIVOS[CAT_SIN_CONTRATO_ACTIVO]
                filas.append(fila)
                continue
            fila["numero_contrato"] = contrato["numero"]

            pagos_actuales = contrato.get("pagos") or []
            existentes = {
                (p["numero_pago"], _fecha_utc(p["fecha_pago"]), p["valor_neto_pago"])
                for p in pagos_actuales
            }
            if (numero_pago, _fecha_utc(fecha_pago), valor_neto) in existentes:
                fila["categoria"] = CAT_YA_EXISTE
                fila["motivo"] = MOTIVOS[CAT_YA_EXISTE]
                filas.append(fila)
                continue

            grupo = (fila["id_usuario"], fila["numero_contrato"])
            candidatos_por_grupo.setdefault(grupo, {"cupo_actual": len(pagos_actuales), "filas": []})
            candidatos_por_grupo[grupo]["filas"].append(fila)
            filas.append(fila)

        for grupo, info in candidatos_por_grupo.items():
            total_tras_merge = info["cupo_actual"] + len(info["filas"])
            if total_tras_merge > MAX_PAGOS_POR_CONTRATO:
                for fila in info["filas"]:
                    fila["categoria"] = CAT_EXCEDE_LIMITE
                    fila["motivo"] = MOTIVOS[CAT_EXCEDE_LIMITE]
            else:
                for fila in info["filas"]:
                    fila["categoria"] = CAT_VALIDO
                    fila["motivo"] = MOTIVOS[CAT_VALIDO]
                    fila["seleccionable"] = True

        resumen = {}
        for fila in filas:
            resumen[fila["categoria"]] = resumen.get(fila["categoria"], 0) + 1

        return {"resumen": resumen, "filas": filas}

    def confirmar_carga(
        self, filas_seleccionadas: list[dict], usuario_que_carga: str, nombre_archivo: str = ""
    ) -> dict:
        candidatas = [f for f in filas_seleccionadas if f["categoria"] == CAT_VALIDO]

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
                if not CertificacionService._contrato_vigente([contrato]):
                    raise ValueError("El contrato ya no está activo.")

                pagos_actuales = contrato.get("pagos") or []
                existentes = {
                    (p["numero_pago"], _fecha_utc(p["fecha_pago"]), p["valor_neto_pago"])
                    for p in pagos_actuales
                }

                pagos_nuevos = []
                for fila in filas_grupo:
                    clave_pago = (
                        fila["numero_pago"],
                        _fecha_utc(fila["fecha_pago"]),
                        fila["valor_neto_pago"],
                    )
                    if clave_pago in existentes:
                        continue
                    pagos_nuevos.append({
                        "numero_pago": fila["numero_pago"],
                        "fecha_pago": fila["fecha_pago"],
                        "valor_bruto_pago": fila["valor_bruto_pago"],
                        "deducciones_pago": fila["deducciones_pago"],
                        "valor_neto_pago": fila["valor_neto_pago"],
                    })
                    existentes.add(clave_pago)

                if not pagos_nuevos:
                    continue  # todos ya existían; nada que hacer, no es un fallo

                pagos_final = pagos_actuales + pagos_nuevos
                if len(pagos_final) > MAX_PAGOS_POR_CONTRATO:
                    raise ValueError(
                        f"El contrato superaría el límite de {MAX_PAGOS_POR_CONTRATO} pagos."
                    )

                valor_total_pagado = sum(p["valor_bruto_pago"] for p in pagos_final)
                valor_contrato = int(contrato.get("valor") or 0)

                contrato_actualizado = dict(contrato)
                contrato_actualizado["pagos"] = pagos_final
                contrato_actualizado["valor_total_pagado"] = valor_total_pagado
                contrato_actualizado["valor_total_por_pagar_contrato"] = abs(
                    valor_contrato - valor_total_pagado
                )

                self.repositorio.editar_contrato_en_usuario(id_usuario, numero_contrato, contrato_actualizado)
                self.auditoria.registrar_accion(
                    usuario=usuario_que_carga,
                    accion="cargue_pagos_excel",
                    recurso=f"usuario:{id_usuario}:contrato:{numero_contrato}",
                    detalle={"pagos_agregados": len(pagos_nuevos), "archivo": nombre_archivo},
                )
                ok.append({
                    "id_usuario": id_usuario,
                    "numero_contrato": numero_contrato,
                    "agregados": len(pagos_nuevos),
                })
            except Exception as e:
                fallidos.append({
                    "id_usuario": id_usuario,
                    "numero_contrato": numero_contrato,
                    "motivo": str(e),
                })

        return {"ok": ok, "fallidos": fallidos}
