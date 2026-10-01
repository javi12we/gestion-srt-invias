from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from bson import ObjectId

from app.core.plantillas_correo import construir_asunto, construir_html, construir_texto, texto_seguro
from app.services.correo_service import CorreoService
from app.services.notificacion_service import (
    NotificacionService,
    clasificar_radicado,
    dias_habiles_entre,
    es_dia_habil,
)

# Jueves 1 de octubre de 2026, 8:00 p. m. en Bogotá.
AHORA = datetime(2026, 10, 2, 1, 0, tzinfo=timezone.utc)
HOY = date(2026, 10, 1)

U1 = ObjectId()
U2 = ObjectId()


def _usuario(_id, nombre="Carlos Acosta", email="carlos@ejemplo.com", activo=True, con_contrato=True):
    contratos = []
    if con_contrato:
        contratos = [{"numero": "299", "fecha_inicio": datetime(2026, 2, 1), "fecha_fin": datetime(2099, 12, 31)}]
    return {"_id": _id, "nombre_completo": nombre, "email": email, "activo": activo, "contratos": contratos}


def _radicado(usuario_id, numero, vence: datetime, asunto="Solicitud de concepto técnico"):
    return {
        "numero_radicado": numero,
        "asunto": asunto,
        "fecha_vencimiento": vence,
        "responsable_actual": {"usuario_id": usuario_id},
    }


class _Usuarios:
    def __init__(self, usuarios):
        self.usuarios = usuarios

    def listar(self):
        return self.usuarios

    def buscar_por_id(self, usuario_id):
        return next((u for u in self.usuarios if str(u["_id"]) == usuario_id), None)


class _Correspondencia:
    def __init__(self, docs):
        self.docs = docs
        self.consultas = 0

    def listar_abiertas_con_vencimiento_hasta(self, fecha_limite, estados_cerrados):
        self.consultas += 1
        return [d for d in self.docs if d["fecha_vencimiento"].replace(tzinfo=timezone.utc) <= fecha_limite]


class _Certificaciones:
    def __init__(self, certs):
        self.certs = certs

    def listar_con_firmas_desde(self, fecha, roles):
        return [
            c for c in self.certs
            if any(
                (c.get("firmas") or {}).get(r)
                and c["firmas"][r]["fecha"].replace(tzinfo=timezone.utc) >= fecha
                for r in roles
            )
        ]


    def buscar_por_id(self, cert_id):
        return next((c for c in self.certs if str(c["_id"]) == cert_id), None)


class _Registro:
    def __init__(self):
        self.envios = {}

    def eliminar_anteriores_a(self, fecha):
        viejas = [k for k, v in self.envios.items() if v < fecha]
        for clave in viejas:
            del self.envios[clave]
        return len(viejas)

    def fecha_envio(self, usuario_id, tipo, clave):
        return self.envios.get((usuario_id, tipo, clave))

    def registrar(self, usuario_id, tipo, clave, fecha):
        self.envios[(usuario_id, tipo, clave)] = fecha


class _Parametros:
    def __init__(self, **valores):
        self.valores = {
            "dia_inicio_periodo_certificacion": 29, "notificaciones_correo_modo": "diario", **valores,
        }

    def obtener(self, clave):
        return self.valores.get(clave, False)


class _Correo:
    def __init__(self, falla_para=()):
        self.enviados = []
        self.falla_para = set(falla_para)
        self.conectado = False
        self.cerrado = False

    def configurado(self):
        return True

    def conectar(self):
        self.conectado = True

    def enviar(self, destinatario, asunto, html, texto):
        if destinatario in self.falla_para:
            raise RuntimeError("buzón rechazado")
        self.enviados.append((destinatario, asunto, html, texto))

    def cerrar(self):
        self.cerrado = True


def _servicio(usuarios=(), radicados=(), certs=(), registro=None, parametros=None, correo=None, ahora=AHORA):
    return NotificacionService(
        usuario_repo=_Usuarios(list(usuarios)),
        correspondencia_repo=_Correspondencia(list(radicados)),
        certificacion_repo=_Certificaciones(list(certs)),
        notificacion_repo=registro or _Registro(),
        parametros=parametros or _Parametros(),
        correo=correo or _Correo(),
        ahora=ahora,
        pausa_segundos=0,
    )


# ── Cálculo de días ──────────────────────────────────────────────────────────

