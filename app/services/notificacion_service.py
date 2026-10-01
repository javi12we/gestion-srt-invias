"""Notificaciones diarias por correo: un resumen por usuario, una vez al día.

No corre dentro de Streamlit: lo ejecuta app/scripts/enviar_notificaciones.py
(programado por fuera de la app) y termina. Ver docs/notificaciones_correo.md.

Avisos que arma, solo si aplican al usuario ese día:
- Correspondencia vencida y próxima a vencer a su nombre (solo días hábiles).
- Apertura de los formatos de contrato del mes (una vez por período, desde el
  día configurado en el parámetro dia_inicio_periodo_certificacion).
- Avance de firmas: cuando uno de sus formatos recibió una firma nueva.
"""

import logging
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone

from app.core.festivos import FESTIVOS_CO
from app.core.plantillas_correo import construir_asunto, construir_html, construir_texto, nombre_mes
from app.core.zona_horaria import ZONA_BOGOTA

_log = logging.getLogger(__name__)

ESTADOS_CERRADOS = ["respondido", "archivado", "traslado_competencia"]

# Misma ventana que el filtro "Próximas a Vencer" de la matriz de correspondencia.
DIAS_PROXIMO_A_VENCER = 5

# Una firma se avisa si se registró en los últimos N días: cubre una noche en la
# que el envío no haya corrido, sin avisar firmas antiguas al activar la función.
VENTANA_FIRMAS_DIAS = 3

# El aviso de apertura de formatos solo sale el día de apertura y los dos
# siguientes (por si esa noche el envío no corrió).
VENTANA_FORMATOS_DIAS = 3

# La limpieza semanal conserva las marcas de los últimos días: son las únicas
# que todavía evitan repetir un aviso (cubren las dos ventanas de arriba).
# Todo lo anterior ya no se consulta y se borra.
DIAS_RETENCION_REGISTRO = max(VENTANA_FIRMAS_DIAS, VENTANA_FORMATOS_DIAS)

MAX_CORREOS_DE_PRUEBA = 3

# Valores del parámetro de admin "notificaciones_correo_modo".
PARAMETRO_MODO = "notificaciones_correo_modo"
MODO_DIARIO = "diario"
MODO_AL_MOMENTO = "al_momento"

_ETIQUETA_ROL = {
    "corr": "Correspondencia",
    "gd": "Gestión Documental",
    "secop": "SECOP II",
    "financiera": "Financiera",
    "abogado": "Jurídico",
    "jefe": "Jefe inmediato",
}
_ETIQUETA_FIRMA_EXTRA = "Firma Extra"

_TITULO_FORMATO = {
    "gestion_correspondencia": "Formato de control Corr-GD-SECOP",
    "acta_compromiso": "Acta de compromiso",
    "acta_recibo_entrega_cps": "Balance General CPS",
    "acta_recibo_entrega_cps_real": "Acta de recibo y entrega CPS",
}

_PATRON_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _utc(fecha: datetime | None) -> datetime | None:
    """PyMongo devuelve las fechas naive en UTC (el cliente no usa tz_aware)."""
    if fecha is None:
        return None
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc)


def es_dia_habil(dia: date) -> bool:
    return dia.weekday() < 5 and dia not in FESTIVOS_CO


def dias_habiles_entre(inicio: date, fin: date) -> int:
    """Días hábiles en (inicio, fin]: mismo conteo que la columna Tiempo de la
    matriz de correspondencia."""
    total = 0
    actual = inicio + timedelta(days=1)
    while actual <= fin:
        if es_dia_habil(actual):
            total += 1
        actual += timedelta(days=1)
    return total


def clasificar_radicado(fecha_vencimiento: datetime, hoy: date) -> tuple[str, int] | None:
    """("vencida", días hábiles de atraso), ("proxima", días hábiles que faltan;
    0 = vence hoy) o None si aún está a tiempo."""
    vence = _utc(fecha_vencimiento).date()
    dias_calendario = (vence - hoy).days
    if dias_calendario < 0:
        return "vencida", dias_habiles_entre(vence, hoy)
    if dias_calendario <= DIAS_PROXIMO_A_VENCER:
        return "proxima", dias_habiles_entre(hoy, vence)
    return None


