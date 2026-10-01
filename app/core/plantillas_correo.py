"""Plantilla HTML del correo diario de notificaciones (resumen por usuario).

Funciones puras: reciben el resumen ya calculado y devuelven asunto, HTML y
texto plano. El correo no lleva ningún enlace: no hay etiquetas <a>, y a los
textos libres (asunto de un radicado) se les quita todo lo que un cliente de
correo convertiría en enlace por su cuenta.
"""

import re
from datetime import date
from html import escape

CID_LOGO = "logo_invias"

# Paleta: naranja corporativo INVIAS sobre tonos café y crema (sin blanco puro).
NARANJA = "#FF8C00"
CAFE = "#5D4037"            # encabezado y pie
CAFE_OSCURO = "#3E2723"     # texto principal
CAFE_SUAVE = "#8D6E63"      # texto secundario
FONDO_PAGINA = "#E7DACB"
FONDO_TARJETA = "#FAF4EA"
FONDO_TABLA = "#FFFBF4"
FONDO_CABECERA_TABLA = "#EADBC8"
BORDE = "#D9C7B0"
GRIS_TEXTO = CAFE_OSCURO
GRIS_SUAVE = CAFE_SUAVE

_ROJO = ("#B71C1C", "#FDECEA")
_AMBAR = ("#9A5B00", "#FFF4E0")
_VERDE = ("#1B5E20", "#E8F5E9")
_GRIS = (CAFE_SUAVE, "#EFE4D6")

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

MAX_FILAS_TABLA = 25

_PATRON_ENLACE = re.compile(r"(?:https?://|www\.)\S+|\S+@\S+\.\S+", re.IGNORECASE)


def fecha_larga(fecha: date) -> str:
    return f"{_DIAS[fecha.weekday()]} {fecha.day} de {_MESES[fecha.month - 1]} de {fecha.year}"


def nombre_mes(mes: int) -> str:
    return _MESES[mes - 1]


def texto_seguro(texto, max_largo: int = 90) -> str:
    """Texto libre listo para el correo: sin nada que parezca un enlace o una
    dirección de correo, recortado y con los caracteres HTML escapados."""
    limpio = _PATRON_ENLACE.sub("[enlace omitido]", str(texto or "")).strip()
    limpio = re.sub(r"\s+", " ", limpio)
    if len(limpio) > max_largo:
        limpio = limpio[: max_largo - 1].rstrip() + "…"
    return escape(limpio)


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _etiqueta(texto: str, colores: tuple) -> str:
    color, fondo = colores
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:12px;'
        f'background:{fondo};color:{color};font-size:12px;font-weight:bold;white-space:nowrap;">'
        f"{escape(texto)}</span>"
    )


def _titulo_seccion(texto: str) -> str:
    return (
        f'<tr><td style="padding:22px 28px 8px 28px;">'
        f'<div style="font-size:15px;font-weight:bold;color:{GRIS_TEXTO};'
        f'border-left:4px solid {NARANJA};padding-left:10px;">{escape(texto)}</div></td></tr>'
    )


def _parrafo(html: str) -> str:
    return (
        f'<tr><td style="padding:4px 28px 6px 28px;font-size:14px;line-height:1.5;color:{GRIS_TEXTO};">'
        f"{html}</td></tr>"
    )


def _tabla_radicados(filas: list, colores: tuple, estado_de) -> str:
    celdas_cab = "".join(
        f'<th align="{alineacion}" style="padding:8px 10px;font-size:12px;color:{CAFE};'
        f'background:{FONDO_CABECERA_TABLA};border-bottom:2px solid {BORDE};">{titulo}</th>'
        for titulo, alineacion in (("Radicado", "left"), ("Asunto", "left"), ("Vence", "center"), ("Estado", "center"))
    )
    cuerpo = ""
    for fila in filas[:MAX_FILAS_TABLA]:
        cuerpo += (
            "<tr>"
            f'<td style="padding:8px 10px;font-size:13px;font-weight:bold;color:{GRIS_TEXTO};'
            f'border-bottom:1px solid {BORDE};white-space:nowrap;">{texto_seguro(fila["radicado"], 30)}</td>'
            f'<td style="padding:8px 10px;font-size:13px;color:{GRIS_TEXTO};border-bottom:1px solid {BORDE};">'
            f'{texto_seguro(fila["asunto"])}</td>'
            f'<td align="center" style="padding:8px 10px;font-size:13px;color:{GRIS_TEXTO};'
            f'border-bottom:1px solid {BORDE};white-space:nowrap;">{fila["vence"].strftime("%d/%m/%Y")}</td>'
            f'<td align="center" style="padding:8px 10px;border-bottom:1px solid {BORDE};">'
            f"{_etiqueta(estado_de(fila), colores)}</td>"
            "</tr>"
        )
    restantes = len(filas) - MAX_FILAS_TABLA
    if restantes > 0:
        cuerpo += (
            f'<tr><td colspan="4" style="padding:8px 10px;font-size:12px;color:{GRIS_SUAVE};">'
            f"… y {_plural(restantes, 'radicado más', 'radicados más')}.</td></tr>"
        )
    return (
        '<tr><td style="padding:4px 28px 6px 28px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;border:1px solid {BORDE};background:{FONDO_TABLA};">'
        f"<tr>{celdas_cab}</tr>{cuerpo}</table></td></tr>"
    )