def test_dias_habiles_no_cuentan_fines_de_semana_ni_festivos():
    assert es_dia_habil(date(2026, 10, 1)) is True
    assert es_dia_habil(date(2026, 10, 3)) is False          # sábado
    assert es_dia_habil(date(2026, 10, 12)) is False         # festivo (Día de la Raza)
    assert dias_habiles_entre(date(2026, 9, 24), date(2026, 10, 1)) == 5
    assert dias_habiles_entre(date(2026, 10, 9), date(2026, 10, 13)) == 1


def test_clasificar_radicado():
    assert clasificar_radicado(datetime(2026, 9, 24), HOY) == ("vencida", 5)
    assert clasificar_radicado(datetime(2026, 10, 1), HOY) == ("proxima", 0)       # vence hoy
    assert clasificar_radicado(datetime(2026, 10, 6), HOY) == ("proxima", 3)
    assert clasificar_radicado(datetime(2026, 10, 7), HOY) is None                  # a más de 5 días


# ── Correspondencia ──────────────────────────────────────────────────────────

def test_correspondencia_separa_vencidas_y_proximas_por_responsable():
    servicio = _servicio(
        usuarios=[_usuario(U1), _usuario(U2, nombre="Ana Ruiz", email="ana@ejemplo.com")],
        radicados=[
            _radicado(U1, "RE26-0001", datetime(2026, 9, 24)),
            _radicado(U1, "RE26-0002", datetime(2026, 9, 30)),
            _radicado(U1, "RE26-0003", datetime(2026, 10, 5)),
            _radicado(U2, "RE26-0009", datetime(2026, 10, 20)),   # a tiempo: Ana no recibe nada
        ],
    )

    resumenes = servicio.construir_resumenes()

    assert [r["email"] for r in resumenes] == ["carlos@ejemplo.com"]
    datos = resumenes[0]["correspondencia"]
    assert [(f["radicado"], f["dias"]) for f in datos["vencidas"]] == [("RE26-0001", 5), ("RE26-0002", 1)]
    assert [(f["radicado"], f["dias"]) for f in datos["proximas"]] == [("RE26-0003", 2)]
    assert resumenes[0]["registros"] == [("correspondencia", "2026-10-01")]


def test_correspondencia_no_se_avisa_en_fin_de_semana_ni_dos_veces_el_mismo_dia():
    radicados = [_radicado(U1, "RE26-0001", datetime(2026, 9, 24))]
    sabado = datetime(2026, 10, 4, 1, 0, tzinfo=timezone.utc)   # sábado 3 en Bogotá
    assert _servicio(usuarios=[_usuario(U1)], radicados=radicados, ahora=sabado).construir_resumenes() == []

    registro = _Registro()
    registro.registrar(str(U1), "correspondencia", "2026-10-01", AHORA)
    assert _servicio(usuarios=[_usuario(U1)], radicados=radicados, registro=registro).construir_resumenes() == []


def test_usuario_inactivo_o_sin_correo_valido_no_recibe_nada():
    radicados = [_radicado(U1, "RE26-0001", datetime(2026, 9, 24)), _radicado(U2, "RE26-0002", datetime(2026, 9, 24))]
    servicio = _servicio(
        usuarios=[_usuario(U1, activo=False), _usuario(U2, email="sin-arroba")],
        radicados=radicados,
    )

    assert servicio.construir_resumenes() == []


# ── Apertura de formatos ─────────────────────────────────────────────────────

def test_aviso_de_formatos_sale_desde_el_dia_configurado_una_vez_por_periodo():
    dia_29 = datetime(2026, 10, 30, 1, 0, tzinfo=timezone.utc)   # jueves 29 de octubre, 8 p. m.
    registro = _Registro()
    usuarios = [_usuario(U1), _usuario(U2, email="ana@ejemplo.com", con_contrato=False)]

    antes = _servicio(usuarios=usuarios, registro=registro, ahora=dia_29 - timedelta(days=1))
    assert antes.construir_resumenes() == []

    servicio = _servicio(usuarios=usuarios, registro=registro, ahora=dia_29)
    resumenes = servicio.construir_resumenes()
    assert [r["email"] for r in resumenes] == ["carlos@ejemplo.com"]        # solo con contrato vigente
    assert resumenes[0]["formatos"] == {"dia_inicio": 29, "mes": 10, "año": 2026}

    servicio.ejecutar()
    al_dia_siguiente = _servicio(usuarios=usuarios, registro=registro, ahora=dia_29 + timedelta(days=1))
    assert al_dia_siguiente.construir_resumenes() == []