class NotificacionService:
    def __init__(
        self,
        usuario_repo=None,
        correspondencia_repo=None,
        certificacion_repo=None,
        notificacion_repo=None,
        parametros=None,
        correo=None,
        ahora: datetime | None = None,
        pausa_segundos: float = 1.0,
    ) -> None:
        # Imports diferidos: permiten inyectar dobles en las pruebas sin abrir Mongo.
        if usuario_repo is None:
            from app.repositories.usuario_repo import UsuarioRepositorio
            usuario_repo = UsuarioRepositorio()
        if correspondencia_repo is None:
            from app.repositories.correspondencia_repo import CorrespondenciaRepositorio
            correspondencia_repo = CorrespondenciaRepositorio()
        if certificacion_repo is None:
            from app.repositories.certificacion_repo import CertificacionRepositorio
            certificacion_repo = CertificacionRepositorio()
        if notificacion_repo is None:
            from app.repositories.notificacion_repo import NotificacionRepositorio
            notificacion_repo = NotificacionRepositorio()
        if parametros is None:
            from app.services.parametros_service import ParametrosService
            parametros = ParametrosService()
        if correo is None:
            from app.services.correo_service import CorreoService
            correo = CorreoService()

        self.usuario_repo = usuario_repo
        self.correspondencia_repo = correspondencia_repo
        self.certificacion_repo = certificacion_repo
        self.notificacion_repo = notificacion_repo
        self.parametros = parametros
        self.correo = correo
        self.pausa_segundos = pausa_segundos

        self.ahora_utc = _utc(ahora) if ahora else datetime.now(timezone.utc)
        self.hoy = self.ahora_utc.astimezone(ZONA_BOGOTA).date()

    # ── Destinatarios ────────────────────────────────────────────────────────

    @staticmethod
    def _es_notificable(usuario: dict | None) -> bool:
        return bool(
            usuario
            and usuario.get("activo", True)
            and _PATRON_EMAIL.fullmatch((usuario.get("email") or "").strip())
        )

    def _usuarios_notificables(self) -> dict:
        """Usuarios activos con un correo utilizable, por id."""
        return {str(u["_id"]): u for u in self.usuario_repo.listar() if self._es_notificable(u)}

    @staticmethod
    def _resumen_base(usuario_id: str, usuario: dict) -> dict:
        return {
            "usuario_id": usuario_id,
            "nombre": (usuario.get("nombre_completo") or usuario.get("usuario") or "").strip(),
            "email": usuario["email"].strip(),
            "registros": [],
        }

    # ── Correspondencia ──────────────────────────────────────────────────────

    def _correspondencia_por_usuario(self) -> dict:
        if not es_dia_habil(self.hoy):
            return {}

        limite = datetime.combine(
            self.hoy + timedelta(days=DIAS_PROXIMO_A_VENCER), datetime.max.time(), tzinfo=timezone.utc
        )
        por_usuario = {}
        for doc in self.correspondencia_repo.listar_abiertas_con_vencimiento_hasta(limite, ESTADOS_CERRADOS):
            clasificacion = clasificar_radicado(doc["fecha_vencimiento"], self.hoy)
            if not clasificacion:
                continue
            categoria, dias = clasificacion
            usuario_id = str(doc["responsable_actual"]["usuario_id"])
            grupo = por_usuario.setdefault(usuario_id, {"vencidas": [], "proximas": []})
            grupo["vencidas" if categoria == "vencida" else "proximas"].append({
                "radicado": doc.get("numero_radicado") or "",
                "asunto": doc.get("asunto") or "",
                "vence": _utc(doc["fecha_vencimiento"]).date(),
                "dias": dias,
            })

        for grupo in por_usuario.values():
            grupo["vencidas"].sort(key=lambda f: f["dias"], reverse=True)
            grupo["proximas"].sort(key=lambda f: f["vence"])
        return por_usuario

    # ── Apertura de formatos de contrato ─────────────────────────────────────

    def _aviso_formatos(self) -> dict | None:
        dia_inicio = self.parametros.obtener("dia_inicio_periodo_certificacion")
        if not (dia_inicio <= self.hoy.day < dia_inicio + VENTANA_FORMATOS_DIAS):
            return None
        return {"dia_inicio": dia_inicio, "mes": self.hoy.month, "año": self.hoy.year}

    @staticmethod
    def _tiene_contrato_vigente(usuario: dict) -> bool:
        from app.services.certificacion_service import CertificacionService
        return bool(CertificacionService._contrato_vigente(usuario.get("contratos") or []).get("numero"))

    # ── Avance de firmas ─────────────────────────────────────────────────────

    def _roles_requeridos(self, tipo_formato: str | None) -> list:
        """Firmas que exige el formato, en orden, como (clave en firmas, etiqueta)."""
        from app.services.certificacion_service import (
            FIRMA_EXTRA_CONFIG, ORDEN_FIRMAS_ACTAS, TIPOS_FIRMA_CORR,
        )

        tipo = tipo_formato or "gestion_correspondencia"
        if tipo == "gestion_correspondencia":
            roles = list(TIPOS_FIRMA_CORR)
        else:
            roles = list(ORDEN_FIRMAS_ACTAS.get(tipo, ()))
        if not roles:
            return []

        requeridos = [(rol, _ETIQUETA_ROL[rol]) for rol in roles]
        extra = FIRMA_EXTRA_CONFIG.get(tipo)
        if extra and self.parametros.obtener(extra["parametro"]):
            requeridos.append((extra["tipo_firmante"], _ETIQUETA_FIRMA_EXTRA))
        return requeridos

    def _avance_de_cert(self, cert: dict) -> dict | None:
        """Avance de firmas de un formato, o None si no tiene ninguna firma nueva
        (reciente y posterior al último aviso que se le envió al contratista)."""
        from app.services.certificacion_service import CertificacionService

        requeridos = self._roles_requeridos(cert.get("tipo_formato"))
        if not requeridos:
            return None

        usuario_id = str(cert.get("usuario_id"))
        cert_id = str(cert["_id"])
        firmas = cert.get("firmas") or {}
        desde = self.ahora_utc - timedelta(days=VENTANA_FIRMAS_DIAS)
        ultimo_aviso = _utc(self.notificacion_repo.fecha_envio(usuario_id, "firmas", cert_id))

        def _es_nueva(firma: dict) -> bool:
            fecha = _utc(firma.get("fecha") or desde)
            if not (desde <= fecha <= self.ahora_utc):
                return False
            # Estrictamente posterior al último aviso: una firma registrada en el
            # mismo instante en que se avisó ya iba incluida en ese aviso.
            return ultimo_aviso is None or fecha > ultimo_aviso

        nuevas = [
            etiqueta for rol, etiqueta in requeridos if firmas.get(rol) and _es_nueva(firmas[rol])
        ]
        if not nuevas:
            return None

        tipo = cert.get("tipo_formato") or "gestion_correspondencia"
        return {
            "cert_id": cert_id,
            "formato": _TITULO_FORMATO.get(tipo, tipo),
            "periodo": f"{nombre_mes(cert.get('mes') or 1).capitalize()} {cert.get('año', '')}",
            "nuevas": nuevas,
            "firmadas": [etiqueta for rol, etiqueta in requeridos if firmas.get(rol)],
            "pendientes": [etiqueta for rol, etiqueta in requeridos if not firmas.get(rol)],
            "aprobado": cert.get("estado") == "aprobado",
            "descargable": CertificacionService.acta_descargable_por_contratista(cert),
        }

    def _firmas_por_usuario(self, usuarios: dict) -> dict:
        from app.services.certificacion_service import FIRMA_EXTRA_CONFIG

        desde = self.ahora_utc - timedelta(days=VENTANA_FIRMAS_DIAS)
        claves_firma = list(_ETIQUETA_ROL) + [m["tipo_firmante"] for m in FIRMA_EXTRA_CONFIG.values()]

        por_usuario = {}
        for cert in self.certificacion_repo.listar_con_firmas_desde(desde, claves_firma):
            usuario_id = str(cert.get("usuario_id"))
            if usuario_id not in usuarios:
                continue
            avance = self._avance_de_cert(cert)
            if avance:
                por_usuario.setdefault(usuario_id, []).append(avance)
        return por_usuario

    # ── Resúmenes ────────────────────────────────────────────────────────────

    def construir_resumenes(self) -> list:
        """Un resumen por usuario que tiene algo que avisar hoy. Cada resumen
        trae en "registros" lo que hay que marcar como enviado si el correo sale."""
        usuarios = self._usuarios_notificables()
        correspondencia = self._correspondencia_por_usuario()
        formatos = self._aviso_formatos()
        firmas = self._firmas_por_usuario(usuarios)

        clave_dia = self.hoy.isoformat()
        clave_periodo = f"{self.hoy.year}-{self.hoy.month:02d}"

        resumenes = []
        for usuario_id, usuario in usuarios.items():
            resumen = self._resumen_base(usuario_id, usuario)

            datos = correspondencia.get(usuario_id)
            if datos and not self.notificacion_repo.fecha_envio(usuario_id, "correspondencia", clave_dia):
                resumen["correspondencia"] = datos
                resumen["registros"].append(("correspondencia", clave_dia))

            if (
                formatos
                and self._tiene_contrato_vigente(usuario)
                and not self.notificacion_repo.fecha_envio(usuario_id, "formatos", clave_periodo)
            ):
                resumen["formatos"] = formatos
                resumen["registros"].append(("formatos", clave_periodo))

            if firmas.get(usuario_id):
                resumen["firmas"] = firmas[usuario_id]
                resumen["registros"] += [("firmas", avance["cert_id"]) for avance in firmas[usuario_id]]

            if resumen["registros"]:
                resumenes.append(resumen)
        return resumenes

    def renderizar(self, resumen: dict) -> tuple[str, str, str]:
        return (
            construir_asunto(resumen, self.hoy),
            construir_html(resumen, self.hoy),
            construir_texto(resumen, self.hoy),
        )

    # ── Envío ────────────────────────────────────────────────────────────────

    def ejecutar(self, simular: bool = False, prueba_a: str | None = None) -> dict:
        """Arma y envía los resúmenes del día.

        - simular: no envía ni registra nada; solo cuenta.
        - prueba_a: envía hasta MAX_CORREOS_DE_PRUEBA resúmenes reales a esa
          dirección en lugar de a sus dueños, sin registrarlos como enviados.
        """
        resumenes = self.construir_resumenes()
        estadisticas = {
            "usuarios_con_aviso": len(resumenes),
            "correspondencia": sum(1 for r in resumenes if r.get("correspondencia")),
            "formatos": sum(1 for r in resumenes if r.get("formatos")),
            "firmas": sum(1 for r in resumenes if r.get("firmas")),
            "enviados": 0,
            "fallidos": 0,
            "errores": [],
        }
        if simular or not resumenes:
            return estadisticas

        if prueba_a:
            resumenes = resumenes[:MAX_CORREOS_DE_PRUEBA]

        self.correo.conectar()
        try:
            for indice, resumen in enumerate(resumenes):
                asunto, html, texto = self.renderizar(resumen)
                try:
                    self.correo.enviar(prueba_a or resumen["email"], asunto, html, texto)
                except Exception as e:
                    # Un destinatario que falla no detiene el resto; al no registrarse,
                    # su aviso se reintenta en la siguiente ejecución.
                    estadisticas["fallidos"] += 1
                    estadisticas["errores"].append(type(e).__name__)
                    continue

                estadisticas["enviados"] += 1
                if not prueba_a:
                    for tipo, clave in resumen["registros"]:
                        self.notificacion_repo.registrar(resumen["usuario_id"], tipo, clave, self.ahora_utc)
                if self.pausa_segundos and indice < len(resumenes) - 1:
                    time.sleep(self.pausa_segundos)
        finally:
            self.correo.cerrar()
        return estadisticas

    # ── Limpieza del registro ────────────────────────────────────────────────

    def limpiar_registro(self) -> int:
        """Borra de la base de datos las marcas de avisos ya enviados que no hacen
        falta para evitar repeticiones. Devuelve cuántas borró."""
        limite = self.ahora_utc - timedelta(days=DIAS_RETENCION_REGISTRO)
        return self.notificacion_repo.eliminar_anteriores_a(limite)

    # ── Aviso inmediato (modo "al momento") ──────────────────────────────────

    def modo_envio(self) -> str:
        return self.parametros.obtener(PARAMETRO_MODO)

    def notificar_firma(self, cert_id: str) -> bool:
        """Envía ya el avance de firmas de un formato a su contratista. Devuelve
        True si salió el correo. Si no sale (o falla), el formato queda sin
        registrar y el resumen de la noche lo vuelve a intentar."""
        cert = self.certificacion_repo.buscar_por_id(cert_id)
        if not cert:
            return False
        usuario_id = str(cert.get("usuario_id"))
        usuario = self.usuario_repo.buscar_por_id(usuario_id)
        if not self._es_notificable(usuario):
            return False
        avance = self._avance_de_cert(cert)
        if not avance:
            return False

        resumen = self._resumen_base(usuario_id, usuario)
        resumen["firmas"] = [avance]
        asunto, html, texto = self.renderizar(resumen)
        try:
            self.correo.conectar()
            self.correo.enviar(resumen["email"], asunto, html, texto)
        finally:
            self.correo.cerrar()
        self.notificacion_repo.registrar(usuario_id, "firmas", cert_id, self.ahora_utc)
        return True


def avisar_firma_en_segundo_plano(cert_id: str) -> None:
    """Punto de entrada desde la app al registrar una firma. Solo actúa si el
    parámetro de admin está en modo 'al momento' y hay correo remitente
    configurado. Corre en un hilo aparte para no demorar la pantalla del
    firmante, y ningún fallo llega a la firma: queda anotado en el registro de
    la app (sin datos personales) y el resumen de la noche cubre el aviso."""

    def _tarea() -> None:
        try:
            servicio = NotificacionService(pausa_segundos=0)
            if servicio.modo_envio() != MODO_AL_MOMENTO:
                return
            if not servicio.correo.configurado():
                _log.warning(
                    "Aviso de firma no enviado: faltan CORREO_REMITENTE y CORREO_PASSWORD_APP "
                    "en la configuración de la app."
                )
                return
            servicio.notificar_firma(cert_id)
        except Exception as e:
            _log.warning("Aviso de firma no enviado (%s).", type(e).__name__)

    threading.Thread(target=_tarea, name="aviso-firma-correo", daemon=True).start()