def _estado_vencida(fila: dict) -> str:
    return _plural(fila["dias"], "día hábil de atraso", "días hábiles de atraso")


def _estado_proxima(fila: dict) -> str:
    if fila["dias"] == 0:
        return "Vence hoy"
    return "Vence en " + _plural(fila["dias"], "día hábil", "días hábiles")


def _seccion_correspondencia(datos: dict) -> str:
    vencidas, proximas = datos["vencidas"], datos["proximas"]
    html = _titulo_seccion("Tu correspondencia")
    if vencidas:
        html += _parrafo(
            f"Tienes <b style=\"color:{_ROJO[0]};\">{_plural(len(vencidas), 'radicado vencido', 'radicados vencidos')}</b> "
            "a tu nombre en la matriz de correspondencia:"
        )
        html += _tabla_radicados(vencidas, _ROJO, _estado_vencida)
    if proximas:
        html += _parrafo(
            f"<b style=\"color:{_AMBAR[0]};\">{_plural(len(proximas), 'radicado está', 'radicados están')} "
            "por vencer</b> en los próximos días:"
        )
        html += _tabla_radicados(proximas, _AMBAR, _estado_proxima)
    return html


def _seccion_formatos(datos: dict) -> str:
    return (
        _titulo_seccion("Formatos de contrato")
        + _parrafo(
            f"Desde el día <b>{datos['dia_inicio']}</b> ya puedes generar tus formatos de contrato de "
            f"<b>{nombre_mes(datos['mes'])} de {datos['año']}</b>. Ingresa al aplicativo SRTI, sección "
            "<b>Formatos de contrato</b>, y genera los que te correspondan."
        )
    )


def _seccion_firmas(avances: list) -> str:
    html = _titulo_seccion("Avance de firmas de tus formatos")
    for avance in avances:
        chips = " ".join(
            [_etiqueta("✔ " + rol, _VERDE) for rol in avance["firmadas"]]
            + [_etiqueta("Pendiente: " + rol, _GRIS) for rol in avance["pendientes"]]
        )
        total = len(avance["firmadas"]) + len(avance["pendientes"])
        nuevas = " y ".join(avance["nuevas"])
        if avance["aprobado"]:
            cierre = f'<b style="color:{_VERDE[0]};">Formato aprobado: ya tiene todas las firmas.</b>'
        elif avance["descargable"]:
            cierre = (
                f'<b style="color:{_VERDE[0]};">Ya puedes descargar el PDF</b> desde el aplicativo; '
                f"falta {_plural(len(avance['pendientes']), 'firma', 'firmas')} para la aprobación final."
            )
        else:
            cierre = f"Falta {_plural(len(avance['pendientes']), 'firma', 'firmas')} para completarlo."
        html += (
            '<tr><td style="padding:6px 28px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border:1px solid {BORDE};border-radius:6px;background:{FONDO_TABLA};">'
            '<tr><td style="padding:12px 14px;">'
            f'<div style="font-size:14px;font-weight:bold;color:{GRIS_TEXTO};">{escape(avance["formato"])}'
            f' <span style="font-weight:normal;color:{GRIS_SUAVE};">· {escape(avance["periodo"])}</span></div>'
            f'<div style="font-size:13px;color:{GRIS_TEXTO};padding:6px 0;">Nueva firma: <b>{escape(nuevas)}</b>'
            f" · {len(avance['firmadas'])} de {total} firmas</div>"
            f'<div style="line-height:2;">{chips}</div>'
            f'<div style="font-size:13px;color:{GRIS_TEXTO};padding-top:6px;">{cierre}</div>'
            "</td></tr></table></td></tr>"
        )
    return html