def test_aviso_de_formatos_solo_sale_en_los_tres_dias_desde_la_apertura():
    """Fuera de esa ventana no sale aunque no exista la marca de enviado: así la
    limpieza semanal del registro no puede hacer que el aviso se repita."""
    usuarios = [_usuario(U1)]
    parametros = _Parametros(dia_inicio_periodo_certificacion=5)

    def sale(dia):
        ahora = datetime(2026, 10, dia + 1, 1, 0, tzinfo=timezone.utc)   # 8 p. m. del día `dia` en Bogotá
        return bool(_servicio(usuarios=usuarios, parametros=parametros, ahora=ahora).construir_resumenes())

    assert [sale(d) for d in (4, 5, 6, 7, 8, 20)] == [False, True, True, True, False, False]


# ── Avance de firmas ─────────────────────────────────────────────────────────

def _cert(usuario_id, tipo, firmas, estado="pendiente"):
    return {
        "_id": ObjectId(), "usuario_id": usuario_id, "tipo_formato": tipo,
        "año": 2026, "mes": 9, "estado": estado, "firmas": firmas,
    }


def _firma(hace_horas):
    return {"firmante_id": ObjectId(), "firmante_nombre": "X", "fecha": (AHORA - timedelta(hours=hace_horas)).replace(tzinfo=None)}


def test_firma_nueva_se_avisa_con_lo_firmado_y_lo_pendiente():
    cert = _cert(U1, None, {"corr": _firma(200), "gd": _firma(5)})
    servicio = _servicio(usuarios=[_usuario(U1)], certs=[cert])

    avance = servicio.construir_resumenes()[0]["firmas"][0]

    assert avance["formato"] == "Formato de control Corr-GD-SECOP"
    assert avance["periodo"] == "Septiembre 2026"
    assert avance["nuevas"] == ["Gestión Documental"]            # la de Correspondencia es vieja
    assert avance["firmadas"] == ["Correspondencia", "Gestión Documental"]
    assert avance["pendientes"] == ["SECOP II"]
    assert avance["descargable"] is False


def test_firmas_de_financiera_y_juridico_avisan_que_ya_se_puede_descargar():
    cert = _cert(U1, "acta_recibo_entrega_cps", {"financiera": _firma(30), "abogado": _firma(2)})
    servicio = _servicio(usuarios=[_usuario(U1)], certs=[cert])

    avance = servicio.construir_resumenes()[0]["firmas"][0]

    assert avance["formato"] == "Balance General CPS"
    assert avance["nuevas"] == ["Financiera", "Jurídico"]
    assert avance["pendientes"] == ["Jefe inmediato"]
    assert avance["descargable"] is True and avance["aprobado"] is False


def test_firma_ya_avisada_no_se_repite_y_una_posterior_si():
    cert = _cert(U1, "acta_recibo_entrega_cps", {"financiera": _firma(5)})
    registro = _Registro()
    servicio = _servicio(usuarios=[_usuario(U1)], certs=[cert], registro=registro)
    assert servicio.ejecutar()["enviados"] == 1

    manana = AHORA + timedelta(days=1)
    assert _servicio(usuarios=[_usuario(U1)], certs=[cert], registro=registro, ahora=manana).construir_resumenes() == []

    cert["firmas"]["abogado"] = {"firmante_id": ObjectId(), "firmante_nombre": "Y", "fecha": (manana - timedelta(hours=3)).replace(tzinfo=None)}
    avance = _servicio(usuarios=[_usuario(U1)], certs=[cert], registro=registro, ahora=manana).construir_resumenes()[0]["firmas"][0]
    assert avance["nuevas"] == ["Jurídico"]


def test_firma_extra_cuenta_como_requerida_solo_si_el_parametro_esta_activo():
    cert = _cert(U1, "acta_compromiso", {"jefe": _firma(2)})
    normal = _servicio(usuarios=[_usuario(U1)], certs=[cert]).construir_resumenes()[0]["firmas"][0]
    assert normal["pendientes"] == []

    con_extra = _servicio(
        usuarios=[_usuario(U1)], certs=[cert],
        parametros=_Parametros(firma_extra_acta_compromiso_activa=True),
    ).construir_resumenes()[0]["firmas"][0]
    assert con_extra["pendientes"] == ["Firma Extra"]


# ── Envío ────────────────────────────────────────────────────────────────────

def test_simular_no_envia_ni_registra():
    registro, correo = _Registro(), _Correo()
    servicio = _servicio(
        usuarios=[_usuario(U1)], radicados=[_radicado(U1, "RE26-0001", datetime(2026, 9, 24))],
        registro=registro, correo=correo,
    )

    resultado = servicio.ejecutar(simular=True)

    assert resultado["usuarios_con_aviso"] == 1 and resultado["enviados"] == 0
    assert correo.enviados == [] and not correo.conectado and registro.envios == {}


def test_envio_real_registra_y_un_fallo_no_detiene_a_los_demas():
    registro = _Registro()
    correo = _Correo(falla_para={"carlos@ejemplo.com"})
    servicio = _servicio(
        usuarios=[_usuario(U1), _usuario(U2, nombre="Ana Ruiz", email="ana@ejemplo.com")],
        radicados=[
            _radicado(U1, "RE26-0001", datetime(2026, 9, 24)),
            _radicado(U2, "RE26-0002", datetime(2026, 9, 24)),
        ],
        registro=registro, correo=correo,
    )

    resultado = servicio.ejecutar()

    assert (resultado["enviados"], resultado["fallidos"]) == (1, 1)
    assert [e[0] for e in correo.enviados] == ["ana@ejemplo.com"]
    assert list(registro.envios) == [(str(U2), "correspondencia", "2026-10-01")]   # Carlos se reintenta mañana
    assert correo.cerrado


def test_prueba_envia_a_la_direccion_de_prueba_sin_registrar():
    registro, correo = _Registro(), _Correo()
    servicio = _servicio(
        usuarios=[_usuario(U1)], radicados=[_radicado(U1, "RE26-0001", datetime(2026, 9, 24))],
        registro=registro, correo=correo,
    )

    servicio.ejecutar(prueba_a="pruebas@ejemplo.com")

    assert [e[0] for e in correo.enviados] == ["pruebas@ejemplo.com"]
    assert registro.envios == {}


# ── Plantilla ────────────────────────────────────────────────────────────────

def _resumen_completo():
    return {
        "nombre": "Carlos <Acosta>",
        "correspondencia": {
            "vencidas": [{"radicado": "RE26-0001", "asunto": "Ver https://sitio.com/x y www.otro.co o a@b.com", "vence": date(2026, 9, 24), "dias": 5}],
            "proximas": [{"radicado": "RE26-0003", "asunto": "Concepto", "vence": date(2026, 10, 1), "dias": 0}],
        },
        "formatos": {"dia_inicio": 29, "mes": 10, "año": 2026},
        "firmas": [{
            "formato": "Balance General CPS", "periodo": "Septiembre 2026", "nuevas": ["Jurídico"],
            "firmadas": ["Financiera", "Jurídico"], "pendientes": ["Jefe inmediato"],
            "aprobado": False, "descargable": True,
        }],
    }


def test_el_correo_no_contiene_ningun_enlace():
    resumen = _resumen_completo()
    html = construir_html(resumen, HOY)
    texto = construir_texto(resumen, HOY)

    for contenido in (html, texto):
        minusculas = contenido.lower()
        assert "<a " not in minusculas and "href" not in minusculas
        assert "http" not in minusculas and "www." not in minusculas
        assert "a@b.com" not in minusculas
    assert html.count("[enlace omitido]") == 3


def test_el_correo_va_personalizado_con_nombre_y_fecha_y_escapa_html():
    resumen = _resumen_completo()
    html = construir_html(resumen, HOY)

    assert "Hola, Carlos &lt;Acosta&gt;" in html
    assert "jueves 1 de octubre de 2026" in html
    assert "5 días hábiles de atraso" in html and "Vence hoy" in html
    assert "Ya puedes descargar el PDF" in html
    assert construir_asunto(resumen, HOY) == (
        "SRTI · 1 radicado vencido, ya puedes generar tus formatos, avance de firmas (1 de octubre)"
    )
    assert texto_seguro("a" * 200, 50).endswith("…")