def construir_asunto(resumen: dict, hoy: date) -> str:
    partes = []
    correspondencia = resumen.get("correspondencia")
    if correspondencia and correspondencia["vencidas"]:
        partes.append(_plural(len(correspondencia["vencidas"]), "radicado vencido", "radicados vencidos"))
    elif correspondencia and correspondencia["proximas"]:
        partes.append(_plural(len(correspondencia["proximas"]), "radicado por vencer", "radicados por vencer"))
    if resumen.get("formatos"):
        partes.append("ya puedes generar tus formatos")
    if resumen.get("firmas"):
        partes.append("avance de firmas")
    detalle = ", ".join(partes) or "tu resumen"
    return f"SRTI · {detalle} ({hoy.day} de {_MESES[hoy.month - 1]})"


def construir_html(resumen: dict, hoy: date) -> str:
    nombre = escape(resumen["nombre"])
    secciones = ""
    if resumen.get("correspondencia"):
        secciones += _seccion_correspondencia(resumen["correspondencia"])
    if resumen.get("formatos"):
        secciones += _seccion_formatos(resumen["formatos"])
    if resumen.get("firmas"):
        secciones += _seccion_firmas(resumen["firmas"])

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:{FONDO_PAGINA};font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO_PAGINA};">
<tr><td align="center" style="padding:20px 10px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:{FONDO_TARJETA};border-radius:8px;overflow:hidden;border:1px solid {BORDE};">
<tr><td style="padding:16px 28px;background:{CAFE};border-bottom:4px solid {NARANJA};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    <td width="72" valign="middle"><img src="cid:{CID_LOGO}" width="54" height="54" alt="INVIAS" style="display:block;border:0;background:{FONDO_TARJETA};border-radius:8px;padding:3px;"></td>
    <td valign="middle">
      <div style="font-size:17px;font-weight:bold;color:{FONDO_TARJETA};">Gestión SRTI</div>
      <div style="font-size:12px;color:{FONDO_CABECERA_TABLA};">Subdirección de Reglamentación Técnica e Innovación · INVIAS</div>
    </td>
  </tr></table>
</td></tr>
<tr><td style="padding:22px 28px 2px 28px;">
  <div style="font-size:18px;font-weight:bold;color:{GRIS_TEXTO};">Hola, {nombre}</div>
  <div style="font-size:13px;color:{GRIS_SUAVE};padding-top:2px;">Resumen del {fecha_larga(hoy)}</div>
</td></tr>
{secciones}
<tr><td style="padding:22px 0 0 0;">
  <div style="background:{FONDO_CABECERA_TABLA};border-top:1px solid {BORDE};padding:14px 28px;font-size:11px;line-height:1.5;color:{CAFE};">
    Mensaje automático del aplicativo Gestión SRTI. No respondas a este correo.
    Este mensaje no contiene enlaces: para cualquier gestión ingresa al aplicativo como lo haces habitualmente.
  </div>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def construir_texto(resumen: dict, hoy: date) -> str:
    """Versión en texto plano del mismo resumen (para clientes sin HTML)."""
    lineas = [f"Hola, {resumen['nombre']}", f"Resumen del {fecha_larga(hoy)}", ""]
    correspondencia = resumen.get("correspondencia")
    if correspondencia:
        lineas.append("TU CORRESPONDENCIA")
        for fila in correspondencia["vencidas"][:MAX_FILAS_TABLA]:
            lineas.append(f"- VENCIDO {fila['radicado']} ({fila['vence'].strftime('%d/%m/%Y')}): {_estado_vencida(fila)}")
        for fila in correspondencia["proximas"][:MAX_FILAS_TABLA]:
            lineas.append(f"- {fila['radicado']} ({fila['vence'].strftime('%d/%m/%Y')}): {_estado_proxima(fila)}")
        lineas.append("")
    formatos = resumen.get("formatos")
    if formatos:
        lineas += [
            "FORMATOS DE CONTRATO",
            f"Desde el día {formatos['dia_inicio']} ya puedes generar tus formatos de contrato de "
            f"{nombre_mes(formatos['mes'])} de {formatos['año']}.",
            "",
        ]
    if resumen.get("firmas"):
        lineas.append("AVANCE DE FIRMAS")
        for avance in resumen["firmas"]:
            total = len(avance["firmadas"]) + len(avance["pendientes"])
            pendientes = ", ".join(avance["pendientes"]) or "ninguna"
            lineas.append(
                f"- {avance['formato']} ({avance['periodo']}): nueva firma de {' y '.join(avance['nuevas'])}; "
                f"{len(avance['firmadas'])} de {total} firmas. Pendientes: {pendientes}."
            )
        lineas.append("")
    lineas.append("Mensaje automático del aplicativo Gestión SRTI. No respondas a este correo.")
    return "\n".join(lineas)