def test_mensaje_lleva_el_logo_embebido_y_version_en_texto():
    cfg = SimpleNamespace(
        correo_remitente="remitente@ejemplo.com", correo_password_app="x",
        correo_nombre_remitente="Gestión SRTI - INVIAS", correo_smtp_host="h", correo_smtp_puerto=465,
    )
    resumen = _resumen_completo()

    mensaje = CorreoService(cfg).construir_mensaje(
        "carlos@ejemplo.com", "Asunto", construir_html(resumen, HOY), construir_texto(resumen, HOY)
    )

    tipos = [parte.get_content_type() for parte in mensaje.walk()]
    assert tipos == ["multipart/alternative", "text/plain", "multipart/related", "text/html", "image/png"]
    assert mensaje["To"] == "carlos@ejemplo.com"
    imagen = [p for p in mensaje.walk() if p.get_content_type() == "image/png"][0]
    assert imagen["Content-ID"] == "<logo_invias>"


# ── Limpieza semanal del registro ────────────────────────────────────────────

def test_limpieza_borra_las_marcas_viejas_y_conserva_las_que_aun_evitan_repetir():
    registro = _Registro()
    registro.registrar(str(U1), "correspondencia", "2026-09-20", AHORA - timedelta(days=11))
    registro.registrar(str(U1), "firmas", "cert-viejo", AHORA - timedelta(days=4))
    registro.registrar(str(U1), "firmas", "cert-reciente", AHORA - timedelta(days=1))

    borradas = _servicio(registro=registro).limpiar_registro()

    assert borradas == 2
    assert list(registro.envios) == [(str(U1), "firmas", "cert-reciente")]


def test_despues_de_la_limpieza_no_se_repite_el_aviso_de_una_firma_ya_avisada():
    cert = _cert(U1, "acta_recibo_entrega_cps", {"financiera": _firma(5)})
    registro = _Registro()
    assert _servicio(usuarios=[_usuario(U1)], certs=[cert], registro=registro).ejecutar()["enviados"] == 1

    for dias in (1, 2, 3, 4, 8):
        despues = AHORA + timedelta(days=dias)
        servicio = _servicio(usuarios=[_usuario(U1)], certs=[cert], registro=registro, ahora=despues)
        servicio.limpiar_registro()
        assert servicio.construir_resumenes() == [], f"se repitió a los {dias} días"
    assert registro.envios == {}


# ── Modo "al momento" ────────────────────────────────────────────────────────

def test_notificar_firma_envia_de_inmediato_y_la_noche_no_la_repite():
    cert = _cert(U1, None, {"corr": _firma(0)})
    registro, correo = _Registro(), _Correo()
    servicio = _servicio(usuarios=[_usuario(U1)], certs=[cert], registro=registro, correo=correo)

    assert servicio.notificar_firma(str(cert["_id"])) is True

    destinatario, asunto, html, _ = correo.enviados[0]
    assert destinatario == "carlos@ejemplo.com"
    assert "avance de firmas" in asunto and "Nueva firma: <b>Correspondencia</b>" in html
    assert correo.cerrado
    assert _servicio(usuarios=[_usuario(U1)], certs=[cert], registro=registro).construir_resumenes() == []
    assert servicio.notificar_firma(str(cert["_id"])) is False       # nada nuevo que avisar


def test_notificar_firma_no_envia_si_el_usuario_no_tiene_correo_o_el_formato_no_existe():
    cert = _cert(U1, None, {"corr": _firma(0)})
    correo = _Correo()
    servicio = _servicio(usuarios=[_usuario(U1, email="")], certs=[cert], correo=correo)

    assert servicio.notificar_firma(str(cert["_id"])) is False
    assert servicio.notificar_firma(str(ObjectId())) is False
    assert correo.enviados == []


def test_parametro_de_modo_solo_admite_sus_dos_opciones():
    import pytest
    from app.services.parametros_service import PARAMETROS, ParametrosService

    meta = PARAMETROS["notificaciones_correo_modo"]
    assert meta["default"] == "diario" and set(meta["opciones"]) == {"diario", "al_momento"}

    servicio = ParametrosService.__new__(ParametrosService)
    assert servicio._validar("notificaciones_correo_modo", "al_momento") == "al_momento"
    with pytest.raises(ValueError):
        servicio._validar("notificaciones_correo_modo", "cada_hora")
    assert _servicio().modo_envio() == "diario"
