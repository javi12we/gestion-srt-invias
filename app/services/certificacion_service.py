"""Servicio de certificaciones mensuales SRTI-INVIAS.

El período de certificación va del día 29 al último día de cada mes.
El supervisor revisa el estado de correspondencia y emite el certificado
que le sirve al colaborador como soporte para su cuenta de cobro.
"""

import hashlib
import hmac
import io
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from bson import ObjectId

from app.config import configuracion
from app.repositories.certificacion_repo import CertificacionRepositorio
from app.core.zona_horaria import ZONA_BOGOTA, utc_a_bogota

MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

# Día del mes en que se abre la ventana normal de certificación del mes actual.
# Días 1 a (DIA_INICIO_PERIODO - 1): se certifica el mes anterior (ventana de ponerse al día).
# Días DIA_INICIO_PERIODO en adelante: se certifica el mes actual (ventana normal).
# Es el valor DEFAULT/fallback: el admin puede sobreescribirlo en runtime
# (ver ParametrosService, parámetro "dia_inicio_periodo_certificacion").
DIA_INICIO_PERIODO = 29

# ── Firmas secuenciales de Actas (Financiera → Abogado → Jefe) ────────────────
TIPOS_FIRMA_CORR = ("corr", "gd", "secop")
TIPOS_FIRMA_ACTAS = ("financiera", "abogado", "jefe")

ORDEN_FIRMAS_ACTAS = {
    "acta_compromiso": ("jefe",),
    "acta_recibo_entrega_cps": ("financiera", "abogado", "jefe"),        # Balance General CPS
    "acta_recibo_entrega_cps_real": ("financiera", "abogado", "jefe"),   # Acta recibo y entrega CPS
}


class CertificacionService:
    def __init__(self) -> None:
        self.repo = CertificacionRepositorio()



    # ──────────────────────────────────────────────────────────────
    # Helpers de período
    # ──────────────────────────────────────────────────────────────

    def _ahora_bogota(self) -> datetime:
        return datetime.now(ZONA_BOGOTA)

    def _dia_inicio_periodo(self) -> int:
        """Día del mes en que se abre la ventana normal de certificación.
        Configurable por el admin; cae a DIA_INICIO_PERIODO si no está definido."""
        try:
            from app.services.parametros_service import ParametrosService
            return ParametrosService().obtener("dia_inicio_periodo_certificacion")
        except Exception:
            return DIA_INICIO_PERIODO

    def periodo_certificable(self) -> tuple:
        """Devuelve (año, mes) del período que se puede certificar hoy.

        Antes del día de inicio: mes anterior (ventana de ponerse al día).
        Desde el día de inicio: mes actual (ventana normal).
        """
        ahora = self._ahora_bogota()
        if ahora.day >= self._dia_inicio_periodo():
            return ahora.year, ahora.month
        if ahora.month == 1:
            return ahora.year - 1, 12
        return ahora.year, ahora.month - 1

    def es_mes_anterior(self) -> bool:
        """True si el período certificable es el mes anterior (antes del día de inicio)."""
        return self._ahora_bogota().day < self._dia_inicio_periodo()

    def _generar_hash(self, usuario_id: str, año: int, mes: int, supervisor_id: str, ts_iso: str) -> str:
        """HMAC-SHA256 firmado con SECRET_KEY. Toma los primeros 16 hex → XXXX-XXXX-XXXX-XXXX."""
        mensaje = f"{usuario_id}:{año}:{mes}:{supervisor_id}:{ts_iso}"
        digest = hmac.new(
            configuracion.secret_key.encode("utf-8"),
            mensaje.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:16].upper()
        return f"{digest[:4]}-{digest[4:8]}-{digest[8:12]}-{digest[12:16]}"

    def es_periodo_abierto(self) -> bool:
        """Siempre abierto: antes del 29 se certifica el mes anterior,
        del 29 en adelante se certifica el mes actual."""
        return True

    def _construir_rango_periodos(self, contratos: list) -> List[tuple]:
        """Genera la lista descendente de (año, mes) desde el mes de inicio del
        contrato más antiguo (fecha_inicio) hasta el período certificable actual,
        ambos inclusive. Si no hay contratos con fecha_inicio, devuelve solo el
        período certificable actual."""
        año_max, mes_max = self.periodo_certificable()

        fechas_inicio = [c.get("fecha_inicio") for c in contratos if c.get("fecha_inicio")]
        if not fechas_inicio:
            return [(año_max, mes_max)]

        fecha_min = min(fechas_inicio)
        if fecha_min.tzinfo is None:
            fecha_min = fecha_min.replace(tzinfo=timezone.utc)
        fecha_min_bogota = fecha_min.astimezone(ZONA_BOGOTA)
        año_min, mes_min = fecha_min_bogota.year, fecha_min_bogota.month

        periodos = []
        año, mes = año_max, mes_max
        while (año, mes) >= (año_min, mes_min):
            periodos.append((año, mes))
            mes -= 1
            if mes == 0:
                mes = 12
                año -= 1
        return periodos

    def periodos_disponibles_usuario(self, usuario_id: str) -> List[tuple]:
        """Períodos (año, mes) seleccionables por este contratista en 'Formatos de
        contrato': desde el inicio de su contrato más antiguo hasta el período
        certificable actual, orden descendente (más reciente primero)."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        usuario = UsuarioRepositorio().buscar_por_id(usuario_id)
        contratos = (usuario.get("contratos") or []) if usuario else []
        return self._construir_rango_periodos(contratos)

    def periodos_disponibles_global(self) -> List[tuple]:
        """Períodos (año, mes) seleccionables en 'Sup. Formatos': desde el contrato
        más antiguo registrado en todo el sistema hasta el período certificable
        actual, orden descendente."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        todos_contratos = []
        for usuario in UsuarioRepositorio().listar():
            todos_contratos.extend(usuario.get("contratos") or [])
        return self._construir_rango_periodos(todos_contratos)

    def leyenda_periodo(self, año: int, mes: int) -> str:
        """Texto coherente con el período efectivamente indicado: el actual, el mes
        anterior dentro de la ventana automática de gracia, o un período pasado
        elegido manualmente. Reemplaza los mensajes hardcodeados que asumían que el
        único período posible era 'hoy' o 'el mes anterior automático'."""
        nombre_mes = MESES_ES[mes - 1]
        if (año, mes) == self.periodo_certificable():
            if self.es_mes_anterior():
                dia_cierre = self._dia_inicio_periodo() - 1
                return (
                    f"Período anterior — {nombre_mes} {año} "
                    f"(ponerse al día, disponible hasta el día {dia_cierre} del mes en curso)"
                )
            return f"Período actual — {nombre_mes} {año}"
        return f"Período pasado — {nombre_mes} {año} (gestión retroactiva)"

    # ──────────────────────────────────────────────────────────────
    # Consultas de certificaciones
    # ──────────────────────────────────────────────────────────────

    def obtener_certificacion_periodo_actual(
        self, usuario_id: str, tipo_formato: str = None, año: int = None, mes: int = None
    ) -> Optional[Dict]:
        """Devuelve la certificación del período dado (por defecto, el período
        certificable hoy: mes actual o anterior)."""
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        return self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, tipo_formato)

    def firmar_y_generar_dependencia(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        ahora_utc = datetime.now(timezone.utc)
        
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "dependencia_economica")
        
        hash_code = (
            cert_existente["hash_verificacion"]
            if cert_existente and cert_existente.get("hash_verificacion")
            else self._generar_hash(usuario_id, año, mes, usuario_id, ahora_utc.isoformat())
        )
        
        campos = {
            "estado": "aprobado",  # Ya queda aprobado porque lo firma el contratista
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "dependencia_economica",
            "hash_verificacion": hash_code,
            "creado_en": ahora_utc,
        }
        
        if cert_existente:
            self.repo.actualizar(str(cert_existente["_id"]), campos)
        else:
            campos.update({
                "usuario_id": ObjectId(usuario_id),
                "nombre_usuario": nombre_usuario,
                "año": año,
                "mes": mes,
            })
            self.repo.crear(campos)
    def firmar_y_generar_cuenta_cobro(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        ahora_utc = datetime.now(timezone.utc)
        
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "cuenta_cobro")
        
        hash_code = (
            cert_existente["hash_verificacion"]
            if cert_existente and cert_existente.get("hash_verificacion")
            else self._generar_hash(usuario_id, año, mes, usuario_id, ahora_utc.isoformat())
        )
        
        campos = {
            "estado": "aprobado",
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "cuenta_cobro",
            "hash_verificacion": hash_code,
            "creado_en": ahora_utc,
        }
        
        if cert_existente:
            self.repo.actualizar(str(cert_existente["_id"]), campos)
        else:
            campos.update({
                "usuario_id": ObjectId(usuario_id),
                "nombre_usuario": nombre_usuario,
                "año": año,
                "mes": mes,
            })
            self.repo.crear(campos)
        return True

    def firmar_y_generar_retencion_primera(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        ahora_utc = datetime.now(timezone.utc)
        
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "retencion_fuente_primera")
        
        hash_code = (
            cert_existente["hash_verificacion"]
            if cert_existente and cert_existente.get("hash_verificacion")
            else self._generar_hash(usuario_id, año, mes, usuario_id, ahora_utc.isoformat())
        )
        
        campos = {
            "estado": "aprobado",  # Ya queda aprobado porque lo firma el contratista
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "retencion_fuente_primera",
            "hash_verificacion": hash_code,
            "creado_en": ahora_utc,
        }
        
        if cert_existente:
            self.repo.actualizar(str(cert_existente["_id"]), campos)
        else:
            campos.update({
                "usuario_id": ObjectId(usuario_id),
                "nombre_usuario": nombre_usuario,
                "año": año,
                "mes": mes,
            })
            self.repo.crear(campos)
        return True

    def firmar_y_generar_retencion_segunda(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        ahora_utc = datetime.now(timezone.utc)
        
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "retencion_fuente_segunda")
        
        hash_code = (
            cert_existente["hash_verificacion"]
            if cert_existente and cert_existente.get("hash_verificacion")
            else self._generar_hash(usuario_id, año, mes, usuario_id, ahora_utc.isoformat())
        )
        
        campos = {
            "estado": "aprobado",  # Ya queda aprobado porque lo firma el contratista
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "retencion_fuente_segunda",
            "hash_verificacion": hash_code,
            "creado_en": ahora_utc,
        }
        
        if cert_existente:
            self.repo.actualizar(str(cert_existente["_id"]), campos)
        else:
            campos.update({
                "usuario_id": ObjectId(usuario_id),
                "nombre_usuario": nombre_usuario,
                "año": año,
                "mes": mes,
            })
            self.repo.crear(campos)
        return True

    def firmar_y_generar_acta_compromiso(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "acta_compromiso")
        if cert_existente:
            return True

        ahora_utc = datetime.now(timezone.utc)
        campos = {
            "usuario_id": ObjectId(usuario_id),
            "nombre_usuario": nombre_usuario,
            "año": año,
            "mes": mes,
            "estado": "pendiente",  # Se aprueba cuando el Jefe firma (ver registrar_firma_actas)
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "acta_compromiso",
            "creado_en": ahora_utc,
        }
        self.repo.crear(campos)
        return True

    def firmar_y_generar_acta_recibo_entrega(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        from app.services.usuario_service import UsuarioService
        req_bg = UsuarioService().validar_datos_balance_general_cps(usuario_id)
        if not req_bg["valido"]:
            raise ValueError(f"Faltan requisitos para generar el Balance General CPS: {', '.join(req_bg['faltantes'])}")

        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "acta_recibo_entrega_cps")
        if cert_existente:
            return True

        ahora_utc = datetime.now(timezone.utc)
        campos = {
            "usuario_id": ObjectId(usuario_id),
            "nombre_usuario": nombre_usuario,
            "año": año,
            "mes": mes,
            "estado": "pendiente",  # Se aprueba cuando Financiera → Abogado → Jefe firman (ver registrar_firma_actas)
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "acta_recibo_entrega_cps",
            "creado_en": ahora_utc,
        }
        self.repo.crear(campos)
        return True

    def firmar_y_generar_acta_recibo_entrega_cps_real(
        self, usuario_id: str, nombre_usuario: str, año: int = None, mes: int = None
    ) -> bool:
        from app.services.usuario_service import UsuarioService
        req_acta = UsuarioService().validar_datos_acta_recibo_entrega_cps(usuario_id)
        if not req_acta["valido"]:
            raise ValueError(f"Faltan requisitos para generar el Acta de Recibo y Entrega CPS: {', '.join(req_acta['faltantes'])}")

        if año is None or mes is None:
            año, mes = self.periodo_certificable()
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "acta_recibo_entrega_cps_real")
        if cert_existente:
            return True

        ahora_utc = datetime.now(timezone.utc)
        campos = {
            "usuario_id": ObjectId(usuario_id),
            "nombre_usuario": nombre_usuario,
            "año": año,
            "mes": mes,
            "estado": "pendiente",  # Se aprueba cuando Financiera → Abogado → Jefe firman (ver registrar_firma_actas)
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "acta_recibo_entrega_cps_real",
            "creado_en": ahora_utc,
        }
        self.repo.crear(campos)
        return True




    def obtener_historial(self, usuario_id: str) -> List[Dict]:
        return self.repo.listar_por_usuario(usuario_id)

    def verificar_certificado(self, codigo: str) -> Optional[Dict]:
        """Busca un certificado por su hash de verificación. Retorna el doc o None."""
        codigo_normalizado = codigo.strip().upper().replace(" ", "")
        return self.repo.buscar_por_hash(codigo_normalizado)

    def obtener_empleados_para_certificar(self, tipo_formato: str = None) -> List[Dict]:
        """Lista todos los colaboradores con correspondencia, estado de firmas y contrato activo."""
        from app.services.correspondencia_service import CorrespondenciaService
        from app.repositories.usuario_repo import UsuarioRepositorio

        corr_service = CorrespondenciaService()
        usuario_repo = UsuarioRepositorio()
        año, mes = self.periodo_certificable()

        estado_formatos = corr_service.obtener_estado_formatos()
        todos_usuarios = {str(u["_id"]): u for u in usuario_repo.listar()}
        certs_mes = {
            str(c["usuario_id"]): c
            for c in self.repo.listar_por_periodo(año, mes, tipo_formato)
        }

        resultados = []
        for estado in estado_formatos:
            uid = estado["usuario_id"]
            cert = certs_mes.get(uid)
            firmas = cert.get("firmas", {}) if cert else {}

            usuario_data = todos_usuarios.get(uid, {})
            contratos = usuario_data.get("contratos") or []
            contrato = self._contrato_vigente(contratos)
            tiene_contrato = bool(contrato.get("numero"))

            resultados.append({
                "usuario_id": uid,
                "nombre": estado["responsable"],
                "cantidad_pendientes": estado["cantidad_pendientes"],
                "cantidad_vencidas": estado["cantidad_vencidas"],
                "al_dia": estado["cantidad_vencidas"] == 0,
                "certificacion": cert,
                "firmas": firmas,
                "tiene_contrato": tiene_contrato,
                "numero_contrato": contrato.get("numero"),
                "tipo_contrato": contrato.get("tipo"),
            })

        return resultados

    # ──────────────────────────────────────────────────────────────
    # Configuración de firmantes designados
    # ──────────────────────────────────────────────────────────────

    def obtener_firmantes_config(
        self, categoria: str = "firmantes_certificacion", tipos: tuple = TIPOS_FIRMA_CORR
    ) -> Dict:
        """Devuelve los firmantes designados de la categoría dada (por defecto, corr/gd/secop)."""
        from app.repositories.opciones_repo import ConfiguracionRepositorio
        doc = ConfiguracionRepositorio().obtener(categoria)
        vacio = {t: None for t in tipos}
        return doc.get("firmantes", vacio) if doc else vacio

    def guardar_firmante(
        self,
        tipo: str,
        usuario_id: Optional[str],
        nombre: Optional[str],
        categoria: str = "firmantes_certificacion",
    ) -> bool:
        """Admin designa quién es el firmante de un tipo dado, dentro de la categoría indicada.
        Sincroniza el permiso certificacion.firmar_<tipo> en permisos_extra del usuario.
        """
        from app.repositories.opciones_repo import ConfiguracionRepositorio
        from app.repositories.usuario_repo import UsuarioRepositorio

        perm = f"certificacion.firmar_{tipo}"
        config = self.obtener_firmantes_config(categoria)
        repo_conf = ConfiguracionRepositorio()
        repo_usr = UsuarioRepositorio()

        old = config.get(tipo) or {}
        old_uid = str(old.get("usuario_id", "")) if old and old.get("usuario_id") else None

        # Remover permiso del firmante anterior si cambia
        if old_uid and old_uid != usuario_id:
            old_user = repo_usr.buscar_por_id(old_uid)
            if old_user:
                permisos_limpios = [p for p in old_user.get("permisos_extra", []) if p != perm]
                repo_usr.actualizar(old_uid, {"permisos_extra": permisos_limpios})

        # Asignar permiso al nuevo firmante
        if usuario_id:
            new_user = repo_usr.buscar_por_id(usuario_id)
            if new_user:
                permisos_new = list(set(new_user.get("permisos_extra", []) + [perm]))
                repo_usr.actualizar(usuario_id, {"permisos_extra": permisos_new})

        valor = {"usuario_id": usuario_id, "nombre": nombre} if usuario_id else None
        repo_conf.upsert(
            categoria,
            {
                "categoria": categoria,
                f"firmantes.{tipo}": valor,
            },
        )
        return True

    # ──────────────────────────────────────────────────────────────
    # Registro de firmas por período
    # ──────────────────────────────────────────────────────────────

    def registrar_firma(
        self,
        empleado_id: str,
        empleado_nombre: str,
        tipo: str,
        firmante_id: str,
        firmante_nombre: str,
        comentario: str | None = None,
    ) -> bool:
        """Registra la aprobación del firmante. Si con esta firma se completan
        las 3 y el contratista cumple requisitos, se certifica automáticamente."""
        año, mes = self.periodo_certificable()
        self.repo.registrar_firma(
            empleado_id, empleado_nombre, año, mes, tipo, firmante_id, firmante_nombre, comentario
        )
        self._intentar_auto_certificar(
            empleado_id, empleado_nombre, firmante_id, firmante_nombre, año, mes
        )
        return True

    def _intentar_auto_certificar(
        self,
        empleado_id: str,
        empleado_nombre: str,
        firmante_id: str,
        firmante_nombre: str,
        año: int,
        mes: int,
    ) -> None:
        """Auto-certifica cuando hay 3 firmas + contrato activo (sin importar estado de correspondencia)."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        cert = self.repo.buscar_por_usuario_periodo(empleado_id, año, mes)
        if not cert or cert.get("estado") == "aprobado":
            return

        firmas = cert.get("firmas", {})
        if not all(firmas.get(t) for t in ("corr", "gd", "secop")):
            return

        usuario = UsuarioRepositorio().buscar_por_id(empleado_id)
        contratos = (usuario.get("contratos") or []) if usuario else []
        if not self._contrato_vigente(contratos).get("numero"):
            return

        self.certificar_empleado(empleado_id, empleado_nombre, firmante_id, firmante_nombre)

    def revocar_firma(self, empleado_id: str, tipo: str) -> bool:
        """Revoca una firma previamente registrada."""
        año, mes = self.periodo_certificable()
        return self.repo.revocar_firma(empleado_id, año, mes, tipo)

    def registrar_firma_actas(
        self,
        cert_id: str,
        rol: str,
        firmante_id: str,
        firmante_nombre: str,
        comentario: str | None = None,
    ) -> bool:
        """Registra la aprobación de un rol (financiera/abogado/jefe) sobre un formato
        de actas. Exige que el rol anterior en ORDEN_FIRMAS_ACTAS ya haya firmado. Si con
        esta firma se completa el orden requerido, aprueba el documento y genera (o
        preserva) su hash de verificación."""
        cert = self.repo.buscar_por_id(cert_id)
        if not cert:
            raise ValueError("No existe el formato especificado.")

        tipo_formato = cert.get("tipo_formato")
        orden = ORDEN_FIRMAS_ACTAS.get(tipo_formato)
        if not orden or rol not in orden:
            raise ValueError(f"El rol '{rol}' no aplica para el formato '{tipo_formato}'.")

        idx = orden.index(rol)
        if idx > 0:
            rol_anterior = orden[idx - 1]
            if not (cert.get("firmas") or {}).get(rol_anterior):
                raise ValueError(
                    f"Aún falta la firma de '{rol_anterior}' antes de poder firmar como '{rol}'."
                )

        self.repo.registrar_firma_actas_por_id(
            cert_id, rol, firmante_id, firmante_nombre, comentario
        )

        cert_actualizado = self.repo.buscar_por_id(cert_id)
        firmas = cert_actualizado.get("firmas") or {}
        if all(firmas.get(r) for r in orden):
            ahora_utc = datetime.now(timezone.utc)
            usuario_id = str(cert_actualizado.get("usuario_id"))
            año = cert_actualizado.get("año")
            mes = cert_actualizado.get("mes")
            hash_code = cert_actualizado.get("hash_verificacion") or self._generar_hash(
                usuario_id, año, mes, firmante_id, ahora_utc.isoformat()
            )
            self.repo.actualizar(str(cert_actualizado["_id"]), {
                "estado": "aprobado",
                "hash_verificacion": hash_code,
            })
        return True

    def revocar_firma_actas(self, cert_id: str, rol: str) -> bool:
        """Revoca la firma de un rol y, en cascada, las de los roles posteriores en el
        orden (que dependían de esta). Registra un evento por cada firma revocada en
        cascada para que el firmante afectado sepa por qué desapareció, y vuelve el
        documento a 'pendiente' si estaba aprobado."""
        cert = self.repo.buscar_por_id(cert_id)
        if not cert:
            return False

        tipo_formato = cert.get("tipo_formato")
        orden = ORDEN_FIRMAS_ACTAS.get(tipo_formato)
        if not orden or rol not in orden:
            raise ValueError(f"El rol '{rol}' no aplica para el formato '{tipo_formato}'.")

        idx = orden.index(rol)
        firmas = cert.get("firmas") or {}
        posteriores_firmados = [r for r in orden[idx + 1:] if firmas.get(r)]
        roles_a_borrar = [rol] + posteriores_firmados

        self.repo.revocar_firmas_actas_por_id(cert_id, roles_a_borrar)

        ahora_utc = datetime.now(timezone.utc)
        for r in posteriores_firmados:
            self.repo.agregar_evento_actas_por_id(cert_id, {
                "tipo": "revocacion_cascada",
                "rol_revocado": r,
                "causada_por": rol,
                "fecha": ahora_utc,
            })

        if cert.get("estado") == "aprobado":
            self.repo.actualizar(str(cert["_id"]), {"estado": "pendiente"})

        return True

    def recuperar_auto_cert(self, empleado_id: str, cert: dict) -> bool:
        """Certifica retroactivamente si el cert ya tiene las 3 firmas + contrato activo
        pero quedó en 'pendiente' por un fallo anterior en _intentar_auto_certificar.
        Retorna True si se certificó ahora."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        if not cert or cert.get("estado") == "aprobado":
            return False

        firmas = cert.get("firmas", {})
        if not all(firmas.get(t) for t in ("corr", "gd", "secop")):
            return False

        usuario = UsuarioRepositorio().buscar_por_id(empleado_id)
        contratos = (usuario.get("contratos") or []) if usuario else []
        if not self._contrato_vigente(contratos).get("numero"):
            return False

        # Usar la última firma como firmante registrado en el certificado
        ultima_firma = next(
            (firmas[t] for t in ("secop", "gd", "corr") if firmas.get(t)), None
        )
        firmante_id = str(ultima_firma.get("firmante_id", "")) if ultima_firma else ""
        firmante_nombre = ultima_firma.get("firmante_nombre", "") if ultima_firma else ""
        nombre_empleado = cert.get("nombre_usuario", "")

        self.certificar_empleado(empleado_id, nombre_empleado, firmante_id, firmante_nombre)
        return True

    # ──────────────────────────────────────────────────────────────
    # Acción de certificar
    # ──────────────────────────────────────────────────────────────

    def certificar_empleado(
        self,
        usuario_id_empleado: str,
        nombre_empleado: str,
        supervisor_id: str,
        supervisor_nombre: str,
        observaciones: str = "",
    ) -> bool:
        """Certifica al colaborador para el período actual.
        Si ya existe un hash previo, lo preserva para que los PDFs ya entregados
        sigan siendo verificables con el código original."""
        año, mes = self.periodo_certificable()
        ahora_utc = datetime.now(timezone.utc)

        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id_empleado, año, mes)

        # Preservar el hash si ya existe — un PDF descargado debe seguir siendo válido
        hash_code = (
            cert_existente["hash_verificacion"]
            if cert_existente and cert_existente.get("hash_verificacion")
            else self._generar_hash(usuario_id_empleado, año, mes, supervisor_id, ahora_utc.isoformat())
        )

        campos = {
            "estado": "aprobado",
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "observaciones": observaciones.strip() or None,
            "hash_verificacion": hash_code,
            "aprobado_por": {
                "usuario_id": ObjectId(supervisor_id),
                "nombre": supervisor_nombre,
                "fecha": ahora_utc,
            },
        }

        if cert_existente:
            self.repo.actualizar(str(cert_existente["_id"]), campos)
        else:
            campos.update({
                "usuario_id": ObjectId(usuario_id_empleado),
                "nombre_usuario": nombre_empleado,
                "año": año,
                "mes": mes,
                "tipo_formato": "gestion_correspondencia",
                "creado_en": ahora_utc,
            })
            self.repo.crear(campos)

        return True

    # ──────────────────────────────────────────────────────────────
    # Generación de PDF
    # ──────────────────────────────────────────────────────────────

    # Días de gracia tras la fecha de fin del contrato (o su prórroga) durante los
    # cuales sigue considerándose "vigente" para efectos de generar/descargar formatos.
    DIAS_GRACIA_CONTRATO_VIGENTE = 60

    @classmethod
    def _contrato_vigente(cls, contratos: list) -> dict:
        """Devuelve el contrato activo hoy (sin fecha_fin, con fecha_fin futura, o dentro
        del período de gracia posterior a su fin), incluyendo prórrogas.
        Si no hay contratos activos hoy, retorna {} (no cae en fallback de vencidos)."""
        if not contratos:
            return {}
        hoy = datetime.now(ZONA_BOGOTA).date()
        activos = []
        for c in contratos:
            fecha_fin = c.get("fecha_fin")

            # Considerar prórroga si existe para la vigencia real
            prorroga = c.get("prorrogra_contrato") or {}
            if prorroga.get("tiene_prorroga") and prorroga.get("fecha_prorrogra"):
                fecha_fin = prorroga.get("fecha_prorrogra")

            if fecha_fin:
                if fecha_fin.tzinfo is None:
                    from datetime import timezone as _tz
                    fecha_fin = fecha_fin.replace(tzinfo=_tz.utc)
                fecha_limite = fecha_fin.astimezone(ZONA_BOGOTA).date() + timedelta(
                    days=cls.DIAS_GRACIA_CONTRATO_VIGENTE
                )
                if fecha_limite >= hoy:
                    activos.append(c)
            else:
                activos.append(c)
                
        if not activos:
            return {}
            
        activos.sort(
            key=lambda c: c.get("fecha_inicio") or datetime.min,
            reverse=True,
        )
        return activos[0]

    @staticmethod
    def _contrato_para_periodo(contratos: list, anio: int, mes: int) -> dict:
        """Devuelve el contrato que estaba activo durante el año y mes indicados.
        Si no hay ninguno que coincida, retorna el de fecha_inicio más reciente (comportamiento de fallback)."""
        if not contratos:
            return {}
        
        import calendar
        from datetime import datetime, timezone
        
        # Rango de fechas del período (zona horaria Bogotá)
        _, ultimo_dia = calendar.monthrange(anio, mes)
        inicio_periodo = datetime(anio, mes, 1, 0, 0, 0, tzinfo=ZONA_BOGOTA)
        fin_periodo = datetime(anio, mes, ultimo_dia, 23, 59, 59, tzinfo=ZONA_BOGOTA)
        
        coincidentes = []
        for c in contratos:
            fi = c.get("fecha_inicio")
            ff = c.get("fecha_fin")
            
            # Prórroga si existe
            prorroga = c.get("prorrogra_contrato") or {}
            if prorroga.get("tiene_prorroga") and prorroga.get("fecha_prorrogra"):
                ff = prorroga.get("fecha_prorrogra")
                
            if not fi:
                continue
                
            # Normalizar zonas horarias a Bogotá
            if fi.tzinfo is None:
                fi = fi.replace(tzinfo=timezone.utc)
            fi_bog = fi.astimezone(ZONA_BOGOTA)
            
            ff_bog = None
            if ff:
                if ff.tzinfo is None:
                    ff = ff.replace(tzinfo=timezone.utc)
                ff_bog = ff.astimezone(ZONA_BOGOTA)
                
            # Activo si inicio es <= fin_periodo y fin es >= inicio_periodo (o no tiene fin)
            if fi_bog <= fin_periodo:
                if ff_bog is None or ff_bog >= inicio_periodo:
                    coincidentes.append(c)
                    
        pool = coincidentes or contratos
        pool.sort(
            key=lambda c: c.get("fecha_inicio") or datetime.min,
            reverse=True,
        )
        return pool[0]

    def _contrato_relevante(self, contratos: list, año: int, mes: int) -> dict:
        """Contrato a usar para mostrar/validar en el período (año, mes): el vigente
        hoy en tiempo real si es el período certificable actual (preserva el
        comportamiento exacto de hoy cuando nadie toca el selector), o el vigente
        históricamente en ese año/mes si es un período pasado elegido manualmente."""
        if (año, mes) == self.periodo_certificable():
            return self._contrato_vigente(contratos)
        return self._contrato_para_periodo(contratos, año, mes)

    def generar_pdf(self, certificacion: Dict) -> bytes:
        """Genera el PDF del certificado con ReportLab en memoria."""
        if certificacion.get("tipo_formato") == "dependencia_economica":
            return self.generar_pdf_dependencia(certificacion)
        if certificacion.get("tipo_formato") == "cuenta_cobro":
            return self.generar_pdf_cuenta_cobro(certificacion)
        if certificacion.get("tipo_formato") == "retencion_fuente_primera":
            return self.generar_pdf_retencion_fuente_primera(certificacion)
        if certificacion.get("tipo_formato") == "retencion_fuente_segunda":
            return self.generar_pdf_retencion_fuente_segunda(certificacion)
        if certificacion.get("tipo_formato") == "acta_compromiso":
            return self.generar_pdf_acta_compromiso(certificacion)
        if certificacion.get("tipo_formato") == "acta_recibo_entrega_cps":
            return self.generar_pdf_acta_recibo_entrega(certificacion)
        if certificacion.get("tipo_formato") == "acta_recibo_entrega_cps_real":
            return self.generar_pdf_acta_recibo_entrega_real(certificacion)

        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, HRFlowable,
        )

        NARANJA = HexColor("#FF8C00")
        CAFE = HexColor("#3D1E0A")
        NEGRO = HexColor("#000000")
        GRIS = HexColor("#777777")
        GRIS_TABLA = HexColor("#F5F5F5")

        # ── datos del usuario (contrato activo, cédula) ──
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_id = str(certificacion.get("usuario_id", ""))
        usuario_data: dict = {}
        if usuario_id:
            try:
                usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
            except Exception:
                pass
        contratos = usuario_data.get("contratos") or []
        año_cert = certificacion.get("año")
        mes_cert = certificacion.get("mes", 1)
        contrato = self._contrato_para_periodo(contratos, año_cert, mes_cert)
        numero_contrato = contrato.get("numero") or "—"
        cedula = usuario_data.get("numero_documento") or "—"

        nombre = certificacion.get("nombre_usuario", "")
        año = certificacion.get("año", "")
        mes_num = certificacion.get("mes", 1)
        mes_nombre = MESES_ES[mes_num - 1]
        hash_code = certificacion.get("hash_verificacion", "")
        obs = certificacion.get("observaciones") or ""

        fecha_corte = certificacion.get("fecha_corte")
        if fecha_corte:
            fc_bogota = utc_a_bogota(fecha_corte)
            dia_expedicion = fc_bogota.strftime("%d").lstrip("0") or "1"
            mes_expedicion = MESES_ES[fc_bogota.month - 1]
            año_expedicion = fc_bogota.strftime("%Y")
        else:
            ahora = datetime.now(ZONA_BOGOTA)
            dia_expedicion = str(ahora.day)
            mes_expedicion = MESES_ES[ahora.month - 1]
            año_expedicion = str(ahora.year)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=2.3 * cm,
            rightMargin=2.3 * cm,
            topMargin=0.8 * cm,
            bottomMargin=1.5 * cm,
        )

        estilos = getSampleStyleSheet()

        s_inst_bold = ParagraphStyle(
            "inst_bold", parent=estilos["Normal"],
            fontSize=9, textColor=CAFE, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceAfter=1, leading=12,
        )
        s_titulo = ParagraphStyle(
            "titulo", parent=estilos["Normal"],
            fontSize=10, textColor=CAFE, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceAfter=2, leading=13,
        )
        s_cuerpo = ParagraphStyle(
            "cuerpo", parent=estilos["Normal"],
            fontSize=8.5, alignment=TA_JUSTIFY, leading=12, spaceAfter=5,
        )
        s_bullet = ParagraphStyle(
            "bullet", parent=estilos["Normal"],
            fontSize=8.5, alignment=TA_JUSTIFY, leading=12, spaceAfter=3,
            leftIndent=12,
        )
        s_pie = ParagraphStyle(
            "pie", parent=estilos["Normal"],
            fontSize=7, textColor=GRIS, alignment=TA_CENTER,
        )

        def _watermark(canvas_obj, _doc):
            from reportlab.lib.colors import Color
            w, h = letter

            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica", 7.5)
            canvas_obj.setFillColor(Color(0.68, 0.68, 0.68, alpha=0.30))
            canvas_obj.translate(w / 2, h / 2)
            canvas_obj.rotate(38)
            for xi in range(-5, 6):
                for yi in range(-14, 15):
                    canvas_obj.drawCentredString(xi * 112, yi * 42, "INVIAS  SRTI")
            canvas_obj.restoreState()

            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica-Bold", 48)
            canvas_obj.setFillColor(Color(0.58, 0.58, 0.58, alpha=0.30))
            canvas_obj.translate(w / 2, h / 2)
            canvas_obj.rotate(45)
            canvas_obj.drawCentredString(0, 42, nombre.upper())
            canvas_obj.drawCentredString(0, -32, f"{mes_nombre.upper()} {año}")
            canvas_obj.restoreState()

            canvas_obj.saveState()
            nb = Color(1.0, 0.549, 0.0, alpha=0.55)
            canvas_obj.setStrokeColor(nb)
            canvas_obj.setLineWidth(1.2)
            canvas_obj.rect(18, 18, w - 36, h - 36)
            canvas_obj.setLineWidth(0.35)
            canvas_obj.rect(23, 23, w - 46, h - 46)
            canvas_obj.restoreState()

            canvas_obj.saveState()
            nf = Color(1.0, 0.549, 0.0, alpha=0.58)
            canvas_obj.setFillColor(nf)
            canvas_obj.setStrokeColor(nf)
            canvas_obj.setLineWidth(0.9)
            dm = 7
            arm = 20
            for cx, cy, dx, dy in [
                (28, 28, 1, 1), (w - 28, 28, -1, 1),
                (28, h - 28, 1, -1), (w - 28, h - 28, -1, -1),
            ]:
                p = canvas_obj.beginPath()
                p.moveTo(cx, cy + dm)
                p.lineTo(cx + dm, cy)
                p.lineTo(cx, cy - dm)
                p.lineTo(cx - dm, cy)
                p.close()
                canvas_obj.drawPath(p, stroke=1, fill=1)
                canvas_obj.line(cx, cy, cx + dx * arm, cy)
                canvas_obj.line(cx, cy, cx, cy + dy * arm)
            canvas_obj.setLineWidth(0.7)
            tk = 5
            for mx, my in [(w / 2, h - 18), (w / 2, 18), (18, h / 2), (w - 18, h / 2)]:
                canvas_obj.line(mx - tk, my, mx + tk, my)
                canvas_obj.line(mx, my - tk, mx, my + tk)
            canvas_obj.restoreState()

        story = []

        # ── Logo ──
        logo = os.path.join("app", "assets", "INVIAS_login_logo.png")
        if os.path.exists(logo):
            from reportlab.platypus import Image
            img = Image(logo, width=4 * cm, height=2 * cm, kind="proportional")
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 0.2 * cm))

        story.append(HRFlowable(width="100%", thickness=2, color=NARANJA))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph("INSTITUTO NACIONAL DE VÍAS – INVIAS", s_inst_bold))
        story.append(Paragraph("SUBDIRECCIÓN DE REGLAMENTACIÓN TÉCNICA E INNOVACIÓN", s_inst_bold))
        story.append(Paragraph("FORMATO DE CONTROL DE CORRESPONDENCIA Y PLATAFORMA SECOP II", s_titulo))
        story.append(Spacer(1, 0.25 * cm))
        story.append(HRFlowable(width="100%", thickness=1, color=NARANJA))
        story.append(Spacer(1, 0.3 * cm))

        # ── Tabla de identificación ──
        col_lbl = 5.2 * cm
        col_val = doc.width - col_lbl
        id_tabla = Table(
            [
                ["Número de contrato", numero_contrato],
                ["Contratista", nombre],
                ["Cédula del contratista", cedula],
            ],
            colWidths=[col_lbl, col_val],
            rowHeights=0.6 * cm,
        )
        id_tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (0, -1), GRIS_TABLA),
            ("TEXTCOLOR", (0, 0), (-1, -1), NEGRO),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(id_tabla)
        story.append(Spacer(1, 0.35 * cm))

        # ── Cuerpo principal ──
        story.append(Paragraph(
            f"En cumplimiento y ejercicio de la función de supervisión y/o ordenación del gasto "
            f"(según corresponda) procede la suscrita con la verificación del cumplimiento adecuado "
            f"de las obligaciones establecidas en el Anexo del Contrato Electrónico – Clausulado "
            f"General de Contrato de Prestación de Servicios Profesionales y/o de Apoyo a la Gestión, "
            f"para el periodo del mes de <b>{mes_nombre}</b> de <b>{año}</b>; en consecuencia, se deja "
            f"constancia de que, una vez efectuada la revisión correspondiente a los soportes "
            f"documentales, matrices de seguimiento y plataforma SECOP II, el(a) contratista:",
            s_cuerpo,
        ))

        # ── Obligaciones (bullets) ──
        obligaciones = [
            "Mantuvo actualizada la información relacionada con la correspondencia, oficios, "
            "memorandos y demás asuntos a su cargo en las bases de datos y sistemas de información "
            "dispuestos por el INVIAS, conforme a los lineamientos institucionales y a los parámetros "
            "definidos para el seguimiento contractual. (Obligación general 5)",

            "Cumplió con las actividades de gestión documental y archivo derivadas de la ejecución "
            "contractual, de acuerdo con los lineamientos institucionales y las disposiciones aplicables "
            "del Archivo General de la Nación – AGN. (Obligación general 21)(NOAPLICA)",

            "Registró / actualizó en la plataforma SECOP II la información correspondiente al "
            "\"Plan de Pagos\", ubicada en la pestaña \"Ejecución del Contrato\", adjuntando el "
            "informe mensual de actividades, sus soportes y la planilla de aportes al Sistema de "
            "Seguridad Social Integral, para efectos de revisión y aprobación por parte del supervisor "
            "del contrato. (Obligación general 32)",

            "Se encuentra al día con la proyección, revisión, tramité y atención conforme los "
            "lineamientos establecidos en la Ley, respecto las solicitudes, peticiones, quejas, "
            "reclamos, sugerencias (PQRS), memorandos, comunicaciones internas o externas, que le "
            "sean asignados por el supervisor del contrato y que tengan relación con el objeto "
            "contractual y el alcance de la Subdirección de Reglamentación Técnica e Innovación "
            "(Obligación Especifica No. 7)",
        ]
        for ob in obligaciones:
            story.append(Paragraph(f"• {ob}", s_bullet))

        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            "La presente constancia se expide como soporte de verificación de cumplimiento de "
            "actividades objeto de seguimiento administrativo y documental, y constituye un insumo "
            "para el ejercicio de supervisión contractual para efectos del trámite de pago.",
            s_cuerpo,
        ))

        if obs:
            story.append(Paragraph(f"<i>Observaciones: {obs}</i>", s_cuerpo))

        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            f"Se expide a los <b>{dia_expedicion}</b> días del mes de "
            f"<b>{mes_expedicion}</b> de <b>{año_expedicion}</b>",
            s_cuerpo,
        ))

        story.append(Spacer(1, 0.25 * cm))

        # ── Firma: imagen pegada a la línea en una sola tabla ──
        ruta_firma = os.path.join("app", "assets", "Firma_Nestor.png")
        if os.path.exists(ruta_firma):
            from reportlab.platypus import Image as _Img
            firma_img = _Img(ruta_firma, width=5.2 * cm, height=2.6 * cm, kind="proportional")
            filas_firma = [
                [firma_img],
                ["Néstor Alfonso Navarro Tovar"],
                ["Contratista Subdirección de Reglamentación Técnica e Innovación"],
            ]
            firma_tabla = Table(filas_firma, colWidths=[8.5 * cm], hAlign="CENTER")
            firma_tabla.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("FONTNAME", (0, 1), (0, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 1), (0, 1), CAFE),
                # línea entre imagen y nombre — la firma la "toca"
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, HexColor("#AAAAAA")),
                ("TOPPADDING", (0, 0), (-1, 0), 0),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
                ("TOPPADDING", (0, 1), (-1, 1), 3),
            ]))
        else:
            filas_firma = [
                [""],
                ["Néstor Alfonso Navarro Tovar"],
                ["Contratista Subdirección de Reglamentación Técnica e Innovación"],
            ]
            firma_tabla = Table(filas_firma, colWidths=[8.5 * cm], rowHeights=[1.5 * cm, None, None], hAlign="CENTER")
            firma_tabla.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 1), (0, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 1), (0, 1), CAFE),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, HexColor("#AAAAAA")),
                ("TOPPADDING", (0, 1), (-1, 1), 3),
            ]))
        story.append(firma_tabla)

        story.append(Spacer(1, 0.4 * cm))

        # ── Código de verificación ──
        if hash_code:
            cod_tabla = Table(
                [[f"Código de verificación: {hash_code}"]],
                colWidths=[doc.width],
            )
            cod_tabla.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FFF3E0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), CAFE),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 1.2, NARANJA),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(cod_tabla)
            story.append(Spacer(1, 0.2 * cm))

        story.append(HRFlowable(width="100%", thickness=1, color=NARANJA))
        story.append(Spacer(1, 0.1 * cm))
        story.append(Paragraph(
            f"Documento generado automáticamente por el Sistema de Gestión de "
            f"Correspondencia SRTI-INVIAS · {dia_expedicion} de {mes_expedicion} de {año_expedicion}",
            s_pie,
        ))

        doc.build(story, onFirstPage=_watermark, onLaterPages=_watermark)
        buf.seek(0)
        return buf.getvalue()

    def generar_pdf_dependencia(self, certificacion: Dict) -> bytes:
        # ── Formato plano: documento en blanco, solo texto, sin marcas de agua,
        #    sin logos, sin colores corporativos y sin código de verificación
        #    visible (el hash se sigue guardando en la certificación, solo no se
        #    muestra). Aplica únicamente a este formato. ──
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor, black
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, Image,
        )

        # ── Paleta neutra: todo en negro sobre fondo blanco ──
        NEGRO   = black
        BORDE   = HexColor("#666666")

        # ── Datos del usuario ──
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_id   = str(certificacion.get("usuario_id", ""))
        usuario_data: dict = {}
        if usuario_id:
            try:
                usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
            except Exception:
                pass

        nombre    = usuario_data.get("nombre_completo", "")
        tipo_doc  = usuario_data.get("tipo_documento", "")
        cedula    = usuario_data.get("numero_documento")    or "—"
        lugar_exp = usuario_data.get("lugar_expedicion_documento") or "—"

        info_laboral     = usuario_data.get("informacion_laboral") or {}
        tributaria       = info_laboral.get("tributaria") or {}
        declarante_renta = tributaria.get("declarante_renta", False)
        dependientes     = info_laboral.get("dependientes") or []

        # Mes/año de EXPEDICIÓN = período al que corresponde el formato
        # (certificacion["mes"]/["año"]), no la fecha de generación. Así un
        # formato del período de mayo dice "se expide en el mes de MAYO".
        mes_periodo = certificacion.get("mes", 1)
        mes_exp     = MESES_ES[mes_periodo - 1]
        año_exp     = str(certificacion.get("año", ""))

        # fecha_fmt = fecha real de firma (bloque de firma), tomada de fecha_corte.
        fecha_corte = certificacion.get("fecha_corte")
        if fecha_corte:
            fecha_fmt = utc_a_bogota(fecha_corte).strftime("%d/%m/%Y")
        else:
            fecha_fmt = datetime.now(ZONA_BOGOTA).strftime("%d/%m/%Y")

        # ── Documento — mismos márgenes que formato 6 ──
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=2.3 * cm,
            rightMargin=2.3 * cm,
            topMargin=0.8 * cm,
            bottomMargin=1.5 * cm,
        )

        estilos = getSampleStyleSheet()

        # ── Estilos — texto plano en negro, sin colores corporativos ──
        s_inst_bold = ParagraphStyle(
            "dep4_inst", parent=estilos["Normal"],
            fontSize=9, textColor=NEGRO, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceAfter=1, leading=12,
        )
        s_titulo = ParagraphStyle(
            "dep4_tit", parent=estilos["Normal"],
            fontSize=10, textColor=NEGRO, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceAfter=2, leading=13,
        )
        s_cuerpo = ParagraphStyle(
            "dep4_cuerpo", parent=estilos["Normal"],
            fontSize=8.5, alignment=TA_JUSTIFY, leading=12, spaceAfter=5,
            textColor=NEGRO,
        )
        s_renta = ParagraphStyle(
            "dep4_renta", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_CENTER, leading=13, spaceAfter=5,
            fontName="Helvetica-Bold", textColor=NEGRO,
        )
        s_bullet = ParagraphStyle(
            "dep4_bullet", parent=estilos["Normal"],
            fontSize=8, alignment=TA_JUSTIFY, leading=11, spaceAfter=2,
            leftIndent=12, textColor=NEGRO,
        )
        s_cell = ParagraphStyle(
            "dep4_cell", parent=estilos["Normal"],
            fontSize=8, alignment=TA_CENTER, leading=10, textColor=NEGRO,
        )
        s_cellhdr = ParagraphStyle(
            "dep4_cellhdr", parent=estilos["Normal"],
            fontSize=8, fontName="Helvetica-Bold", alignment=TA_CENTER,
            leading=10, textColor=NEGRO,
        )

        # ── Story — sin marca de agua, sin logo, sin reglas de color ──
        story = []

        story.append(Paragraph("INSTITUTO NACIONAL DE VÍAS – INVIAS", s_inst_bold))
        story.append(Paragraph("SUBDIRECCIÓN DE REGLAMENTACIÓN TÉCNICA E INNOVACIÓN", s_inst_bold))
        story.append(Paragraph("CONDICIÓN DE DECLARANTE Y EXISTENCIA Y DEPENDENCIA ECONÓMICA", s_titulo))
        story.append(Spacer(1, 0.35 * cm))

        # Párrafo 1
        story.append(Paragraph(
            f"Yo, <b>{nombre.upper()}</b> identificado con <b>{tipo_doc}</b> No. <b>{cedula}</b>, "
            f"expedida en <b>{lugar_exp.upper()}</b>, ubicada en BOGOTÁ D.C. "
            f"En cumplimiento al parágrafo 2° del artículo 15 de la Ley 1607 de 2012, por el cual se modifica "
            f"el artículo 387 del E.T. y en concordancia con el parágrafo 4° de los artículos 2° y 3° del Decreto "
            f"0099 del 25 de enero del 2013, certifico a ustedes bajo la gravedad de juramento, mi condición:",
            s_cuerpo,
        ))

        # Condición tributaria
        renta_txt = "SI, DECLARANTE DE IMPUESTO SOBRE LA RENTA" if declarante_renta else "NO DECLARANTE DE IMPUESTO SOBRE LA RENTA"
        story.append(Paragraph(f"<u>{renta_txt}</u>", s_renta))

        # Párrafo 2
        story.append(Paragraph(
            "Declaro que mi ingreso en una proporción igual o superior a un ochenta por ciento (80%), "
            "corresponde a la prestación de servicios de manera personal o de la realización de una actividad "
            "económica por cuenta y riesgo del empleador o contratante, mediante una vinculación laboral o legal y "
            "reglamentaria o de cualquier otra naturaleza, independientemente de su denominación.",
            s_cuerpo,
        ))

        # Párrafo 3
        story.append(Paragraph(
            "Que la(s) siguiente(s) persona(s) se encuentra(n) a mi cargo en la calidad de dependiente(s):",
            s_cuerpo,
        ))

        # ── Tabla de dependientes — ancho completo ──
        t_data = [[
            Paragraph("<b>NOMBRE</b>",                          s_cellhdr),
            Paragraph("<b>TIPO DOC. ID.<br/>(C.C. / T.I.)</b>", s_cellhdr),
            Paragraph("<b>NÚMERO<br/>DOCUMENTO</b>",             s_cellhdr),
            Paragraph("<b>TIPO</b>",                             s_cellhdr),
        ]]
        for dep in dependientes:
            t_raw = (dep.get("tipo") or "").strip()
            letra = t_raw.replace("tipo_", "").replace("tipo", "").strip().upper()
            t_fmt = f"TIPO {letra}" if letra else "—"
            t_data.append([
                Paragraph((dep.get("nombre") or "").upper(), s_cell),
                Paragraph(dep.get("tipo_documento") or "—",  s_cell),
                Paragraph(dep.get("numero_documento") or "—", s_cell),
                Paragraph(t_fmt, s_cell),
            ])
        if len(t_data) == 1:
            t_data.append([Paragraph(" ", s_cell)] * 4)

        cw = doc.width
        # Fila de encabezados más alta (texto de 2 líneas); filas de datos normales.
        row_heights = [0.95 * cm] + [0.55 * cm] * (len(t_data) - 1)
        dep_tbl = Table(t_data, colWidths=[cw * 0.36, cw * 0.22, cw * 0.24, cw * 0.18], rowHeights=row_heights)
        dep_tbl.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",          (0, 0), (-1, -1), 0.5, BORDE),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ]))
        story.append(dep_tbl)
        story.append(Spacer(1, 0.15 * cm))

        # Lista de tipos de dependientes
        story.append(Paragraph("<b>TIPO DE DEPENDIENTES:</b>", s_cuerpo))
        for txt in [
            "<b>A.</b> Hijo(s) de hasta 18 años que dependen económicamente de mí.",
            "<b>B.</b> Hijo(s) entre 18 y 23 años con educación formal a mi cargo, certificada por el ICFES o autoridad competente.",
            "<b>C.</b> Hijo(s) mayor(es) de 23 años con dependencia por factores físicos o psicológicos certificados por Medicina Legal.",
            "<b>D.</b> Cónyuge o compañero permanente con dependencia por ausencia de ingresos (menos de 260 UVT/año) o factores físicos/psicológicos, certificados.",
            "<b>E.</b> Padres y/o hermanos con dependencia por ausencia de ingresos (menos de 260 UVT/año) o factores físicos/psicológicos, certificados.",
        ]:
            story.append(Paragraph(txt, s_bullet))

        story.append(Spacer(1, 0.15 * cm))

        # Párrafo 4
        story.append(Paragraph(
            "Que de conformidad con lo ordenado en el inciso 2° del parágrafo 4° del Decreto 099 del 25 de enero "
            "del 2013, nadie más solicitará la deducción de la base de la retención en la fuente por el mismo dependiente.",
            s_cuerpo,
        ))

        # Párrafo 5 – expedición
        story.append(Paragraph(
            f"La presente certificación se expide en la ciudad de Bogotá, en el mes de <b>{mes_exp.upper()}</b> "
            f"del año <b>{año_exp}</b>, para efectos de la depuración de la base del cálculo de la retención "
            f"establecida en los artículos 383 y 387 del Estatuto Tributario.",
            s_cuerpo,
        ))

        story.append(Spacer(1, 0.25 * cm))

        # ── Firma: CENTRADA, imagen sobre la línea gris — igual que formato 6 ──
        from app.services.firma_service import FirmaService
        firma_bytes = FirmaService().obtener_imagen(usuario_id)

        s_firma_nombre = ParagraphStyle(
            "dep4_fn", parent=estilos["Normal"],
            fontSize=9, fontName="Helvetica-Bold", alignment=TA_CENTER,
            textColor=NEGRO, leading=12,
        )
        s_firma_sub = ParagraphStyle(
            "dep4_fs", parent=estilos["Normal"],
            fontSize=8.5, alignment=TA_CENTER, leading=11, textColor=NEGRO,
        )

        if firma_bytes:
            firma_img = Image(io.BytesIO(firma_bytes), width=5.2 * cm, height=2.6 * cm, kind="proportional")
            filas_firma = [
                [firma_img],
                [Paragraph(f"C.C.: <b>{cedula}</b> de <b>{lugar_exp.upper()}</b>", s_firma_sub)],
                [Paragraph(f"Fecha: Bogotá, <b>{fecha_fmt}</b>", s_firma_sub)],
            ]
        else:
            filas_firma = [
                [""],
                [Paragraph(f"C.C.: <b>{cedula}</b> de <b>{lugar_exp.upper()}</b>", s_firma_sub)],
                [Paragraph(f"Fecha: Bogotá, <b>{fecha_fmt}</b>", s_firma_sub)],
            ]

        firma_tabla = Table(filas_firma, colWidths=[8.5 * cm], hAlign="CENTER")
        firma_tabla.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
            ("FONTNAME",      (0, 0), (0, 0),   "Helvetica"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            # Línea negra debajo de la imagen de firma
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, NEGRO),
            ("TOPPADDING",    (0, 0), (-1, 0),  0),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  0),
            ("TOPPADDING",    (0, 1), (-1, 1),  3),
        ]))
        story.append(firma_tabla)

        # NOTA: el código de verificación (hash_verificacion) se sigue
        # generando y almacenando en la certificación, pero por solicitud
        # NO se muestra en este formato plano. No se renderiza aquí.

        doc.build(story)
        buf.seek(0)
        return buf.getvalue()

    def generar_pdf_cuenta_cobro(self, certificacion: Dict) -> bytes:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import black
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, Image,
        )

        NEGRO = black

        # ── Datos del usuario ──
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_id = str(certificacion.get("usuario_id", ""))
        usuario_data: dict = {}
        if usuario_id:
            try:
                usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
            except Exception:
                pass

        nombre = usuario_data.get("nombre_completo", "")
        tipo_doc = usuario_data.get("tipo_documento", "C.C.")
        cedula = usuario_data.get("numero_documento") or "—"
        lugar_exp = usuario_data.get("lugar_expedicion_documento") or "—"

        info_laboral = usuario_data.get("informacion_laboral") or {}
        bancaria = info_laboral.get("bancaria") or {}
        banco_clave = bancaria.get("banco")
        
        from app.services.opciones_service import OpcionesService
        banco_nombre = (
            OpcionesService().obtener_etiqueta_por_clave("banco", banco_clave)
            if banco_clave else "—"
        )
        cuenta_bancaria = bancaria.get("numero_cuenta") or "—"

        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        año_cert = certificacion.get("año")
        mes_cert = certificacion.get("mes", 1)
        contrato_vig = self._contrato_para_periodo(contratos, año_cert, mes_cert)
        no_contrato = contrato_vig.get("numero", "—")
        valor_mensual = contrato_vig.get("valor_mensual", 0)
        objeto_contrato = contrato_vig.get("objeto") or ""
        
        fecha_ini_raw = contrato_vig.get("fecha_inicio")
        fecha_fin_raw = contrato_vig.get("fecha_fin")
        valor_total = contrato_vig.get("valor", 0)
        
        # RP y Fecha RP
        rp_compromiso = contrato_vig.get("rp_compromiso_presupuestal") or "—"
        fecha_rp_raw = contrato_vig.get("fecha_recurso_presupuestal")
        if fecha_rp_raw:
            fecha_rp_str = f"{fecha_rp_raw.day} de {MESES_ES[fecha_rp_raw.month - 1].lower()} de {fecha_rp_raw.year}"
        else:
            fecha_rp_str = "—"

        # Periodo del certificado
        cert_month = certificacion.get("mes", 1)
        cert_year = certificacion.get("año", 2026)
        mes_nombre_upper = MESES_ES[cert_month - 1].upper()

        # Calcular número de cuenta de cobro
        if fecha_ini_raw:
            mes_num = (cert_year - fecha_ini_raw.year) * 12 + (cert_month - fecha_ini_raw.month) + 1
        else:
            mes_num = 1

        # Fecha actual o de firma para el encabezado "Bogotá D.C, {fecha de expedición}"
        fecha_corte = certificacion.get("fecha_corte")
        if fecha_corte:
            dt = utc_a_bogota(fecha_corte)
        else:
            dt = datetime.now(ZONA_BOGOTA)
        
        dias_expedicion = str(dt.day)
        mes_expedicion_capitalizado = MESES_ES[dt.month - 1]
        año_expedicion = str(dt.year)
        
        fecha_expedicion_completa = f"{dias_expedicion} {mes_expedicion_capitalizado} de {año_expedicion}"

        # ── Utilidades de conversión ──
        def _numero_a_letras(numero: int) -> str:
            unidades = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
            decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
            especiales = {
                11: "ONCE", 12: "DOCE", 13: "TRECE", 14: "CATORCE", 15: "QUINCE",
                16: "DIECISEIS", 17: "DIECISIETE", 18: "DIECIOCHO", 19: "DIECINUEVE",
                21: "VEINTIUNO", 22: "VEINTIDOS", 23: "VEINTITRES", 24: "VEINTICUATRO",
                25: "VEINTICINCO", 26: "VEINTISEIS", 27: "VEINTISIETE", 28: "VEINTIOCHO", 29: "VEINTINUEVE"
            }
            centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

            if numero == 0:
                return "CERO"

            def _convertir(n):
                if n < 10:
                    return unidades[n]
                elif n in especiales:
                    return especiales[n]
                elif n < 30:
                    if n == 20: return "VEINTE"
                    return especiales.get(n, "")
                elif n < 100:
                    u = n % 10
                    d = n // 10
                    if u > 0:
                        return f"{decenas[d]} Y {unidades[u]}"
                    return decenas[d]
                elif n < 1000:
                    if n == 100:
                        return "CIEN"
                    d_u = n % 100
                    c = n // 100
                    if d_u > 0:
                        return f"{centenas[c]} {_convertir(d_u)}"
                    return centenas[c]
                elif n < 1000000:
                    m = n // 1000
                    resto = n % 1000
                    m_str = ""
                    if m == 1:
                        m_str = "MIL"
                    else:
                        m_str = f"{_convertir(m)} MIL"
                    if resto > 0:
                        return f"{m_str} {_convertir(resto)}"
                    return m_str
                elif n < 1000000000:
                    millon = n // 1000000
                    resto = n % 1000000
                    mill_str = ""
                    if millon == 1:
                        mill_str = "UN MILLON"
                    else:
                        mill_words = _convertir(millon)
                        if mill_words.endswith("UNO"):
                            mill_words = mill_words[:-3] + "UN"
                        elif mill_words == "UNO":
                            mill_words = "UN"
                        mill_str = f"{mill_words} MILLONES"
                    if resto > 0:
                        return f"{mill_str} {_convertir(resto)}"
                    return mill_str
                return str(n)

            return _convertir(numero).strip()

        def _formatear_pesos(valor: float) -> str:
            return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # ── Documento — márgenes ──
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=2.3 * cm,
            rightMargin=2.3 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        estilos = getSampleStyleSheet()

        s_cuerpo = ParagraphStyle(
            "cc_cuerpo", parent=estilos["Normal"],
            fontSize=11.5, alignment=TA_JUSTIFY, leading=16, spaceAfter=10,
            textColor=NEGRO, fontName="Helvetica",
        )
        s_cuerpo_left = ParagraphStyle(
            "cc_cuerpo_l", parent=estilos["Normal"],
            fontSize=11.5, alignment=TA_LEFT, leading=16, spaceAfter=2,
            textColor=NEGRO, fontName="Helvetica",
        )
        s_cuerpo_center = ParagraphStyle(
            "cc_cuerpo_c", parent=estilos["Normal"],
            fontSize=11.5, alignment=TA_CENTER, leading=16, spaceAfter=6,
            textColor=NEGRO, fontName="Helvetica",
        )
        s_cuerpo_bold_center = ParagraphStyle(
            "cc_cuerpo_bc", parent=estilos["Normal"],
            fontSize=12.5, alignment=TA_CENTER, leading=17, spaceAfter=6,
            fontName="Helvetica-Bold", textColor=NEGRO,
        )

        story = []

        # Encabezado fecha
        story.append(Paragraph(f"Bogotá D.C, {fecha_expedicion_completa}", s_cuerpo_left))
        story.append(Spacer(1, 1.2 * cm))

        # Título Cuenta de Cobro
        story.append(Paragraph(f"<b>CUENTA DE COBRO No. {mes_num}</b>", s_cuerpo_bold_center))
        story.append(Spacer(1, 1.0 * cm))

        # Deudor
        story.append(Paragraph("EL INSTITUTO NACIONAL DE VIAS<br/>(INVIAS)<br/>NIT. 800.215.807-2", s_cuerpo_center))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("D E B E A:", s_cuerpo_center))
        story.append(Spacer(1, 0.5 * cm))

        # Nombre del usuario y documento
        story.append(Paragraph(f"<b>{nombre.upper()}</b>", s_cuerpo_bold_center))
        story.append(Paragraph(f"{tipo_doc}. {cedula} de {lugar_exp}.", s_cuerpo_center))
        story.append(Spacer(1, 1.0 * cm))

        # Párrafo valor y objeto
        es_primer_mes = False
        if fecha_ini_raw and cert_month == fecha_ini_raw.month and cert_year == fecha_ini_raw.year:
            es_primer_mes = True

        es_ultimo_mes = False
        if fecha_fin_raw and cert_month == fecha_fin_raw.month and cert_year == fecha_fin_raw.year:
            es_ultimo_mes = True

        if es_primer_mes and es_ultimo_mes:
            valor_pago = valor_total if valor_total > 0 else (contrato_vig.get("valor_primer_pago") or valor_mensual)
            dia_ini = fecha_ini_raw.day
            dia_fin = fecha_fin_raw.day
            mes_ini = MESES_ES[fecha_ini_raw.month - 1].lower()
            periodo_html = f"del <b>{dia_ini} al {dia_fin} de {mes_ini} del {cert_year}</b>"
        elif es_primer_mes:
            valor_pago = contrato_vig.get("valor_primer_pago")
            if valor_pago is None or valor_pago == 0:
                valor_pago = valor_mensual
            
            dia_ini = fecha_ini_raw.day
            mes_ini = MESES_ES[fecha_ini_raw.month - 1].lower()
            mes_nombre_lower = MESES_ES[cert_month - 1].lower()
            periodo_html = f"del <b>{dia_ini} de {mes_ini} al 30 de {mes_nombre_lower} del {cert_year}</b>"
        elif es_ultimo_mes:
            if contrato_vig.get("personalizar_ultimacuenta"):
                valor_pago = contrato_vig.get("valor_personalizar_ultimacuenta") or 0
            elif fecha_ini_raw and valor_total > 0:
                total_meses_contrato = (fecha_fin_raw.year - fecha_ini_raw.year) * 12 + (fecha_fin_raw.month - fecha_ini_raw.month)
                meses_completos = max(0, total_meses_contrato - 1)
                val_primer = contrato_vig.get("valor_primer_pago")
                if val_primer is None or val_primer == 0:
                    val_primer = valor_mensual
                valor_pago = valor_total - val_primer - (meses_completos * valor_mensual)
                valor_pago = max(0, valor_pago)
            else:
                valor_pago = valor_mensual
            
            dia_fin = fecha_fin_raw.day
            mes_fin = MESES_ES[fecha_fin_raw.month - 1].lower()
            periodo_html = f"del <b>1 de {mes_fin} al {dia_fin} de {mes_fin} del {cert_year}</b>"
        else:
            valor_pago = valor_mensual
            periodo_html = f"de <b>{mes_nombre_upper}</b> del <b>{cert_year}</b>"

        val_letras = _numero_a_letras(int(valor_pago))
        val_num_fmt = _formatear_pesos(valor_pago)
        objeto_sostenida = objeto_contrato.upper()
        
        p_valor = (
            f"La suma de <b>{val_letras} PESOS MONEDA CORRIENTE </b><b>(${val_num_fmt})</b>  "
            f"por concepto del Contrato de Prestación de Servicios No. <b>{no_contrato}</b> de <b>{fecha_ini_raw.year if fecha_ini_raw else dt.year}</b> "
            f"cuyo objeto es: “<b>{objeto_sostenida}</b>”, en el periodo correspondiente {periodo_html}."
        )
        story.append(Paragraph(p_valor, s_cuerpo))

        # Párrafo presupuesto
        p_presupuesto = (
            f"El presente valor se tomará del compromiso presupuestal No. <b>{rp_compromiso}</b> "
            f"del <b>{fecha_rp_str}</b>."
        )
        story.append(Paragraph(p_presupuesto, s_cuerpo))

        # Párrafo cuenta bancaria
        tipo_cuenta_clave = bancaria.get("tipo_cuenta")
        from app.core.catalogos import TIPOS_CUENTA_BANCARIA
        if tipo_cuenta_clave == "cts":
            tipo_cuenta_lbl = "cuenta de trámite simplificado (CTS/ Depósitos electrónicos)"
        elif tipo_cuenta_clave:
            tipo_cuenta_lbl = TIPOS_CUENTA_BANCARIA.get(tipo_cuenta_clave, "Cuenta de ahorros").lower()
        else:
            tipo_cuenta_lbl = "cuenta de ahorros"

        p_banco = (
            f"Autorizo consignar en la {tipo_cuenta_lbl} No. <b>{cuenta_bancaria}</b> "
            f"del <b>{banco_nombre}</b>."
        )
        story.append(Paragraph(p_banco, s_cuerpo))
        story.append(Spacer(1, 1.2 * cm))

        # Firma
        from app.services.firma_service import FirmaService
        firma_bytes = FirmaService().obtener_imagen(usuario_id)

        s_firma_nombre = ParagraphStyle(
            "cc_fn", parent=estilos["Normal"],
            fontSize=11, fontName="Helvetica-Bold", alignment=TA_CENTER,
            textColor=NEGRO, leading=15,
        )
        s_firma_sub = ParagraphStyle(
            "cc_fs", parent=estilos["Normal"],
            fontSize=10.5, alignment=TA_CENTER, leading=14.5, textColor=NEGRO,
            fontName="Helvetica",
        )

        if firma_bytes:
            firma_img = Image(io.BytesIO(firma_bytes), width=5.2 * cm, height=2.6 * cm, kind="proportional")
            filas_firma = [
                [firma_img],
                [Paragraph(nombre.upper(), s_firma_nombre)],
                [Paragraph(f"{tipo_doc}. {cedula} de {lugar_exp.upper()}", s_firma_sub)],
                [Paragraph("Contratista", s_firma_sub)],
            ]
        else:
            filas_firma = [
                [""],
                [Paragraph(nombre.upper(), s_firma_nombre)],
                [Paragraph(f"{tipo_doc}. {cedula} de {lugar_exp.upper()}", s_firma_sub)],
                [Paragraph("Contratista", s_firma_sub)],
            ]

        # Tabla de firma centrada con un ancho reducido para que la línea no sea tan larga
        firma_tabla = Table(filas_firma, colWidths=[8.5 * cm], hAlign="CENTER")
        firma_tabla.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, NEGRO),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        story.append(firma_tabla)

        doc.build(story)
        buf.seek(0)
        return buf.getvalue()

    def generar_pdf_retencion_fuente_primera(self, certificacion: Dict) -> bytes:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor, black
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, Image,
        )

        NEGRO = black
        BORDE = HexColor("#666666")

        # ── Datos del usuario ──
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_id = str(certificacion.get("usuario_id", ""))
        usuario_data: dict = {}
        if usuario_id:
            try:
                usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
            except Exception:
                pass

        nombre = usuario_data.get("nombre_completo", "")
        tipo_doc = usuario_data.get("tipo_documento", "C.C.")
        cedula = usuario_data.get("numero_documento") or "—"
        lugar_exp = usuario_data.get("lugar_expedicion_documento") or "—"

        info_laboral = usuario_data.get("informacion_laboral") or {}
        tributaria = info_laboral.get("tributaria") or {}
        declarante_renta = tributaria.get("declarante_renta", False)

        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        año_cert = certificacion.get("año")
        mes_cert = certificacion.get("mes", 1)
        contrato_vig = self._contrato_para_periodo(contratos, año_cert, mes_cert)
        no_contrato = contrato_vig.get("numero", "—")
        valor_contrato = contrato_vig.get("valor", 0)
        valor_mensual = contrato_vig.get("valor_mensual", 0)
        
        fecha_ini_raw = contrato_vig.get("fecha_inicio")
        fecha_fin_raw = contrato_vig.get("fecha_fin")
        
        fecha_ini_str = fecha_ini_raw.strftime("%d/%m/%Y") if fecha_ini_raw else "—"
        fecha_fin_str = fecha_fin_raw.strftime("%d/%m/%Y") if fecha_fin_raw else "—"

        if fecha_ini_raw:
            dia_ini = str(fecha_ini_raw.day)
            mes_ini = MESES_ES[fecha_ini_raw.month - 1].lower()
            año_ini = str(fecha_ini_raw.year)
        else:
            dia_ini = "—"
            mes_ini = "—"
            año_ini = "—"

        # Fechas de expedición del documento (mes/año parameter)
        mes_num = certificacion.get("mes", 1)
        nombre_mes_exp = MESES_ES[mes_num - 1]
        año_exp = str(certificacion.get("año", ""))

        # Fecha actual o de firma para el encabezado "Bogotá D.C., {fecha de expedición del formato}"
        fecha_corte = certificacion.get("fecha_corte")
        if fecha_corte:
            dt = utc_a_bogota(fecha_corte)
        else:
            dt = datetime.now(ZONA_BOGOTA)
        
        fecha_expedicion_completa = f"{dt.day} {MESES_ES[dt.month - 1]} de {dt.year}"

        # ── Utilidades de conversión ──
        def _numero_a_letras(numero: int) -> str:
            unidades = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
            decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
            especiales = {
                11: "ONCE", 12: "DOCE", 13: "TRECE", 14: "CATORCE", 15: "QUINCE",
                16: "DIECISEIS", 17: "DIECISIETE", 18: "DIECIOCHO", 19: "DIECINUEVE",
                21: "VEINTIUNO", 22: "VEINTIDOS", 23: "VEINTITRES", 24: "VEINTICUATRO",
                25: "VEINTICINCO", 26: "VEINTISEIS", 27: "VEINTISIETE", 28: "VEINTIOCHO", 29: "VEINTINUEVE"
            }
            centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

            if numero == 0:
                return "CERO"

            def _convertir(n):
                if n < 10:
                    return unidades[n]
                elif n in especiales:
                    return especiales[n]
                elif n < 30:
                    if n == 20: return "VEINTE"
                    return especiales.get(n, "")
                elif n < 100:
                    u = n % 10
                    d = n // 10
                    if u > 0:
                        return f"{decenas[d]} Y {unidades[u]}"
                    return decenas[d]
                elif n < 1000:
                    if n == 100:
                        return "CIEN"
                    d_u = n % 100
                    c = n // 100
                    if d_u > 0:
                        return f"{centenas[c]} {_convertir(d_u)}"
                    return centenas[c]
                elif n < 1000000:
                    m = n // 1000
                    resto = n % 1000
                    m_str = ""
                    if m == 1:
                        m_str = "MIL"
                    else:
                        m_str = f"{_convertir(m)} MIL"
                    if resto > 0:
                        return f"{m_str} {_convertir(resto)}"
                    return m_str
                elif n < 1000000000:
                    millon = n // 1000000
                    resto = n % 1000000
                    mill_str = ""
                    if millon == 1:
                        mill_str = "UN MILLON"
                    else:
                        mill_words = _convertir(millon)
                        if mill_words.endswith("UNO"):
                            mill_words = mill_words[:-3] + "UN"
                        elif mill_words == "UNO":
                            mill_words = "UN"
                        mill_str = f"{mill_words} MILLONES"
                    if resto > 0:
                        return f"{mill_str} {_convertir(resto)}"
                    return mill_str
                return str(n)

            return _convertir(numero).strip()

        def _formatear_pesos(valor: float) -> str:
            return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # ── Documento — márgenes ──
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=2.3 * cm,
            rightMargin=2.3 * cm,
            topMargin=1.2 * cm,
            bottomMargin=1.2 * cm,
        )

        estilos = getSampleStyleSheet()

        s_cuerpo = ParagraphStyle(
            "ret_cuerpo_prim", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_JUSTIFY, leading=12.5, spaceAfter=4,
            textColor=NEGRO, fontName="Helvetica",
        )
        s_cuerpo_left = ParagraphStyle(
            "ret_cuerpo_l_prim", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_LEFT, leading=12.5, spaceAfter=1,
            textColor=NEGRO, fontName="Helvetica",
        )
        s_cuerpo_bold = ParagraphStyle(
            "ret_cuerpo_b_prim", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_LEFT, leading=12.5, spaceAfter=1,
            fontName="Helvetica-Bold", textColor=NEGRO,
        )
        s_cell = ParagraphStyle(
            "ret_cell_prim", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_LEFT, leading=12, textColor=NEGRO,
            fontName="Helvetica",
        )

        story = []

        # Encabezado fecha
        story.append(Paragraph(f"Bogotá D.C., {fecha_expedicion_completa}", s_cuerpo_left))
        story.append(Spacer(1, 0.7 * cm))

        # Obtener el nombre del responsable de financiera
        from app.services.parametros_service import ParametrosService
        try:
            nombre_responsable = ParametrosService().obtener("nombre_financiera_retefuente")
        except Exception:
            nombre_responsable = "sin nombre_financiera_retefuente"

        if not nombre_responsable or not nombre_responsable.strip():
            nombre_responsable = "sin nombre_financiera_retefuente"

        # Destinatario
        story.append(Paragraph("Doctor", s_cuerpo_left))
        story.append(Paragraph(nombre_responsable, s_cuerpo_bold))
        story.append(Paragraph("Subdirección Financiera - Grupo Cuentas Por Pagar", s_cuerpo_left))
        story.append(Paragraph("INSTITUTO NACIONAL DE VÍAS", s_cuerpo_bold))
        story.append(Paragraph("Bogotá D.C", s_cuerpo_left))
        story.append(Spacer(1, 0.7 * cm))

        # Asunto
        story.append(Paragraph(f"<b>ASUNTO:</b> Disminución Base Retención en la Fuente Contrato No. {no_contrato}", s_cuerpo_bold))
        story.append(Spacer(1, 0.7 * cm))

        # Saludo
        story.append(Paragraph("Respetado Señor Jairo,", s_cuerpo_left))
        story.append(Spacer(1, 0.15 * cm))

        # Párrafo legal
        p_legal = (
            f"<b>{nombre.upper()}</b> identificado como aparece al pie de la firma, solicito realizar la "
            f"retención en la fuente con fundamento en el Parágrafo 2 del Artículo 17 de la Ley 1819 de 2016, "
            f"el cual estableció para el artículo 383 del Estatuto Tributario lo siguiente: <i>“Parágrafo 2. La "
            f"retención en la fuente establecida en el presente artículo será aplicable a los pagos o abonos "
            f"en cuenta por concepto de ingresos por honorarios y por compensación por servicios personales "
            f"obtenidos por las personas que informen que no han contratado o vinculado dos (2) o más "
            f"trabajadores asociados a la actividad”</i>."
        )
        story.append(Paragraph(p_legal, s_cuerpo))
        story.append(Paragraph("Que los datos del contrato son:", s_cuerpo_left))
        story.append(Spacer(1, 0.1 * cm))

        # Tabla 1: Datos contrato
        t1_data = [
            [Paragraph("a.", s_cell), Paragraph("Contrato:", s_cell), Paragraph(no_contrato, s_cell)],
            [Paragraph("b.", s_cell), Paragraph("Razón social:", s_cell), Paragraph("Instituto Nacional de Vías-INVIAS", s_cell)],
            [Paragraph("c.", s_cell), Paragraph("NIT Entidad:", s_cell), Paragraph("800.215.807-2", s_cell)],
            [Paragraph("d.", s_cell), Paragraph("Valor del contrato:", s_cell), Paragraph(f"$ {_formatear_pesos(valor_contrato)[:-3]}", s_cell)],
            [Paragraph("e.", s_cell), Paragraph("Fecha de inicio:", s_cell), Paragraph(fecha_ini_str, s_cell)],
            [Paragraph("f.", s_cell), Paragraph("Fecha de terminación:", s_cell), Paragraph(fecha_fin_str, s_cell)],
        ]
        t1 = Table(t1_data, colWidths=[0.6 * cm, 3.8 * cm, 6.5 * cm], hAlign='CENTER')
        t1.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
            ("TOPPADDING", (0, 0), (-1, -1), 0.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(t1)
        story.append(Spacer(1, 0.2 * cm))

        # Párrafo Certifico Régimen
        regimen_db = tributaria.get("regimen") or "NULL"
        regimen_str = regimen_db.replace("_", " ").upper()
        rut_str = tributaria.get("rut") or "—"
        renta_str = "SI RENTA" if declarante_renta else "NO RENTA"

        p_regimen = (
            f"De igual manera, bajo la gravedad de juramento certifico que: PERTENEZCO AL RÉGIMEN <b>{regimen_str}</b>, "
            f"CON RUT No. <b>{rut_str}</b> y <b>{renta_str}</b>"
        )
        story.append(Paragraph(p_regimen, s_cuerpo))

        # Nuevo Párrafo Seguridad Social para Primera Cuenta
        p_seg_social_primera = (
            f"<i>Teniendo en cuenta que el presente contrato de prestación de servicios inició el día {dia_ini} de {mes_ini} de {año_ini}, "
            f"el pago de las cotizaciones al Sistema de Seguridad Social integral se efectuará mes vencido, de conformidad con lo establecido en el Artículo 1 del Decreto 1273 de 2018.</i>"
        )
        story.append(Paragraph(p_seg_social_primera, s_cuerpo))
        story.append(Spacer(1, 0.3 * cm))

        # Honorarios
        valor_base = contrato_vig.get("valor_primer_pago")
        if valor_base is None or valor_base == 0:
            valor_base = valor_mensual
        val_letras = _numero_a_letras(int(valor_base))
        val_num_fmt = _formatear_pesos(valor_base)
        nombre_mes_exp_lc = nombre_mes_exp.lower()
        if fecha_ini_raw:
            periodo_texto = f"el {dia_ini} de {mes_ini} al 30 de {nombre_mes_exp_lc} del {año_ini}"
        else:
            periodo_texto = f"el — de — al 30 de {nombre_mes_exp_lc} del —"
            
        p_honorarios = (
            f"Que el valor a cobrar por concepto de honorarios corresponden al periodo del <b><i>{periodo_texto}</i></b> "
            f"y ascienden a la suma de: <b><i>{val_letras} ($ {val_num_fmt}) M/Cte.</i></b>"
        )
        story.append(Paragraph(p_honorarios, s_cuerpo))
        story.append(Spacer(1, 0.3 * cm))

        # Despedida
        story.append(Paragraph("Atentamente,", s_cuerpo_left))
        story.append(Spacer(1, 0.1 * cm))

        # Firma
        from app.services.firma_service import FirmaService
        firma_bytes = FirmaService().obtener_imagen(usuario_id)

        s_firma_nombre = ParagraphStyle(
            "ret_fn_prim", parent=estilos["Normal"],
            fontSize=9.5, fontName="Helvetica-Bold", alignment=TA_CENTER,
            textColor=NEGRO, leading=13,
        )
        s_firma_sub = ParagraphStyle(
            "ret_fs_prim", parent=estilos["Normal"],
            fontSize=9, alignment=TA_CENTER, leading=12, textColor=NEGRO,
            fontName="Helvetica",
        )

        if firma_bytes:
            firma_img = Image(io.BytesIO(firma_bytes), width=5.2 * cm, height=2.6 * cm, kind="proportional")
            filas_firma = [
                [firma_img],
                [Paragraph(nombre, s_firma_nombre)],
                [Paragraph(f"{tipo_doc}. {cedula} de {lugar_exp}", s_firma_sub)],
            ]
        else:
            filas_firma = [
                [""],
                [Paragraph(nombre, s_firma_nombre)],
                [Paragraph(f"{tipo_doc}. {cedula} de {lugar_exp}", s_firma_sub)],
            ]

        firma_tabla = Table(filas_firma, colWidths=[8.5 * cm], hAlign="CENTER")
        firma_tabla.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, NEGRO),
            ("TOPPADDING",    (0, 0), (-1, 0),  0),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  0),
            ("TOPPADDING",    (0, 1), (-1, 1),  3),
        ]))
        story.append(firma_tabla)

        # NOTA: el código de verificación (hash_verificacion) se sigue
        # generando y almacenando en la certificación, pero por solicitud
        # NO se muestra en este formato plano. No se renderiza aquí.

        doc.build(story)
        buf.seek(0)
        return buf.getvalue()

    def generar_pdf_retencion_fuente_segunda(self, certificacion: Dict) -> bytes:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor, black
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, Image,
        )

        NEGRO = black
        BORDE = HexColor("#666666")

        # ── Datos del usuario ──
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_id = str(certificacion.get("usuario_id", ""))
        usuario_data: dict = {}
        if usuario_id:
            try:
                usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
            except Exception:
                pass

        nombre = usuario_data.get("nombre_completo", "")
        tipo_doc = usuario_data.get("tipo_documento", "C.C.")
        cedula = usuario_data.get("numero_documento") or "—"
        lugar_exp = usuario_data.get("lugar_expedicion_documento") or "—"

        info_laboral = usuario_data.get("informacion_laboral") or {}
        tributaria = info_laboral.get("tributaria") or {}
        declarante_renta = tributaria.get("declarante_renta", False)
        seguridad_social = info_laboral.get("seguridad_social") or {}

        # Contrato vigente
        contratos = usuario_data.get("contratos") or []
        año_cert = certificacion.get("año")
        mes_cert = certificacion.get("mes", 1)
        contrato_vig = self._contrato_para_periodo(contratos, año_cert, mes_cert)
        no_contrato = contrato_vig.get("numero", "—")
        valor_contrato = contrato_vig.get("valor", 0)
        valor_mensual = contrato_vig.get("valor_mensual", 0)
        
        fecha_ini_raw = contrato_vig.get("fecha_inicio")
        fecha_fin_raw = contrato_vig.get("fecha_fin")
        
        fecha_ini_str = fecha_ini_raw.strftime("%d/%m/%Y") if fecha_ini_raw else "—"
        fecha_fin_str = fecha_fin_raw.strftime("%d/%m/%Y") if fecha_fin_raw else "—"

        # Fechas de expedición del documento (mes/año parameter)
        mes_num = certificacion.get("mes", 1)
        año_num = certificacion.get("año", 2026)
        nombre_mes_exp = MESES_ES[mes_num - 1]
        año_exp = str(año_num)
        
        planilla_mes_vencido = bool(info_laboral.get("planilla_mes_vencido"))
        if planilla_mes_vencido:
            if mes_num == 1:
                mes_num_periodo = 12
                año_num_periodo = año_num - 1
            else:
                mes_num_periodo = mes_num - 1
                año_num_periodo = año_num
        else:
            mes_num_periodo = mes_num
            año_num_periodo = año_num

        nombre_mes_planilla = MESES_ES[mes_num_periodo - 1]
        año_planilla = str(año_num_periodo)

        # Fecha actual o de firma para el encabezado "Bogotá D.C., {fecha de expedición del formato}"
        fecha_corte = certificacion.get("fecha_corte")
        if fecha_corte:
            dt = utc_a_bogota(fecha_corte)
        else:
            dt = datetime.now(ZONA_BOGOTA)
        
        fecha_expedicion_completa = f"{dt.day} {MESES_ES[dt.month - 1]} de {dt.year}"

        # ── Utilidades de conversión ──
        def _numero_a_letras(numero: int) -> str:
            unidades = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
            decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
            especiales = {
                11: "ONCE", 12: "DOCE", 13: "TRECE", 14: "CATORCE", 15: "QUINCE",
                16: "DIECISEIS", 17: "DIECISIETE", 18: "DIECIOCHO", 19: "DIECINUEVE",
                21: "VEINTIUNO", 22: "VEINTIDOS", 23: "VEINTITRES", 24: "VEINTICUATRO",
                25: "VEINTICINCO", 26: "VEINTISEIS", 27: "VEINTISIETE", 28: "VEINTIOCHO", 29: "VEINTINUEVE"
            }
            centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

            if numero == 0:
                return "CERO"

            def _convertir(n):
                if n < 10:
                    return unidades[n]
                elif n in especiales:
                    return especiales[n]
                elif n < 30:
                    if n == 20: return "VEINTE"
                    return especiales.get(n, "")
                elif n < 100:
                    u = n % 10
                    d = n // 10
                    if u > 0:
                        return f"{decenas[d]} Y {unidades[u]}"
                    return decenas[d]
                elif n < 1000:
                    if n == 100:
                        return "CIEN"
                    d_u = n % 100
                    c = n // 100
                    if d_u > 0:
                        return f"{centenas[c]} {_convertir(d_u)}"
                    return centenas[c]
                elif n < 1000000:
                    m = n // 1000
                    resto = n % 1000
                    m_str = ""
                    if m == 1:
                        m_str = "MIL"
                    else:
                        m_str = f"{_convertir(m)} MIL"
                    if resto > 0:
                        return f"{m_str} {_convertir(resto)}"
                    return m_str
                elif n < 1000000000:
                    millon = n // 1000000
                    resto = n % 1000000
                    mill_str = ""
                    if millon == 1:
                        mill_str = "UN MILLON"
                    else:
                        mill_words = _convertir(millon)
                        if mill_words.endswith("UNO"):
                            mill_words = mill_words[:-3] + "UN"
                        elif mill_words == "UNO":
                            mill_words = "UN"
                        mill_str = f"{mill_words} MILLONES"
                    if resto > 0:
                        return f"{mill_str} {_convertir(resto)}"
                    return mill_str
                return str(n)

            return _convertir(numero).strip()

        def _formatear_pesos(valor: float) -> str:
            return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # ── Documento — márgenes ──
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=2.3 * cm,
            rightMargin=2.3 * cm,
            topMargin=1.2 * cm,
            bottomMargin=1.2 * cm,
        )

        estilos = getSampleStyleSheet()

        s_cuerpo = ParagraphStyle(
            "ret_cuerpo", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_JUSTIFY, leading=12.5, spaceAfter=4,
            textColor=NEGRO, fontName="Helvetica",
        )
        s_cuerpo_left = ParagraphStyle(
            "ret_cuerpo_l", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_LEFT, leading=12.5, spaceAfter=1,
            textColor=NEGRO, fontName="Helvetica",
        )
        s_cuerpo_bold = ParagraphStyle(
            "ret_cuerpo_b", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_LEFT, leading=12.5, spaceAfter=1,
            fontName="Helvetica-Bold", textColor=NEGRO,
        )
        s_cell = ParagraphStyle(
            "ret_cell", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_LEFT, leading=12, textColor=NEGRO,
            fontName="Helvetica",
        )
        s_cell_center = ParagraphStyle(
            "ret_cell_c", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_CENTER, leading=12, textColor=NEGRO,
            fontName="Helvetica",
        )
        s_cell_hdr = ParagraphStyle(
            "ret_cell_h", parent=estilos["Normal"],
            fontSize=9.5, fontName="Helvetica-Bold", alignment=TA_CENTER,
            leading=12, textColor=NEGRO,
        )

        story = []

        # Encabezado fecha
        story.append(Paragraph(f"Bogotá D.C., {fecha_expedicion_completa}", s_cuerpo_left))
        story.append(Spacer(1, 0.7 * cm))

        # Obtener el nombre del responsable de financiera
        from app.services.parametros_service import ParametrosService
        try:
            nombre_responsable = ParametrosService().obtener("nombre_financiera_retefuente")
        except Exception:
            nombre_responsable = "sin nombre_financiera_retefuente"

        if not nombre_responsable or not nombre_responsable.strip():
            nombre_responsable = "sin nombre_financiera_retefuente"

        # Destinatario
        story.append(Paragraph("Doctor", s_cuerpo_left))
        story.append(Paragraph(nombre_responsable, s_cuerpo_bold))
        story.append(Paragraph("Subdirección Financiera - Grupo Cuentas Por Pagar", s_cuerpo_left))
        story.append(Paragraph("INSTITUTO NACIONAL DE VÍAS", s_cuerpo_bold))
        story.append(Paragraph("Bogotá D.C", s_cuerpo_left))
        story.append(Spacer(1, 0.7 * cm))

        # Asunto
        story.append(Paragraph(f"<b>ASUNTO:</b> Disminución Base Retención en la Fuente Contrato No. {no_contrato}", s_cuerpo_bold))
        story.append(Spacer(1, 0.7 * cm))

        # Saludo
        story.append(Paragraph("Respetado Señor Jairo,", s_cuerpo_left))
        story.append(Spacer(1, 0.15 * cm))

        # Párrafo legal
        p_legal = (
            f"<b>{nombre.upper()}</b> identificado como aparece al pie de la firma, solicito realizar la "
            f"retención en la fuente con fundamento en el Parágrafo 2 del Artículo 17 de la Ley 1819 de 2016, "
            f"el cual estableció para el artículo 383 del Estatuto Tributario lo siguiente: <i>“Parágrafo 2. La "
            f"retención en la fuente establecida en el presente artículo será aplicable a los pagos o abonos "
            f"en cuenta por concepto de ingresos por honorarios y por compensación por servicios personales "
            f"obtenidos por las personas que informen que no han contratado o vinculado dos (2) o más "
            f"trabajadores asociados a la actividad”</i>."
        )
        story.append(Paragraph(p_legal, s_cuerpo))
        story.append(Paragraph("Que los datos del contrato son:", s_cuerpo_left))
        story.append(Spacer(1, 0.1 * cm))

        # Tabla 1: Datos contrato (3 columnas compactas y centradas en la página)
        t1_data = [
            [Paragraph("a.", s_cell), Paragraph("Contrato:", s_cell), Paragraph(no_contrato, s_cell)],
            [Paragraph("b.", s_cell), Paragraph("Razón social:", s_cell), Paragraph("Instituto Nacional de Vías-INVIAS", s_cell)],
            [Paragraph("c.", s_cell), Paragraph("NIT Entidad:", s_cell), Paragraph("800.215.807-2", s_cell)],
            [Paragraph("d.", s_cell), Paragraph("Valor del contrato:", s_cell), Paragraph(f"$ {_formatear_pesos(valor_contrato)[:-3]}", s_cell)],
            [Paragraph("e.", s_cell), Paragraph("Fecha de inicio:", s_cell), Paragraph(fecha_ini_str, s_cell)],
            [Paragraph("f.", s_cell), Paragraph("Fecha de terminación:", s_cell), Paragraph(fecha_fin_str, s_cell)],
        ]
        t1 = Table(t1_data, colWidths=[0.6 * cm, 3.8 * cm, 6.5 * cm], hAlign='CENTER')
        t1.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
            ("TOPPADDING", (0, 0), (-1, -1), 0.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(t1)
        story.append(Spacer(1, 0.2 * cm))

        # Párrafo Certifico Régimen
        regimen_db = tributaria.get("regimen") or "NULL"
        regimen_str = regimen_db.replace("_", " ").upper()
        rut_str = tributaria.get("rut") or "—"
        renta_str = "SI RENTA" if declarante_renta else "NO RENTA"

        p_regimen = (
            f"De igual manera, bajo la gravedad de juramento certifico que: PERTENEZCO AL RÉGIMEN <b>{regimen_str}</b>, "
            f"CON RUT No. <b>{rut_str}</b> y <b>{renta_str}</b>"
        )
        story.append(Paragraph(p_regimen, s_cuerpo))

        # Párrafo Seguridad Social
        eps_info = seguridad_social.get("eps") or {}
        afp_info = seguridad_social.get("afp") or {}
        arl_info = seguridad_social.get("arl") or {}

        eps_name = (eps_info.get("entidad") or "EPS").replace("_", " ").upper()
        eps_val = eps_info.get("valor") or 0

        afp_name = (afp_info.get("entidad") or "FONDO DE PENSIONES").replace("_", " ").upper()
        afp_val = afp_info.get("valor") or 0

        arl_name = (arl_info.get("entidad") or "ARL").replace("_", " ").upper()
        arl_val = arl_info.get("valor") or 0

        if planilla_mes_vencido:
            p_seg_social = (
                f"También declaró bajo la gravedad de juramento, que el documento soporte de pago de aportes obligatorios "
                f"al Sistema General de Seguridad Social, realizados a la Entidad Prestadora de <b>{eps_name}</b> y "
                f"aporte obligatorio realizados al Fondo de Pensiones <b>{afp_name}</b> correspondiente al pago a mes vencido en periodo del mes de "
                f"<b>{nombre_mes_planilla.upper()}</b> de <b>{año_planilla}</b>, corresponde a la suma de:"
            )
        else:
            p_seg_social = (
                f"También declaró bajo la gravedad de juramento, que el documento soporte de pago de aportes obligatorios "
                f"al Sistema General de Seguridad Social, realizados a la Entidad Prestadora de <b>{eps_name}</b> y "
                f"aporte obligatorio realizados al Fondo de Pensiones <b>{afp_name}</b> correspondiente al periodo del mes de "
                f"<b>{nombre_mes_planilla.upper()}</b> de <b>{año_planilla}</b>, corresponde a la suma de:"
            )
        story.append(Paragraph(p_seg_social, s_cuerpo))
        story.append(Spacer(1, 0.1 * cm))

        # Tabla 2: Seguridad Social (más angosta, bordes delgados de 0.25pt y centrada)
        t2_data = [
            [Paragraph("<b>Concepto</b>", s_cell_hdr), Paragraph("<b>Valor</b>", s_cell_hdr)],
            [Paragraph(eps_name, s_cell), Paragraph(f"{_formatear_pesos(eps_val)[:-3]}", s_cell_center)],
            [Paragraph(afp_name, s_cell), Paragraph(f"{_formatear_pesos(afp_val)[:-3]}", s_cell_center)],
            [Paragraph(arl_name, s_cell), Paragraph(f"{_formatear_pesos(arl_val)[:-3]}", s_cell_center)],
        ]
        t2 = Table(t2_data, colWidths=[8.0 * cm, 3.0 * cm], hAlign='CENTER')
        t2.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.25, HexColor("#999999")),
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F9F9F9")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t2)
        story.append(Spacer(1, 0.2 * cm))

        # Honorarios
        es_ultimo_mes = False
        if fecha_fin_raw and mes_num == fecha_fin_raw.month and año_num == fecha_fin_raw.year:
            es_ultimo_mes = True

        if es_ultimo_mes:
            if contrato_vig.get("personalizar_ultimacuenta"):
                valor_pago = contrato_vig.get("valor_personalizar_ultimacuenta") or 0
            elif fecha_ini_raw and valor_contrato > 0:
                total_meses_contrato = (fecha_fin_raw.year - fecha_ini_raw.year) * 12 + (fecha_fin_raw.month - fecha_ini_raw.month)
                meses_completos = max(0, total_meses_contrato - 1)
                val_primer = contrato_vig.get("valor_primer_pago")
                if val_primer is None or val_primer == 0:
                    val_primer = valor_mensual
                valor_pago = valor_contrato - val_primer - (meses_completos * valor_mensual)
                valor_pago = max(0, valor_pago)
            else:
                valor_pago = valor_mensual
            
            dia_fin = fecha_fin_raw.day
            mes_fin_lower = MESES_ES[fecha_fin_raw.month - 1].lower()
            periodo_texto = f"DEL 1 DE {mes_fin_lower.upper()} AL {dia_fin} DE {mes_fin_lower.upper()} DEL {año_num}"
        else:
            valor_pago = valor_mensual
            periodo_texto = f"{nombre_mes_exp.upper()}"

        val_letras = _numero_a_letras(int(valor_pago))
        val_num_fmt = _formatear_pesos(valor_pago)
        p_honorarios = (
            f"Que el valor a cobrar por concepto de honorarios corresponden al periodo del <b><i>{periodo_texto}</i></b> "
            f"y ascienden a la suma de: <b><i>{val_letras} ($ {val_num_fmt}) M/Cte.</i></b>"
        )
        story.append(Paragraph(p_honorarios, s_cuerpo))
        story.append(Spacer(1, 0.3 * cm))

        # Despedida
        story.append(Paragraph("Atentamente,", s_cuerpo_left))
        story.append(Spacer(1, 0.1 * cm))

        # Firma
        from app.services.firma_service import FirmaService
        firma_bytes = FirmaService().obtener_imagen(usuario_id)

        s_firma_nombre = ParagraphStyle(
            "ret_fn", parent=estilos["Normal"],
            fontSize=9.5, fontName="Helvetica-Bold", alignment=TA_CENTER,
            textColor=NEGRO, leading=13,
        )
        s_firma_sub = ParagraphStyle(
            "ret_fs", parent=estilos["Normal"],
            fontSize=9, alignment=TA_CENTER, leading=12, textColor=NEGRO,
            fontName="Helvetica",
        )

        if firma_bytes:
            firma_img = Image(io.BytesIO(firma_bytes), width=5.2 * cm, height=2.6 * cm, kind="proportional")
            filas_firma = [
                [firma_img],
                [Paragraph(nombre, s_firma_nombre)],
                [Paragraph(f"{tipo_doc}. {cedula} de {lugar_exp}", s_firma_sub)],
            ]
        else:
            filas_firma = [
                [""],
                [Paragraph(nombre, s_firma_nombre)],
                [Paragraph(f"{tipo_doc}. {cedula} de {lugar_exp}", s_firma_sub)],
            ]

        firma_tabla = Table(filas_firma, colWidths=[8.5 * cm], hAlign="CENTER")
        firma_tabla.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, NEGRO),
            ("TOPPADDING",    (0, 0), (-1, 0),  0),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  0),
            ("TOPPADDING",    (0, 1), (-1, 1),  3),
        ]))
        story.append(firma_tabla)

        doc.build(story)
        buf.seek(0)
        return buf.getvalue()

    def generar_pdf_acta_compromiso(self, certificacion: Dict) -> bytes:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import black
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, Image,
        )

        NEGRO = black

        # 1. Datos del usuario
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_id = str(certificacion.get("usuario_id", ""))
        usuario_data: dict = {}
        if usuario_id:
            try:
                usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
            except Exception:
                pass

        nombre = usuario_data.get("nombre_completo", "")
        tipo_doc = usuario_data.get("tipo_documento", "C.C.")
        cedula = usuario_data.get("numero_documento") or "—"
        lugar_exp = usuario_data.get("lugar_expedicion_documento") or "—"

        info_laboral = usuario_data.get("informacion_laboral") or {}
        seg_social = info_laboral.get("seguridad_social") or {}

        # AFP
        afp_obj = seg_social.get("afp") or {}
        afp_val = afp_obj.get("valor")
        if afp_val is not None:
            afp_str = f"{afp_val:,.0f}".replace(",", ".")
        else:
            afp_str = afp_obj.get("entidad") or "—"

        # EPS
        eps_obj = seg_social.get("eps") or {}
        eps_val = eps_obj.get("valor")
        if eps_val is not None:
            eps_str = f"{eps_val:,.0f}".replace(",", ".")
        else:
            eps_str = eps_obj.get("entidad") or "—"

        # ARL
        arl_obj = seg_social.get("arl") or {}
        arl_val = arl_obj.get("valor")
        if arl_val is not None:
            arl_str = f"{arl_val:,.0f}".replace(",", ".")
        else:
            arl_str = arl_obj.get("entidad") or "—"

        # Contrato del usuario
        contratos = usuario_data.get("contratos") or []
        año_cert = certificacion.get("año")
        mes_cert = certificacion.get("mes", 1)
        contrato_vig = self._contrato_para_periodo(contratos, año_cert, mes_cert)
        no_contrato = contrato_vig.get("numero", "—")
        fecha_ini_raw = contrato_vig.get("fecha_inicio")
        año_contrato = str(fecha_ini_raw.year) if fecha_ini_raw else "—"

        # Mes de expedición y año de expedición
        cert_month = certificacion.get("mes", 1)
        cert_year = certificacion.get("año", 2026)
        mes_nombre_upper = MESES_ES[cert_month - 1].upper()
        mes_nombre_lower = MESES_ES[cert_month - 1].lower()

        # Fecha de expedición (fecha de corte/firma)
        fecha_corte = certificacion.get("fecha_corte")
        if fecha_corte:
            dt = utc_a_bogota(fecha_corte)
        else:
            dt = datetime.now(ZONA_BOGOTA)
        def _dia_a_letras(d: int) -> str:
            dias_letras = {
                1: "un", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
                11: "once", 12: "doce", 13: "trece", 14: "catorce", 15: "quince", 16: "dieciséis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve", 20: "veinte",
                21: "veintiuno", 22: "veintidós", 23: "veintitres", 24: "veinticuatro", 25: "veinticinco", 26: "veintiséis", 27: "veintissiete", 28: "veintiocho", 29: "veintinueve", 30: "treinta", 31: "treinta y uno"
            }
            return dias_letras.get(d, str(d))

        dia_texto = _dia_a_letras(dt.day)
        dia_numero = str(dt.day)
        mes_exp_texto = MESES_ES[dt.month - 1].lower()
        año_expedicion = str(dt.year)

        # Configuración del documento PDF - Reducimos márgenes para asegurar 1 página
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=2.2 * cm,
            rightMargin=2.2 * cm,
            topMargin=1.8 * cm,
            bottomMargin=1.8 * cm,
        )

        estilos = getSampleStyleSheet()

        s_cuerpo = ParagraphStyle(
            "acta_cuerpo", parent=estilos["Normal"],
            fontSize=11, alignment=TA_JUSTIFY, leading=16, spaceAfter=12,
            textColor=NEGRO, fontName="Helvetica",
        )
        s_cuerpo_center = ParagraphStyle(
            "acta_cuerpo_c", parent=estilos["Normal"],
            fontSize=11, alignment=TA_CENTER, leading=16, spaceAfter=12,
            textColor=NEGRO, fontName="Helvetica-Bold",
        )
        s_cuerpo_bold_center = ParagraphStyle(
            "acta_cuerpo_bc", parent=estilos["Normal"],
            fontSize=12, alignment=TA_CENTER, leading=17, spaceAfter=10,
            fontName="Helvetica-Bold", textColor=NEGRO,
        )

        story = []

        # TÍTULOS
        story.append(Paragraph("<b>ACTA DE COMPROMISO</b>", s_cuerpo_bold_center))
        story.append(Paragraph(f"<b>CONTRATO DE PRESTACIÓN DE SERVICIOS No. {no_contrato} DE {año_contrato}</b>", s_cuerpo_bold_center))
        story.append(Spacer(1, 0.4 * cm))

        # Párrafo Inicial
        p_inicial = (
            f"Yo <b>{nombre}</b>, identificado con <b>{tipo_doc}</b> No. <b>{cedula}</b> expedida en <b>{lugar_exp}</b>, "
            f"Contratista de Prestación de Servicios profesionales del Instituto Nacional de Vías y Gladys "
            f"Gutiérrez Buitrago Supervisora del Contrato No. <b>{no_contrato}</b> de <b>{año_contrato}</b>, para la prestación de los "
            f"servicios correspondientes al mes de <b>{mes_nombre_upper}</b> de la citada vigencia y pago de estos."
        )
        story.append(Paragraph(p_inicial, s_cuerpo))

        # HACEN CONSTAR QUE
        story.append(Paragraph("<b>HACEN CONSTAR QUE:</b>", s_cuerpo_center))

        # Declaración 1
        p_decl_1 = (
            f"El Contratista se compromete a prestar sus servicios profesionales al Instituto Nacional de Vías hasta la fecha "
            f"de terminación de su contrato No. <b>{no_contrato}</b> de <b>{año_contrato}</b>, aun cuando el pago por este concepto se realice con algunos "
            f"días de anterioridad a la causación del mes."
        )
        story.append(Paragraph(p_decl_1, s_cuerpo))

        # Declaración 2
        p_decl_2 = (
            f"El contratista con la suscripción de la presente autoriza al Instituto Nacional de Vías para hacer efectiva la "
            f"garantía única de cumplimiento general del contrato, en el evento en que no cumpla con la prestación de los "
            f"servicios requeridos hasta la fecha de terminación, (si aplica) de acuerdo con el objeto del contrato No. <b>{no_contrato}</b> de <b>{año_contrato}</b>, "
            f"<u>por el valor no ejecutado que se le pague por concepto de honorarios del periodo del mes</u>."
        )
        story.append(Paragraph(p_decl_2, s_cuerpo))

        # Declaración 3
        p_decl_3 = (
            f"Que de conformidad con el artículo 23 de la ley 1150 de 2007 y la Ley 100 de 1993, Ley 789 de 2002, Ley 828 "
            f"de 2003, Ley 797 de 2003, por el Decreto 1703 de 2002 y las demás normas concordantes y complementarias "
            f"sobre la materia, el Supervisor del contrato certifica que el Contratista se encuentra al día con los pagos "
            f"mensuales en Salud, pensión y ARL correspondiente al mes de <b>{mes_nombre_lower}</b> de <b>{cert_year}</b>, así:"
        )
        story.append(Paragraph(p_decl_3, s_cuerpo))

        # Cotizaciones
        ibc_val = info_laboral.get("ibc_prestaciones_sociales")
        if ibc_val is not None:
            ibc_str = f"{ibc_val:,.0f}".replace(",", ".")
        else:
            ibc_str = "—"

        story.append(Paragraph(f"<b>Ingreso Base de Cotización: $ {ibc_str}</b>", s_cuerpo))
        story.append(Paragraph(f"<b>AFP:</b> <b>{afp_str}</b>", s_cuerpo))
        story.append(Paragraph(f"<b>EPS:</b> <b>{eps_str}</b>", s_cuerpo))
        story.append(Paragraph(f"<b>ARL:</b> <b>{arl_str}</b>", s_cuerpo))

        # Suscripción
        p_suscripcion = (
            f"Se suscribe en la ciudad de Bogotá a los <b>{dia_texto}</b> (<b>{dia_numero}</b>) días del mes de <b>{mes_exp_texto}</b> de <b>{año_expedicion}</b>."
        )
        story.append(Paragraph(p_suscripcion, s_cuerpo))
        story.append(Spacer(1, 0.8 * cm))

        # --- Firmas alineadas (Izquierda y Derecha) ---
        from app.services.firma_service import FirmaService
        firma_contratista_bytes = FirmaService().obtener_imagen(usuario_id)

        # Cargar firma del Jefe
        jefe_nombre = "Gladys Gutiérrez Buitrago"
        jefe_firma_img = None

        firma_jefe_doc = certificacion.get("firmas", {}).get("jefe")
        jefe_id_str = None
        if firma_jefe_doc:
            jefe_nombre = firma_jefe_doc.get("firmante_nombre", jefe_nombre)
            jefe_id_str = str(firma_jefe_doc.get("firmante_id", ""))
        else:
            config_firmantes = self.obtener_firmantes_config("firmantes_formatos_actas", TIPOS_FIRMA_ACTAS)
            jefe_config = config_firmantes.get("jefe") or {}
            jefe_nombre = jefe_config.get("nombre", jefe_nombre)
            jefe_id_str = jefe_config.get("usuario_id")

        if jefe_id_str:
            jefe_firma_bytes = FirmaService().obtener_imagen(jefe_id_str)
            if jefe_firma_bytes:
                jefe_firma_img = Image(io.BytesIO(jefe_firma_bytes), width=4.0 * cm, height=1.2 * cm, kind="proportional")

        if not jefe_firma_img and jefe_nombre == "Gladys Gutiérrez Buitrago":
            firma_gladys_path = os.path.join("app", "assets", "firma_gla.png")
            if os.path.exists(firma_gladys_path):
                jefe_firma_img = Image(firma_gladys_path, width=4.0 * cm, height=1.2 * cm, kind="proportional")

        firma_contratista_img = ""
        if firma_contratista_bytes:
            firma_contratista_img = Image(io.BytesIO(firma_contratista_bytes), width=4.0 * cm, height=1.2 * cm, kind="proportional")

        s_firma_lbl = ParagraphStyle(
            "acta_firma_lbl", parent=estilos["Normal"],
            fontSize=9.5, fontName="Helvetica-Bold", leading=13,
            textColor=NEGRO, alignment=TA_CENTER,
        )
        s_firma_desc = ParagraphStyle(
            "acta_firma_desc", parent=estilos["Normal"],
            fontSize=8.5, fontName="Helvetica", leading=12,
            textColor=NEGRO, alignment=TA_CENTER,
        )

        col_izq = [
            firma_contratista_img,
            Paragraph(f"<b>{nombre}</b>", s_firma_lbl),
            Paragraph(f"CONTRATISTA CTO {no_contrato} de {año_contrato}", s_firma_desc),
            Paragraph(f"{tipo_doc}. {cedula} {lugar_exp}", s_firma_desc)
        ]

        col_der = [
            Spacer(1, 1.2 * cm),
            Paragraph(f"<b>{jefe_nombre}</b>", s_firma_lbl),
            Paragraph("Subdirectora de Reglamentación Técnica e Innovación", s_firma_desc) if jefe_nombre == "Gladys Gutiérrez Buitrago" else Paragraph("Supervisora de Reglamentación Técnica y Innovación", s_firma_desc),
            Paragraph(f"SUPERVISOR CTO {no_contrato} de {año_contrato}", s_firma_desc)
        ]

        # Estructurar tabla de firmas de dos columnas con espacio intermedio (3 columnas totales)
        ancho_firma = 7.0 * cm
        ancho_espacio = doc.width - (2 * ancho_firma)
        
        # Las celdas vacías representarán el espaciado
        datos_tabla = [
            [col_izq[0], "", col_der[0]],
            [col_izq[1], "", col_der[1]],
            [col_izq[2], "", col_der[2]],
            [col_izq[3], "", col_der[3]],
        ]

        tabla_firmas = Table(datos_tabla, colWidths=[ancho_firma, ancho_espacio, ancho_firma])
        tabla_firmas.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LINEABOVE", (0, 1), (0, 1), 0.5, NEGRO), # Línea de firma contratista
            ("LINEABOVE", (2, 1), (2, 1), 0.5, NEGRO), # Línea de firma supervisor
        ]))

        story.append(tabla_firmas)

        doc.build(story)
        buf.seek(0)
        return buf.getvalue()

    def generar_pdf_acta_recibo_entrega(self, certificacion: Dict) -> bytes:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import black
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, Image,
        )

        NEGRO = black

        # 1. Datos del usuario
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_id = str(certificacion.get("usuario_id", ""))
        usuario_data: dict = {}
        if usuario_id:
            try:
                usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
            except Exception:
                pass

        nombre = usuario_data.get("nombre_completo", "")
        tipo_doc = usuario_data.get("tipo_documento", "C.C.")
        cedula = usuario_data.get("numero_documento") or "—"
        lugar_exp = usuario_data.get("lugar_expedicion_documento") or "—"

        contratos = usuario_data.get("contratos") or []
        año_cert = certificacion.get("año")
        mes_cert = certificacion.get("mes", 1)
        contrato_vig = self._contrato_para_periodo(contratos, año_cert, mes_cert)
        no_contrato = contrato_vig.get("numero") or "—"
        
        año = certificacion.get("año")
        mes_num = certificacion.get("mes", 1)
        mes_nombre = MESES_ES[mes_num - 1]

        buf = io.BytesIO()
        custom_width = letter[0] + 2.0 * cm

        estilos = getSampleStyleSheet()
        s_titulo = ParagraphStyle(
            "acta_recibo_tit", parent=estilos["Normal"],
            fontSize=11, fontName="Helvetica-Bold", alignment=TA_CENTER,
            spaceAfter=15, leading=14
        )
        s_cuerpo = ParagraphStyle(
            "acta_recibo_cuerpo", parent=estilos["Normal"],
            fontSize=10, alignment=TA_JUSTIFY, leading=14, spaceAfter=8
        )

        s_header_bold_center = ParagraphStyle(
            "header_bold_center", parent=estilos["Normal"],
            fontSize=6.5, fontName="Helvetica-Bold", alignment=TA_CENTER,
            leading=8.5, textColor=NEGRO
        )
        s_cell_label = ParagraphStyle(
            "cell_label", parent=estilos["Normal"],
            fontSize=7, fontName="Helvetica-Bold", alignment=TA_CENTER,
            leading=9, textColor=NEGRO
        )
        s_cell_value = ParagraphStyle(
            "cell_value", parent=estilos["Normal"],
            fontSize=7, fontName="Helvetica", alignment=TA_CENTER,
            leading=9, textColor=NEGRO
        )

        story = []

        # Ancho total disponible = 19.59 cm
        w_col1 = 3.5 * cm
        w_col2 = 10.7 * cm
        w_col3 = 2.5 * cm
        w_col4 = 2.89 * cm

        logo_path = os.path.join("app", "assets", "INVIAS.png")
        if os.path.exists(logo_path):
            logo_img = Image(logo_path, width=3.3 * cm, height=1.3 * cm, kind="proportional")
        else:
            logo_img = Paragraph("<b>INVIAS</b>", s_cell_label)

        p_proceso = Paragraph("<b>PROCESO:</b> GESTIÓN CONTRACTUAL, PROCESOS ADMINISTRATIVOS Y SANCIONATORIO", s_header_bold_center)
        p_formato = Paragraph("<b>FORMATO:</b> BALANCE GENERAL DEL CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES O DE APOYO A LA GESTIÓN", s_header_bold_center)
        
        col2_content = [
            p_proceso,
            Spacer(1, 4),
            p_formato
        ]

        t_col3 = Table(
            [
                [Paragraph("CÓDIGO", s_cell_label)],
                [Paragraph("VERSIÓN", s_cell_label)]
            ],
            colWidths=[w_col3],
            rowHeights=[0.8 * cm, 0.8 * cm]
        )
        t_col3.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (0, 0), 0.5, NEGRO),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        t_col4 = Table(
            [
                [Paragraph("ACPA-FR-11", s_cell_label)],
                [Paragraph("2", s_cell_value)]
            ],
            colWidths=[w_col4],
            rowHeights=[0.8 * cm, 0.8 * cm]
        )
        t_col4.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (0, 0), 0.5, NEGRO),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        header_table = Table(
            [
                [logo_img, col2_content, t_col3, t_col4]
            ],
            colWidths=[w_col1, w_col2, w_col3, w_col4],
            rowHeights=[1.6 * cm]
        )
        header_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.7, NEGRO),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        story.append(header_table)
        
        story.append(Spacer(1, 0.4 * cm))

        from reportlab.platypus import Flowable
        class DottedLine(Flowable):
            def __init__(self, width, thickness=0.8, color=NEGRO):
                Flowable.__init__(self)
                self.width = width
                self.thickness = thickness
                self.color = color
            def draw(self):
                self.canv.saveState()
                self.canv.setStrokeColor(self.color)
                self.canv.setLineWidth(self.thickness)
                self.canv.setDash([1, 1.5])  # Patrón punteado
                self.canv.line(0, 0, self.width, 0)
                self.canv.restoreState()

        from reportlab.lib.colors import HexColor
        AZUL_CABECERA = HexColor("#3a9ad9")
        AZUL_CLARO = HexColor("#D2E9F6")

        # Cargar variables del contrato y laboral del usuario
        informacion_laboral = usuario_data.get("informacion_laboral") or {}
        paga_iva = informacion_laboral.get("paga_iva", False)
        valor_iva = informacion_laboral.get("valor_iva", 0) or 0

        fecha_ini_dt = contrato_vig.get("fecha_inicio")
        fecha_fin_dt = contrato_vig.get("fecha_fin")
        fecha_fin_str = fecha_fin_dt.strftime("%d/%m/%Y") if fecha_fin_dt else "—"
        objeto_str = (contrato_vig.get("objeto") or "").upper()

        adiciones = (contrato_vig.get("adiciones_contrato") or {}) if contrato_vig else {}
        tiene_adiciones = bool(adiciones.get("tiene_adiciones"))
        valor_adicion = adiciones.get("valor_adicion") or 0 if tiene_adiciones else 0

        valor_inicial = contrato_vig.get("valor") or 0
        valor_total = valor_inicial + valor_adicion
        valor_str = f"$   {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        valor_total_ejecutado = contrato_vig.get("valor_total_ejecutado_contrato", 0) or 0
        valor_total_pagado = contrato_vig.get("valor_total_pagado", 0) or 0
        saldo_liberar = contrato_vig.get("saldo_presp_lib_contrato", 0) or 0

        s_lbl_body = ParagraphStyle(
            "lbl_body", parent=estilos["Normal"],
            fontSize=7.5, fontName="Helvetica-Bold", leading=10.5, textColor=NEGRO
        )
        s_val_body = ParagraphStyle(
            "val_body", parent=estilos["Normal"],
            fontSize=7.5, fontName="Helvetica", leading=10.5, textColor=NEGRO
        )
        s_val_body_right = ParagraphStyle(
            "val_body_right", parent=estilos["Normal"],
            fontSize=7.5, fontName="Helvetica", leading=10.5, alignment=2, textColor=NEGRO
        )
        s_lbl_body_normal = ParagraphStyle(
            "lbl_body_normal", parent=estilos["Normal"],
            fontSize=7.5, fontName="Helvetica", leading=10.5, textColor=NEGRO
        )

        def format_document(doc_str):
            if not doc_str:
                return "—"
            doc_str = str(doc_str).replace(".", "").replace(",", "").strip()
            if doc_str.isdigit():
                reversed_str = doc_str[::-1]
                chunks = [reversed_str[i:i+3] for i in range(0, len(reversed_str), 3)]
                return ".".join(chunks)[::-1]
            return doc_str

        def numero_a_letras(n):
            n = int(n)
            if n == 0:
                return "CERO"
            unidades = ["", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
            especiales = {
                10: "DIEZ", 11: "ONCE", 12: "DOCE", 13: "TRECE", 14: "CATORCE", 15: "QUINCE",
                16: "DIECISEIS", 17: "DIECISIETE", 18: "DIECIOCHO", 19: "DIECINUEVE",
                21: "VEINTIUNO", 22: "VEINTIDOS", 23: "VEINTITRES", 24: "VEINTICUATRO",
                25: "VEINTICINCO", 26: "VEINTISEIS", 27: "VEINTISIETE", 28: "VEINTIOCHO", 29: "VEINTINUEVE"
            }
            decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
            centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

            def _convertir(num):
                if num in especiales:
                    return especiales[num]
                elif num < 10:
                    return unidades[num]
                elif num < 30:
                    if num == 20: return "VEINTE"
                    return especiales.get(num, "")
                elif num < 100:
                    u = num % 10
                    d = num // 10
                    if u > 0:
                        return f"{decenas[d]} Y {unidades[u]}"
                    return decenas[d]
                elif num < 1000:
                    if num == 100:
                        return "CIEN"
                    d_u = num % 100
                    c = num // 100
                    if d_u > 0:
                        return f"{centenas[c]} {_convertir(d_u)}"
                    return centenas[c]
                elif num < 1000000:
                    m = num // 1000
                    resto = num % 1000
                    m_str = "MIL" if m == 1 else f"{_convertir(m)} MIL"
                    if resto > 0:
                        return f"{m_str} {_convertir(resto)}"
                    return m_str
                elif num < 1000000000:
                    millon = num // 1000000
                    resto = num % 1000000
                    if millon == 1:
                        mill_str = "UN MILLON"
                    else:
                        mill_words = _convertir(millon)
                        if mill_words.endswith("UNO"):
                            mill_words = mill_words[:-3] + "UN"
                        elif mill_words == "UNO":
                            mill_words = "UN"
                        mill_str = f"{mill_words} MILLONES"
                    if resto > 0:
                        return f"{mill_str} {_convertir(resto)}"
                    return mill_str
                return str(num)

            return _convertir(n).strip()

        def crear_celda_moneda(valor, ancho, show_dash_if_none=True):
            if valor is None or valor == 0:
                if not show_dash_if_none:
                    return ""
                valor_str = "-"
            else:
                valor_str = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            t_mon = Table(
                [
                    [Paragraph("<b>$</b>", s_lbl_body), Paragraph(valor_str, s_val_body_right)]
                ],
                colWidths=[1.0 * cm, ancho - 1.0 * cm],
                rowHeights=[0.5 * cm]
            )
            t_mon.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            return t_mon

        # --- Tabla Balance General ---
        s_header_balance = ParagraphStyle(
            "header_balance", parent=estilos["Normal"],
            fontSize=8, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=10, textColor=HexColor("#FFFFFF")
        )

        row_0 = [Paragraph("<b>BALANCE GENERAL DEL CONTRATO</b>", s_header_balance), "", ""]
        row_1 = [Paragraph("Valor contratado", s_lbl_body_normal), crear_celda_moneda(valor_total, 9.09 * cm), ""]
        
        # Fila IVA
        if paga_iva and valor_iva:
            row_2 = [Paragraph("Valor IVA", s_lbl_body_normal), crear_celda_moneda(valor_iva, 9.09 * cm), ""]
        else:
            row_2 = [Paragraph("Valor IVA", s_lbl_body_normal), "", ""]

        row_3 = [Paragraph("Valor Total Ejecutado", s_lbl_body_normal), crear_celda_moneda(valor_total_ejecutado, 4.54 * cm), ""]
        row_4 = [Paragraph("Valor total Pagado", s_lbl_body_normal), "", crear_celda_moneda(valor_total_pagado, 4.55 * cm)]
        row_5 = [Paragraph("Saldo presupuestal a Liberar", s_lbl_body_normal), crear_celda_moneda(saldo_liberar, 4.54 * cm), crear_celda_moneda(saldo_liberar, 4.55 * cm)]
        row_6 = [Paragraph("SUMAS IGUALES", s_lbl_body), crear_celda_moneda(valor_total, 4.54 * cm), crear_celda_moneda(valor_total, 4.55 * cm)]

        t_balance = Table(
            [row_0, row_1, row_2, row_3, row_4, row_5, row_6],
            colWidths=[4.5 * cm, 4.54 * cm, 4.55 * cm],
            rowHeights=[0.65 * cm, 0.6 * cm, 0.6 * cm, 0.6 * cm, 0.6 * cm, 0.6 * cm, 0.6 * cm]
        )

        t_balance_style = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.7, NEGRO),
            ("SPAN", (0, 0), (2, 0)),
            ("BACKGROUND", (0, 0), (2, 0), AZUL_CABECERA),
            ("SPAN", (1, 1), (2, 1)),
            ("SPAN", (1, 2), (2, 2)),
            ("BACKGROUND", (1, 3), (1, 3), AZUL_CLARO),
            ("BACKGROUND", (2, 4), (2, 4), AZUL_CLARO),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 1), (0, -1), 12),
            ("RIGHTPADDING", (0, 1), (0, -1), 12),
        ]

        if not paga_iva:
            t_balance_style.append(("BACKGROUND", (1, 2), (2, 2), AZUL_CLARO))

        t_balance.setStyle(TableStyle(t_balance_style))

        # Wrapper para márgenes de 2cm y 4cm de la tabla de balance
        t_wrapper = Table(
            [["", t_balance, ""]],
            colWidths=[2.0 * cm, 13.59 * cm, 4.0 * cm]
        )
        t_wrapper.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # --- Fila FECHA superior ---
        t_fecha = Table(
            [
                ["", Paragraph("FECHA", s_cell_label), Paragraph(fecha_fin_str, s_cell_value)]
            ],
            colWidths=[14.2 * cm, 2.5 * cm, 2.89 * cm],
            rowHeights=[0.55 * cm]
        )
        t_fecha.setStyle(TableStyle([
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEABOVE", (0, 0), (2, 0), 0.7, NEGRO),
            ("LINEBEFORE", (0, 0), (0, 0), 0.7, NEGRO),
            ("LINEAFTER", (2, 0), (2, 0), 0.7, NEGRO),
            ("LINEBEFORE", (1, 0), (1, 0), 0.7, NEGRO),
            ("LINEBEFORE", (2, 0), (2, 0), 0.7, NEGRO),
            ("LINEBELOW", (1, 0), (2, 0), 0.7, NEGRO),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(t_fecha)

        # --- Tabla Consolidado de Pagos ---
        AZUL_CONSOLIDADO = HexColor("#8db3e2")

        from datetime import datetime
        pagos_lista = contrato_vig.get("pagos") or []
        try:
            pagos_lista = sorted(pagos_lista, key=lambda x: x.get("fecha_pago") or datetime.min)
        except Exception:
            pass

        s_header_pagos = ParagraphStyle(
            "header_pagos", parent=estilos["Normal"],
            fontSize=8, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=10, textColor=HexColor("#FFFFFF")
        )
        s_lbl_body_normal_pagos = ParagraphStyle(
            "lbl_body_normal_pagos", parent=estilos["Normal"],
            fontSize=6.0, fontName="Helvetica", leading=8, textColor=NEGRO
        )
        s_lbl_body_center_pagos = ParagraphStyle(
            "lbl_body_center_pagos", parent=estilos["Normal"],
            fontSize=6.0, fontName="Helvetica", leading=8, alignment=1, textColor=NEGRO
        )
        s_lbl_body_center_bold_pagos = ParagraphStyle(
            "lbl_body_center_bold_pagos", parent=estilos["Normal"],
            fontSize=6.0, fontName="Helvetica-Bold", leading=8, alignment=1, textColor=NEGRO
        )
        s_val_body_right_pagos = ParagraphStyle(
            "val_body_right_pagos", parent=estilos["Normal"],
            fontSize=6.0, fontName="Helvetica", leading=8, alignment=2, textColor=NEGRO
        )

        rows_pagos = []
        # Fila 1: Cabecera
        rows_pagos.append([Paragraph(f"<b>CONSOLIDADO PAGOS CONTRATO {no_contrato}</b>", s_header_pagos), "", "", "", "", ""])
        # Fila 2: Encabezados
        rows_pagos.append([
            Paragraph("<b>No.</b>", s_lbl_body_center_bold_pagos),
            Paragraph("<b>Fecha de Pago</b>", s_lbl_body_center_bold_pagos),
            Paragraph("<b>Numero de Pago</b>", s_lbl_body_center_bold_pagos),
            Paragraph("<b>Valor Bruto</b>", s_lbl_body_center_bold_pagos),
            Paragraph("<b>Deducciones</b>", s_lbl_body_center_bold_pagos),
            Paragraph("<b>Valor Neto</b>", s_lbl_body_center_bold_pagos)
        ])

        # Fila 3 a 14: 12 filas de pagos (ancho total disponible para esta tabla es 13.59 cm)
        ancho_mon_col = 2.53 * cm
        ancho_mon_col_neto = 2.53 * cm

        def crear_celda_moneda_pagos(valor, ancho):
            if valor is None or valor == 0:
                valor_str = "-"
            else:
                valor_str = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            t_mon = Table(
                [
                    [Paragraph("<b>$</b>", s_lbl_body_normal_pagos), Paragraph(valor_str, s_val_body_right_pagos)]
                ],
                colWidths=[0.35 * cm, ancho - 0.35 * cm],
                rowHeights=[0.4 * cm]
            )
            t_mon.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]))
            return t_mon

        for idx in range(12):
            if idx < len(pagos_lista):
                p = pagos_lista[idx]
                f_pago_dt = p.get("fecha_pago")
                f_pago_str = f_pago_dt.strftime("%d/%m/%Y") if f_pago_dt else "—"
                num_p_str = str(p.get("numero_pago") or "—")
                val_bruto = p.get("valor_bruto_pago") or 0
                deduc = p.get("deducciones_pago") or 0
                val_neto = p.get("valor_neto_pago") or 0

                rows_pagos.append([
                    Paragraph(f"Pago No. {idx+1}", s_lbl_body_normal_pagos),
                    Paragraph(f_pago_str, s_lbl_body_center_pagos),
                    Paragraph(num_p_str, s_lbl_body_center_pagos),
                    crear_celda_moneda_pagos(val_bruto, ancho_mon_col),
                    crear_celda_moneda_pagos(deduc, ancho_mon_col),
                    crear_celda_moneda_pagos(val_neto, ancho_mon_col_neto)
                ])
            else:
                rows_pagos.append([
                    Paragraph(f"Pago No. {idx+1}", s_lbl_body_normal_pagos),
                    Paragraph("", s_lbl_body_center_pagos),
                    Paragraph("", s_lbl_body_center_pagos),
                    crear_celda_moneda_pagos(None, ancho_mon_col),
                    crear_celda_moneda_pagos(None, ancho_mon_col),
                    crear_celda_moneda_pagos(None, ancho_mon_col_neto)
                ])

        # Fila 15: Totales
        tot_bruto = 0
        tot_deduc = 0
        tot_neto = 0
        if pagos_lista:
            p_last = pagos_lista[-1]
            tot_bruto = p_last.get("valor_bruto_total") or 0
            tot_deduc = p_last.get("deducciones_pago_total") or 0
            tot_neto = p_last.get("valor_neto_pago_total") or 0

        rows_pagos.append([
            Paragraph("<b>TOTALES</b>", s_lbl_body_center_bold_pagos), "", "",
            crear_celda_moneda_pagos(tot_bruto, ancho_mon_col),
            crear_celda_moneda_pagos(tot_deduc, ancho_mon_col),
            crear_celda_moneda_pagos(tot_neto, ancho_mon_col_neto)
        ])

        t_consolidado = Table(
            rows_pagos,
            colWidths=[1.8 * cm, 2.0 * cm, 2.2 * cm, 2.53 * cm, 2.53 * cm, 2.53 * cm],
            rowHeights=[0.55 * cm] + [0.5 * cm] * 14
        )

        t_consolidado.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.7, NEGRO),
            ("SPAN", (0, 0), (5, 0)),
            ("BACKGROUND", (0, 0), (5, 0), AZUL_CONSOLIDADO),
            ("BACKGROUND", (3, 14), (3, 14), AZUL_CONSOLIDADO),  # Total Valor Bruto coloreado
            ("SPAN", (0, 14), (2, 14)),
            ("ALIGN", (0, 14), (2, 14), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 2), (0, 13), 8),
        ]))

        t_wrapper_pagos = Table(
            [["", t_consolidado, ""]],
            colWidths=[2.0 * cm, 13.59 * cm, 4.0 * cm]
        )
        t_wrapper_pagos.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # Párrafos de Cierre de Contrato
        s_cuerpo_texto = ParagraphStyle(
            "cuerpo_texto_cierre", parent=estilos["Normal"],
            fontSize=7.5, fontName="Helvetica", leading=11, textColor=NEGRO
        )
        s_cuerpo_texto_bold = ParagraphStyle(
            "cuerpo_texto_cierre_bold", parent=estilos["Normal"],
            fontSize=7.5, fontName="Helvetica-Bold", leading=11, textColor=NEGRO
        )

        p_texto_1 = Paragraph(
            "Previo al pago de cada una de las cuentas se verificaron los pagos de seguridad social tal como consta en la carpeta del contrato.",
            s_cuerpo_texto
        )

        # Formato de valor ejecutado
        valor_ejec_fmt = f"$ {valor_total_ejecutado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        valor_ejec_letras = numero_a_letras(valor_total_ejecutado)
        p_texto_2 = Paragraph(
            f"El valor ejecutado y pagado, ascendió a la suma de {valor_ejec_fmt} {valor_ejec_letras} PESOS M/CTE",
            s_cuerpo_texto
        )

        # Fecha de Bogotá
        dia_fin = fecha_fin_dt.day if fecha_fin_dt else datetime.now().day
        mes_fin_text = MESES_ES[(fecha_fin_dt.month - 1) if fecha_fin_dt else 0].capitalize()
        anio_fin = fecha_fin_dt.year if fecha_fin_dt else datetime.now().year
        p_texto_bogota = Paragraph(
            f"Bogotá, {dia_fin} de {mes_fin_text} de {anio_fin}.",
            s_cuerpo_texto_bold
        )

        t_wrapper_texto_1 = Table(
            [["", p_texto_1, ""]],
            colWidths=[2.0 * cm, 13.59 * cm, 4.0 * cm]
        )
        t_wrapper_texto_1.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        t_wrapper_texto_2 = Table(
            [["", p_texto_2, ""]],
            colWidths=[2.0 * cm, 13.59 * cm, 4.0 * cm]
        )
        t_wrapper_texto_2.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        t_wrapper_texto_bogota = Table(
            [["", p_texto_bogota, ""]],
            colWidths=[2.0 * cm, 13.59 * cm, 4.0 * cm]
        )
        t_wrapper_texto_bogota.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # --- Tabla OBSERVACIONES ---
        s_obs_header = ParagraphStyle(
            "obs_header", parent=estilos["Normal"],
            fontSize=7.0, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=9, textColor=NEGRO
        )
        t_observaciones = Table(
            [
                [Paragraph("<b>OBSERVACIONES</b>", s_obs_header)],
                [""]
            ],
            colWidths=[16.59 * cm],
            rowHeights=[0.45 * cm, 1.05 * cm]
        )
        t_observaciones.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.7, NEGRO),
            ("BACKGROUND", (0, 0), (-1, 0), AZUL_CABECERA),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        t_wrapper_observaciones = Table(
            [["", t_observaciones, ""]],
            colWidths=[1.5 * cm, 16.59 * cm, 1.5 * cm]
        )
        t_wrapper_observaciones.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # --- Firmas ---
        from app.services.firma_service import FirmaService
        firma_contratista_bytes = FirmaService().obtener_imagen(usuario_id)

        # Buscar nombres e IDs de Financiera, Abogado y Jefe
        config_firmantes = self.obtener_firmantes_config("firmantes_formatos_actas", TIPOS_FIRMA_ACTAS)
        
        # Financiera
        firma_fin_doc = certificacion.get("firmas", {}).get("financiera")
        fin_nombre = "sin nombre_financiera"
        fin_id_str = None
        if firma_fin_doc:
            fin_nombre = firma_fin_doc.get("firmante_nombre", fin_nombre)
            fin_id_str = str(firma_fin_doc.get("firmante_id", ""))
        else:
            fin_config = config_firmantes.get("financiera") or {}
            fin_nombre = fin_config.get("nombre", fin_nombre)
            fin_id_str = fin_config.get("usuario_id")

        # Abogado
        firma_abog_doc = certificacion.get("firmas", {}).get("abogado")
        abog_nombre = "sin nombre_abogado"
        abog_id_str = None
        if firma_abog_doc:
            abog_nombre = firma_abog_doc.get("firmante_nombre", abog_nombre)
            abog_id_str = str(firma_abog_doc.get("firmante_id", ""))
        else:
            abog_config = config_firmantes.get("abogado") or {}
            abog_nombre = abog_config.get("nombre", abog_nombre)
            abog_id_str = abog_config.get("usuario_id")

        # Jefe (Supervisor)
        firma_jefe_doc = certificacion.get("firmas", {}).get("jefe")
        jefe_nombre = "GLADYS GUTIÉRREZ BUITRAGO"
        jefe_id_str = None
        if firma_jefe_doc:
            jefe_nombre = firma_jefe_doc.get("firmante_nombre", jefe_nombre)
            jefe_id_str = str(firma_jefe_doc.get("firmante_id", ""))
        else:
            jefe_config = config_firmantes.get("jefe") or {}
            jefe_nombre = jefe_config.get("nombre", jefe_nombre)
            jefe_id_str = jefe_config.get("usuario_id")

        # Cargar firma del Jefe
        jefe_firma_img = None
        if jefe_id_str:
            jefe_firma_bytes = FirmaService().obtener_imagen(jefe_id_str)
            if jefe_firma_bytes:
                jefe_firma_img = Image(io.BytesIO(jefe_firma_bytes), width=4.0 * cm, height=1.2 * cm, kind="proportional")

        # Fallback a Gladys si no hay firma registrada y es su nombre
        if not jefe_firma_img and jefe_nombre == "GLADYS GUTIÉRREZ BUITRAGO":
            firma_gladys_path = os.path.join("app", "assets", "firma_gla.png")
            if os.path.exists(firma_gladys_path):
                jefe_firma_img = Image(firma_gladys_path, width=4.0 * cm, height=1.2 * cm, kind="proportional")

        firma_contratista_img = ""
        if firma_contratista_bytes:
            firma_contratista_img = Image(io.BytesIO(firma_contratista_bytes), width=4.0 * cm, height=1.2 * cm, kind="proportional")

        s_firma_lbl = ParagraphStyle(
            "acta_recibo_f_lbl", parent=estilos["Normal"],
            fontSize=7.0, fontName="Helvetica-Bold", alignment=TA_CENTER,
            leading=8, spaceAfter=0
        )
        s_firma_desc = ParagraphStyle(
            "acta_recibo_f_desc", parent=estilos["Normal"],
            fontSize=6.5, fontName="Helvetica", alignment=TA_CENTER,
            leading=7.5
        )

        col_der = [
            Spacer(1, 1.2 * cm),
            Paragraph(f"<b>{jefe_nombre.upper()}</b>", s_firma_lbl),
            Paragraph("Subdirectora de Reglamentación Técnica e Innovación", s_firma_desc) if jefe_nombre == "GLADYS GUTIÉRREZ BUITRAGO" else Paragraph("Supervisora de Reglamentación Técnica e Innovación", s_firma_desc),
            Paragraph("Supervisor (a) del Contrato", s_firma_desc)
        ]

        datos_tabla = [
            ["", col_der[0], ""],
            ["", col_der[1], ""],
            ["", col_der[2], ""],
            ["", col_der[3], ""],
        ]

        tabla_firmas = Table(datos_tabla, colWidths=[6.29 * cm, 7.0 * cm, 6.3 * cm])
        tabla_firmas.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LINEABOVE", (1, 1), (1, 1), 0.5, NEGRO),
        ]))

        # Contenido del cuerpo principal del cuadro
        num_contrato_p = [Paragraph(no_contrato, s_val_body), DottedLine(3.0 * cm)]
        contratista_p = [Paragraph(nombre.upper(), s_val_body), DottedLine(12.0 * cm)]
        cedula_p = [Paragraph(format_document(cedula), s_val_body), DottedLine(3.2 * cm)]
        fecha_ini_p = [Paragraph(fecha_ini_dt.strftime("%d/%m/%Y") if fecha_ini_dt else "—", s_val_body), DottedLine(2.5 * cm)]
        fecha_fin_p = [Paragraph(fecha_fin_dt.strftime("%d/%m/%Y") if fecha_fin_dt else "—", s_val_body), DottedLine(2.5 * cm)]
        objeto_p = [Paragraph(objeto_str, s_val_body), DottedLine(12.0 * cm)]
        valor_p = [Paragraph(valor_str, s_val_body), DottedLine(4.5 * cm)]

        # --- Metadata (Elaboró/Revisó/Anexo) ---
        s_metadata_text = ParagraphStyle(
            "metadata_text", parent=estilos["Normal"],
            fontSize=6.5, fontName="Helvetica", alignment=TA_LEFT,
            leading=8.0, textColor=NEGRO
        )

        # Cargar firmas pequeñas para Financiera y Abogado
        firma_fin_img = ""
        if fin_id_str and firma_fin_doc:
            fin_bytes = FirmaService().obtener_imagen(fin_id_str)
            if fin_bytes:
                firma_fin_img = Image(io.BytesIO(fin_bytes), width=1.4 * cm, height=0.4 * cm, kind="proportional")

        firma_abog_img = ""
        if abog_id_str and firma_abog_doc:
            abog_bytes = FirmaService().obtener_imagen(abog_id_str)
            if abog_bytes:
                firma_abog_img = Image(io.BytesIO(abog_bytes), width=1.4 * cm, height=0.4 * cm, kind="proportional")

        p_meta_elaboro = Paragraph(f"<b>Elaboró:</b> {nombre}", s_metadata_text)
        
        # Tablas anidadas para alinear firmas pequeñas al frente de los nombres
        t_reviso1 = Table(
            [[Paragraph(f"<b>Revisó:</b> {fin_nombre}", s_metadata_text), firma_fin_img]],
            colWidths=[6.0 * cm, 2.0 * cm]
        )
        t_reviso1.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        t_reviso2 = Table(
            [[Paragraph(f"<b>Revisó:</b> {abog_nombre}", s_metadata_text), firma_abog_img]],
            colWidths=[6.0 * cm, 2.0 * cm]
        )
        t_reviso2.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        p_meta_anexo = Paragraph("<b>Anexo:</b> Relación de Pagos Generada por SIIF NACION – Un (1) Folio.", s_metadata_text)
        p_meta_acta = Paragraph(f"<b>Acta de Entrega y Recibo del Contrato No</b> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {no_contrato} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Un (1) Folio", s_metadata_text)

        t_wrapper_metadata = Table(
            [
                ["", p_meta_elaboro, ""],
                ["", t_reviso1, ""],
                ["", t_reviso2, ""],
                ["", p_meta_anexo, ""],
                ["", p_meta_acta, ""]
            ],
            colWidths=[1.5 * cm, 16.59 * cm, 1.5 * cm]
        )

        t_wrapper_metadata.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # Contenido del cuerpo principal del cuadro
        num_contrato_p = [Paragraph(no_contrato, s_val_body), DottedLine(3.0 * cm)]
        contratista_p = [Paragraph(nombre.upper(), s_val_body), DottedLine(12.0 * cm)]
        cedula_p = [Paragraph(format_document(cedula), s_val_body), DottedLine(3.2 * cm)]
        fecha_ini_p = [Paragraph(fecha_ini_dt.strftime("%d/%m/%Y") if fecha_ini_dt else "—", s_val_body), DottedLine(2.5 * cm)]
        fecha_fin_p = [Paragraph(fecha_fin_dt.strftime("%d/%m/%Y") if fecha_fin_dt else "—", s_val_body), DottedLine(2.5 * cm)]
        objeto_p = [Paragraph(objeto_str, s_val_body), DottedLine(12.0 * cm)]
        valor_p = [Paragraph(valor_str, s_val_body), DottedLine(4.5 * cm)]

        t_cuerpo = Table(
            [
                ["", Paragraph("Número de Contrato:", s_lbl_body), num_contrato_p],
                ["", Paragraph("Contratista:", s_lbl_body), contratista_p],
                ["", Paragraph("Cédula de Ciudadanía o NIT:", s_lbl_body), cedula_p],
                ["", Paragraph("Fecha de Inicio:", s_lbl_body), fecha_ini_p],
                ["", Paragraph("Fecha de Terminación:", s_lbl_body), fecha_fin_p],
                ["", Paragraph("Objeto:", s_lbl_body), objeto_p],
                ["", Paragraph("Valor Total del contrato:", s_lbl_body), valor_p],
                ["", "", ""],  # Spacer row 1 (for t_balance)
                [t_wrapper, "", ""],  # Nested Balance Table
                ["", "", ""],  # Spacer row 2 (for t_consolidado)
                [t_wrapper_pagos, "", ""],  # Nested Consolidated Payments Table
                ["", "", ""],  # Spacer row 3 (before closing text 1)
                [t_wrapper_texto_1, "", ""],  # Text 1
                [t_wrapper_texto_2, "", ""],  # Text 2
                ["", "", ""],  # Spacer row 4 (before Bogotá)
                [t_wrapper_texto_bogota, "", ""],  # Bogotá Date
                ["", "", ""],  # Spacer row 5 (before Observaciones)
                [t_wrapper_observaciones, "", ""],  # Observaciones Table
                [tabla_firmas, "", ""],  # Signatures
                ["", "", ""],  # Spacer row 6 (before metadata - 2 lines distance)
                [t_wrapper_metadata, "", ""]  # Metadata
            ],
            colWidths=[1.0 * cm, 5.0 * cm, 13.59 * cm]
        )
        t_cuerpo.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBEFORE", (0, 0), (0, -1), 0.7, NEGRO),
            ("LINEAFTER", (2, 0), (2, -1), 0.7, NEGRO),
            ("LINEBELOW", (0, -1), (-1, -1), 0.7, NEGRO),  # Borde inferior que cierra todo
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            
            # Spacer row 1 (Row 7)
            ("BOTTOMPADDING", (0, 7), (-1, 7), 10),
            ("TOPPADDING", (0, 7), (-1, 7), 10),
            
            # Balance Table (Row 8)
            ("SPAN", (0, 8), (2, 8)),
            
            # Spacer row 2 (Row 9)
            ("BOTTOMPADDING", (0, 9), (-1, 9), 4),
            ("TOPPADDING", (0, 9), (-1, 9), 4),
            
            # Payments Table (Row 10)
            ("SPAN", (0, 10), (2, 10)),
            ("BOTTOMPADDING", (0, 10), (-1, 10), 10),
            
            # Spacer row 3 (Row 11) - space before Text 1 (pequeño para pegar a tabla de pagos)
            ("BOTTOMPADDING", (0, 11), (-1, 11), 2),
            ("TOPPADDING", (0, 11), (-1, 11), 2),
            
            # Text 1 (Row 12)
            ("SPAN", (0, 12), (2, 12)),
            ("BOTTOMPADDING", (0, 12), (-1, 12), 2),
            ("TOPPADDING", (0, 12), (-1, 12), 0),
            
            # Text 2 (Row 13)
            ("SPAN", (0, 13), (2, 13)),
            ("BOTTOMPADDING", (0, 13), (-1, 13), 2),
            ("TOPPADDING", (0, 13), (-1, 13), 0),
            
            # Spacer row 4 (Row 14) - reduced space before Bogotá
            ("BOTTOMPADDING", (0, 14), (-1, 14), 2),
            ("TOPPADDING", (0, 14), (-1, 14), 2),
            
            # Bogotá Date (Row 15)
            ("SPAN", (0, 15), (2, 15)),
            ("BOTTOMPADDING", (0, 15), (-1, 15), 2),
            
            # Spacer row 5 (Row 16) - space before Observaciones
            ("BOTTOMPADDING", (0, 16), (-1, 16), 2),
            ("TOPPADDING", (0, 16), (-1, 16), 2),
            
            # Observaciones Table (Row 17)
            ("SPAN", (0, 17), (2, 17)),
            ("BOTTOMPADDING", (0, 17), (-1, 17), 2),
            ("TOPPADDING", (0, 17), (-1, 17), 0),
            
            # Signatures Table (Row 18)
            ("SPAN", (0, 18), (2, 18)),
            ("TOPPADDING", (0, 18), (-1, 18), 0),
            ("BOTTOMPADDING", (0, 18), (-1, 18), 2),
            
            # Spacer row 6 (Row 19) - 2 lines space before metadata
            ("SPAN", (0, 19), (2, 19)),
            ("BOTTOMPADDING", (0, 19), (-1, 19), 6),
            ("TOPPADDING", (0, 19), (-1, 19), 6),
            
            # Metadata Table (Row 20)
            ("SPAN", (0, 20), (2, 20)),
            ("TOPPADDING", (0, 20), (-1, 20), 0),
            ("BOTTOMPADDING", (0, 20), (-1, 20), 15),
        ]))
        story.append(t_cuerpo)

        # Calcular altura dinámica de la página para que se adapte exactamente a 1 hoja
        ancho_util = custom_width - 4.0 * cm  # Margen izquierdo y derecho de 2cm cada uno
        altura_total = 0
        for elemento in story:
            _, h_el = elemento.wrap(ancho_util, 100000)
            altura_total += h_el
            
        custom_height = altura_total + 4.0 * cm + 0.5 * cm
        custom_pagesize = (custom_width, custom_height)
        
        doc = SimpleDocTemplate(
            buf,
            pagesize=custom_pagesize,
            leftMargin=2.0 * cm,
            rightMargin=2.0 * cm,
            topMargin=2.0 * cm,
            bottomMargin=2.0 * cm,
        )

        def draw_page_number(canvas, doc_obj):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(NEGRO)
            w, h = doc_obj.pagesize
            # Centered at the bottom, close to the edge (0.8 * cm)
            canvas.drawCentredString(w / 2.0, 0.8 * cm, "1")
            # Right-aligned, close to the right edge (aligned with the 2.0 cm margin)
            canvas.drawRightString(w - 2.0 * cm, 0.8 * cm, "1")
            canvas.restoreState()

        doc.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)
        buf.seek(0)
        return buf.getvalue()

    def generar_pdf_acta_recibo_entrega_real(self, certificacion: Dict) -> bytes:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor, black
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, Image, Flowable,
        )

        NEGRO = black

        class DottedLine(Flowable):
            def __init__(self, width, thickness=0.8, color=NEGRO):
                Flowable.__init__(self)
                self.width = width
                self.thickness = thickness
                self.color = color
            def draw(self):
                self.canv.saveState()
                self.canv.setStrokeColor(self.color)
                self.canv.setLineWidth(self.thickness)
                self.canv.setDash([1, 1.5])  # Patrón punteado
                self.canv.line(0, 0, self.width, 0)
                self.canv.restoreState()

        AZUL_CABECERA = HexColor("#3b9bd5")

        # 1. Datos del usuario
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_id = str(certificacion.get("usuario_id", ""))
        usuario_data: dict = {}
        if usuario_id:
            try:
                usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
            except Exception:
                pass

        contratos = usuario_data.get("contratos") or []
        año_cert = certificacion.get("año")
        mes_cert = certificacion.get("mes", 1)
        contrato_vig = self._contrato_para_periodo(contratos, año_cert, mes_cert)
        no_contrato = contrato_vig.get("numero", "") if contrato_vig else ""

        # Obtener valores para Adiciones y Prórroga
        adiciones = (contrato_vig.get("adiciones_contrato") or {}) if contrato_vig else {}
        tiene_adiciones = bool(adiciones.get("tiene_adiciones"))
        valor_adicion = adiciones.get("valor_adicion") or 0

        valor_contrato = contrato_vig.get("valor") or 0 if contrato_vig else 0
        valor_total_contrato = valor_contrato + (valor_adicion if tiene_adiciones else 0)
        try:
            valor_total_formatted = f"{valor_total_contrato:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            valor_total_formatted = "0,00"

        prorroga = (contrato_vig.get("prorrogra_contrato") or {}) if contrato_vig else {}
        tiene_prorroga = bool(prorroga.get("tiene_prorroga"))
        fecha_prorroga_dt = prorroga.get("fecha_prorrogra")

        buf = io.BytesIO()
        custom_width = letter[0] + 2.0 * cm

        estilos = getSampleStyleSheet()
        
        # Estilos de cabecera
        s_header_bold_center = ParagraphStyle(
            "header_bold_center_real", parent=estilos["Normal"],
            fontSize=6.5, fontName="Helvetica", alignment=TA_CENTER,
            leading=8.5, textColor=NEGRO
        )
        s_cell_label = ParagraphStyle(
            "cell_label_real", parent=estilos["Normal"],
            fontSize=7, fontName="Helvetica-Bold", alignment=TA_CENTER,
            leading=9, textColor=NEGRO
        )
        s_cell_value = ParagraphStyle(
            "cell_value_real", parent=estilos["Normal"],
            fontSize=7, fontName="Helvetica", alignment=TA_CENTER,
            leading=9, textColor=NEGRO
        )

        logo_path = os.path.join("app", "assets", "INVIAS.png")
        if os.path.exists(logo_path):
            logo_img = Image(logo_path, width=3.3 * cm, height=1.3 * cm, kind="proportional")
        else:
            logo_img = Paragraph("<b>INVIAS</b>", s_cell_label)

        p_proceso = Paragraph("<b>PROCESO:</b> GESTION CONTRACTUAL PROCESOS ADMINISTRATIVOS Y SANCIONATORIO", s_header_bold_center)
        p_formato = Paragraph("<b>FORMATO:</b> ACTA DE RECIBO DEFINITIVO CONTRATO POR PRESTACIÓN DE SERVICIOS PROFESIONALES O DE APOYO A LA GESTIÓN", s_header_bold_center)
        
        col2_content = [
            p_proceso,
            Spacer(1, 4),
            p_formato
        ]

        # nested table for metadata (CODIGO, VERSION, PAGINA)
        s_meta_lbl = ParagraphStyle(
            "meta_lbl_real", parent=estilos["Normal"],
            fontSize=6.0, fontName="Helvetica-Bold", alignment=TA_CENTER,
            leading=7, textColor=NEGRO
        )
        s_meta_val = ParagraphStyle(
            "meta_val_real", parent=estilos["Normal"],
            fontSize=6.0, fontName="Helvetica-Bold", alignment=TA_CENTER,
            leading=7, textColor=NEGRO
        )

        t_meta_header = Table(
            [
                [Paragraph("CÓDIGO", s_meta_lbl), Paragraph("ACPA-FR-10", s_meta_val), "", ""],
                [Paragraph("VERSIÓN", s_meta_lbl), Paragraph("2", s_meta_val), "", ""],
                [Paragraph("PÁGINA", s_meta_lbl), Paragraph("1", s_meta_val), Paragraph("DE", s_meta_lbl), Paragraph("1", s_meta_val)]
            ],
            colWidths=[2.2 * cm, 1.06 * cm, 1.07 * cm, 1.06 * cm],
            rowHeights=[0.45 * cm, 0.45 * cm, 0.45 * cm]
        )
        t_meta_header.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.7, NEGRO),
            ("SPAN", (1, 0), (3, 0)),
            ("SPAN", (1, 1), (3, 1)),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # Ancho total exacto: 19.59 cm
        w_col1 = 3.5 * cm
        w_col2 = 10.7 * cm
        w_col3 = 2.5 * cm
        w_col4 = 2.89 * cm

        header_table = Table(
            [
                [logo_img, col2_content, t_meta_header, ""],
                ["", "", "", ""]
            ],
            colWidths=[w_col1, w_col2, w_col3, w_col4],
            rowHeights=[0.675 * cm, 0.675 * cm]
        )
        header_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.7, NEGRO),
            ("SPAN", (0, 0), (0, 1)),
            ("SPAN", (1, 0), (1, 1)),
            ("SPAN", (2, 0), (3, 1)),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            
            # Quitar padding en la celda del sub-cuadro de metadatos
            ("BOTTOMPADDING", (2, 0), (3, 1), 0),
            ("TOPPADDING", (2, 0), (3, 1), 0),
            ("LEFTPADDING", (2, 0), (3, 1), 0),
            ("RIGHTPADDING", (2, 0), (3, 1), 0),
        ]))

        story = [header_table]
        story.append(Spacer(1, 0.4 * cm))

        # Cuadro de fecha (DD, MM, AA) con la fecha fin del último contrato activo (incluyendo prórroga si existe)
        from app.core.zona_horaria import utc_a_bogota
        fecha_fin_efectiva_dt = None
        if contrato_vig and contrato_vig.get("fecha_fin"):
            if tiene_prorroga and fecha_prorroga_dt:
                fecha_fin_efectiva_dt = fecha_prorroga_dt
            else:
                fecha_fin_efectiva_dt = contrato_vig["fecha_fin"]
        
        dia_str = fecha_fin_efectiva_dt.strftime("%d") if fecha_fin_efectiva_dt else "—"
        mes_str = fecha_fin_efectiva_dt.strftime("%m") if fecha_fin_efectiva_dt else "—"
        anio_str = fecha_fin_efectiva_dt.strftime("%Y") if fecha_fin_efectiva_dt else "—"

        s_fecha_lbl = ParagraphStyle(
            "acta_recibo_fec_lbl", parent=estilos["Normal"],
            fontSize=6.5, fontName="Helvetica-Bold", alignment=TA_CENTER,
            leading=8, textColor=NEGRO
        )
        s_fecha_val = ParagraphStyle(
            "acta_recibo_fec_val", parent=estilos["Normal"],
            fontSize=6.5, fontName="Helvetica", alignment=TA_CENTER,
            leading=8, textColor=NEGRO
        )

        t_fecha = Table(
            [
                ["", Paragraph("DD", s_fecha_lbl), Paragraph("MM", s_fecha_lbl), Paragraph("AA", s_fecha_lbl)],
                ["", Paragraph(dia_str, s_fecha_val), Paragraph(mes_str, s_fecha_val), Paragraph(anio_str, s_fecha_val)]
            ],
            colWidths=[16.4 * cm, 1.06 * cm, 1.07 * cm, 1.06 * cm],
            rowHeights=[0.45 * cm, 0.45 * cm]
        )
        t_fecha.setStyle(TableStyle([
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("SPAN", (0, 0), (0, 1)),
            ("GRID", (1, 0), (3, 1), 0.7, NEGRO),
            ("LINEABOVE", (0, 0), (3, 0), 0.7, NEGRO),
            ("LINEBEFORE", (0, 0), (0, 1), 0.7, NEGRO),
            ("LINEAFTER", (3, 0), (3, 1), 0.7, NEGRO),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(t_fecha)

        # --- CONFIGURACIÓN Y VALORES DE DATOS DE CONTRATO ---
        nombre_contratista = usuario_data.get("nombre_completo", "").upper()
        
        fecha_ini_dt = contrato_vig.get("fecha_inicio") if contrato_vig and contrato_vig.get("fecha_inicio") else None
        fecha_inicio_str = fecha_ini_dt.strftime("%d/%m/%Y") if fecha_ini_dt else "—"

        objeto_contrato_upper = (contrato_vig.get("objeto") or "—").upper()

        valor_contrato = contrato_vig.get("valor") or 0
        try:
            valor_formatted = f"{valor_contrato:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            valor_formatted = "0,00"

        # Cálculo de plazo exacto en meses y días
        plazo_str = "—"
        if contrato_vig and contrato_vig.get("fecha_inicio") and contrato_vig.get("fecha_fin"):
            d1 = contrato_vig["fecha_inicio"]
            d2 = fecha_fin_efectiva_dt if fecha_fin_efectiva_dt else contrato_vig["fecha_fin"]
            if hasattr(d1, "date"): d1 = d1.date()
            if hasattr(d2, "date"): d2 = d2.date()
            years = d2.year - d1.year
            months = d2.month - d1.month
            days = d2.day - d1.day
            total_months = years * 12 + months
            if days < 0:
                total_months -= 1
                import calendar
                prev_month = d2.month - 1 if d2.month > 1 else 12
                prev_year = d2.year if d2.month > 1 else d2.year - 1
                days_in_prev = calendar.monthrange(prev_year, prev_month)[1]
                days += days_in_prev
            
            parts = []
            if total_months > 0:
                parts.append(f"{total_months:02d} MESES")
            if days > 0:
                parts.append(f"{days:02d} DÍAS")
            if parts:
                plazo_str = " Y ".join(parts)
            else:
                plazo_str = "00 DÍAS"

        MESES_LARGOS_ES = [
            "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
            "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
        ]
        fecha_fin_larga = "—"
        if fecha_fin_efectiva_dt:
            fecha_fin_larga = f"HASTA EL {fecha_fin_efectiva_dt.day} DE {MESES_LARGOS_ES[fecha_fin_efectiva_dt.month - 1]} DE {fecha_fin_efectiva_dt.year}"

        valor_adicion_str = "-"
        if tiene_adiciones and valor_adicion:
            try:
                valor_adicion_str = f"{valor_adicion:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                valor_adicion_str = "-"

        fecha_prorrogra_str = "—"
        if tiene_prorroga and fecha_prorroga_dt:
            try:
                fecha_prorrogra_str = fecha_prorroga_dt.strftime("%d/%m/%Y")
            except Exception:
                fecha_prorrogra_str = "—"

        # Obtener variables para textos narrativos 12-15
        fecha_fin_dt = fecha_fin_efectiva_dt

        dia_fin = str(fecha_fin_dt.day) if fecha_fin_dt else "—"
        mes_fin = MESES_ES[fecha_fin_dt.month - 1].capitalize() if fecha_fin_dt else "—"
        anio_fin = str(fecha_fin_dt.year) if fecha_fin_dt else "—"

        tipo_doc_val = (usuario_data.get("tipo_documento") or "cédula de ciudadanía").lower()

        num_doc_str = "—"
        if usuario_data.get("numero_documento"):
            try:
                num_doc_raw = int(usuario_data.get("numero_documento"))
                num_doc_str = f"{num_doc_raw:,}".replace(",", ".")
            except Exception:
                num_doc_str = str(usuario_data.get("numero_documento"))

        lugar_exp_val = usuario_data.get("lugar_expedicion_documento") or "—"
        radicado_val = contrato_vig.get("radicado_del_contrato") or "—"
        rp_val = contrato_vig.get("rp_compromiso_presupuestal") or "—"
        fecha_rp_dt = contrato_vig.get("fecha_recurso_presupuestal")

        fecha_rp_str = "—"
        if fecha_rp_dt:
            try:
                meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
                fecha_rp_str = f"{fecha_rp_dt.day:02d} de {meses_es[fecha_rp_dt.month - 1]} de {fecha_rp_dt.year}"
            except Exception:
                fecha_rp_str = "—"

        fecha_fin_larga_lower = "—"
        if fecha_fin_dt:
            try:
                meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
                fecha_fin_larga_lower = f"{fecha_fin_dt.day} de {meses_es[fecha_fin_dt.month - 1]} de {fecha_fin_dt.year}"
            except Exception:
                fecha_fin_larga_lower = "—"

        tiene_inventario = bool(contrato_vig.get("tiene_inventario"))
        desc_inventario = contrato_vig.get("desc_inventario") or ""

        # Estilos para la tabla de datos
        s_lbl_contrato = ParagraphStyle(
            "lbl_contrato_real", parent=estilos["Normal"],
            fontSize=7.5, fontName="Helvetica-Bold", alignment=TA_LEFT,
            leading=10, textColor=NEGRO
        )
        s_val_center = ParagraphStyle(
            "val_center_real", parent=estilos["Normal"],
            fontSize=7.5, fontName="Helvetica", alignment=TA_CENTER,
            leading=10, textColor=NEGRO
        )
        s_val_objeto = ParagraphStyle(
            "val_objeto_real", parent=estilos["Normal"],
            fontSize=6.5, fontName="Helvetica", alignment=TA_CENTER,
            leading=8.5, textColor=NEGRO
        )
        s_val_right = ParagraphStyle(
            "val_right_real", parent=estilos["Normal"],
            fontSize=7.5, fontName="Helvetica", alignment=TA_RIGHT,
            leading=10, textColor=NEGRO
        )
        s_caption = ParagraphStyle(
            "caption_under_real", parent=estilos["Normal"],
            fontSize=4.8, fontName="Helvetica-Oblique", alignment=TA_LEFT,
            leading=5.5, textColor=HexColor("#444444")
        )

        # Helper para celdas con linea de puntos y caption
        def crear_celda_con_linea(valor_flowable, caption_p=None, width_linea=7.0 * cm):
            flowables_val = [valor_flowable, Spacer(1, 3), DottedLine(width_linea, thickness=0.6, color=NEGRO)]
            
            tbl_rows = [[flowables_val, ""]]
            if caption_p:
                tbl_rows.append([caption_p, ""])
            
            t_cell = Table(
                tbl_rows,
                colWidths=[width_linea, 11.29 * cm - width_linea]
            )
            t_cell.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            return t_cell

        # Creador de casilla de verificación (Checkbox)
        def crear_checkbox(is_checked: bool):
            s_x = ParagraphStyle(
                "chk_x", parent=estilos["Normal"],
                fontSize=8.0, fontName="Helvetica-Bold", alignment=TA_CENTER,
                leading=8, textColor=NEGRO
            )
            val = Paragraph("X", s_x) if is_checked else ""
            t_chk = Table(
                [[val]],
                colWidths=[0.6 * cm],
                rowHeights=[0.6 * cm]
            )
            t_chk.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.7, HexColor("#999999")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            return t_chk

        def crear_col0_adicion_prorroga(lbl_text: str, is_checked: bool):
            chk = crear_checkbox(is_checked)
            t_col = Table(
                [[Paragraph(lbl_text, s_lbl_contrato), chk, ""]],
                colWidths=[3.2 * cm, 0.8 * cm, 1.3 * cm]
            )
            t_col.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            return t_col

        # Sub-cuadro para Contrato N° y Fecha con lineas punteadas
        contrato_flowables = [Paragraph(no_contrato, s_val_center), Spacer(1, 1), DottedLine(3.0 * cm, 0.6, NEGRO)]
        fecha_flowables = [Paragraph(fecha_inicio_str, s_val_center), Spacer(1, 1), DottedLine(3.0 * cm, 0.6, NEGRO)]

        t_row3_val = Table(
            [
                [
                    contrato_flowables,
                    "",
                    Paragraph("FECHA:", s_lbl_contrato),
                    fecha_flowables,
                    ""
                ],
                [
                    "",
                    "",
                    "",
                    Paragraph("Indique fecha (dia/mes/año)", s_caption),
                    ""
                ]
            ],
            colWidths=[3.0 * cm, 0.8 * cm, 1.5 * cm, 3.0 * cm, 2.99 * cm],
            rowHeights=[0.45 * cm, 0.25 * cm]
        )
        t_row3_val.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # Sub-cuadros para campos monetarios (con signo $ a la izquierda y numero a la derecha)
        t_money_inicial = Table(
            [[Paragraph("<b>$</b>", s_lbl_contrato), Paragraph(valor_formatted, s_val_right)]],
            colWidths=[1.0 * cm, 6.0 * cm],
            rowHeights=[0.45 * cm]
        )
        t_money_inicial.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        celda_valor_inicial = crear_celda_con_linea(t_money_inicial, Paragraph("(Indique en este espacio el valor total en números)", s_caption))

        t_money_total = Table(
            [[Paragraph("<b>$</b>", s_lbl_contrato), Paragraph(valor_total_formatted, s_val_right)]],
            colWidths=[1.0 * cm, 6.0 * cm],
            rowHeights=[0.45 * cm]
        )
        t_money_total.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        celda_valor_total = crear_celda_con_linea(t_money_total, Paragraph("(Indique en este espacio el valor total en números)", s_caption))

        t_money_adicion = Table(
            [[Paragraph("<b>$</b>", s_lbl_contrato), Paragraph(valor_adicion_str, s_val_right)]],
            colWidths=[1.0 * cm, 6.0 * cm],
            rowHeights=[0.45 * cm]
        )
        t_money_adicion.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        celda_adicion = crear_celda_con_linea(t_money_adicion, Paragraph("(Indique en este espacio el valor total en números)", s_caption))

        celda_prorroga = crear_celda_con_linea(Paragraph(fecha_prorrogra_str, s_val_center), Paragraph("Indique en este espacio la fecha", s_caption))

        rows_datos = [
            [Paragraph("1. UNIDAD EJECUTORA", s_lbl_contrato), crear_celda_con_linea(Paragraph("SUBDIRECCIÓN DE REGLAMENTACIÓN TÉCNICA E INNOVACIÓN", s_val_center), width_linea=11.29 * cm)],
            [Paragraph("2. DIRECCIÓN TERRITORIAL", s_lbl_contrato), crear_celda_con_linea(Paragraph("N.A.", s_val_center), width_linea=11.29 * cm)],
            [Paragraph("3. CONTRATO Nº", s_lbl_contrato), t_row3_val],
            [Paragraph("4. CONTRATISTA:", s_lbl_contrato), crear_celda_con_linea(Paragraph(nombre_contratista, s_val_center), width_linea=11.29 * cm)],
            [Paragraph("5. SUPERVISOR:", s_lbl_contrato), crear_celda_con_linea(Paragraph("GLADYS GUTIÉRREZ BUITRAGO - SUBDIRECTORA REGLAMENTACIÓN TÉCNICA E INNOVACIÓN", s_val_center), width_linea=11.29 * cm)],
            [Paragraph("6. OBJETO DEL CONTRATO:", s_lbl_contrato), crear_celda_con_linea(Paragraph(objeto_contrato_upper, s_val_objeto), width_linea=11.29 * cm)],
            [Paragraph("7. VALOR INICIAL DEL CONTRATO", s_lbl_contrato), celda_valor_inicial],
            [Paragraph("8. VALOR TOTAL DEL CONTRATO", s_lbl_contrato), celda_valor_total],
            [Paragraph("9. FECHA DE INICIO DEL CONTRATO", s_lbl_contrato), crear_celda_con_linea(Paragraph(fecha_inicio_str, s_val_center), Paragraph("Indique fecha (dia/mes/año)", s_caption))],
            [Paragraph("10. PLAZO DE EJECUCIÓN DEL CONTRATO", s_lbl_contrato), crear_celda_con_linea(Paragraph(plazo_str, s_val_center), Paragraph("(Indique en este espacio el número de meses para ejecutar el contrato)", s_caption))],
            [Paragraph("11. FECHA DE VENCIMIENTO DEL CONTRATO", s_lbl_contrato), crear_celda_con_linea(Paragraph(fecha_fin_larga, s_val_center), Paragraph("Indique fecha (dia/mes/año)", s_caption))],
            [crear_col0_adicion_prorroga("ADICIÓN", tiene_adiciones), celda_adicion],
            [crear_col0_adicion_prorroga("PRÓRROGA", tiene_prorroga), celda_prorroga],
        ]

        t_datos_contrato = Table(
            rows_datos,
            colWidths=[5.3 * cm, 11.29 * cm]
        )
        t_datos_contrato.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        t_wrapper_datos = Table(
            [["", t_datos_contrato, ""]],
            colWidths=[1.5 * cm, 16.59 * cm, 1.5 * cm]
        )
        t_wrapper_datos.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # --- Textos narrativos ---
        s_narrative = ParagraphStyle(
            "narrative_real", parent=estilos["Normal"],
            fontSize=7.2, fontName="Helvetica", alignment=TA_JUSTIFY,
            leading=10.5, textColor=NEGRO
        )

        text_12 = f"<b>12.</b> En la ciudad de Bogotá, a los <b>{dia_fin}</b> días del mes de <b>{mes_fin}</b> del año <b>{anio_fin}</b>, se reunieron: GLADYS GUTIERREZ BUITRAGO por parte del Instituto Nacional de Vías, como SUPERVISOR del Contrato de prestación de servicios Profesionales y de apoyo a la gestión <b>Nº {no_contrato} de {anio_fin}</b> y <b>{nombre_contratista}</b> como CONTRATISTA, identificada con {tipo_doc_val} No. {num_doc_str} expedida en {lugar_exp_val}, con el fin de recibir a satisfacción las obligaciones objeto del Contrato, conforme a lo establecido en las cláusulas del mismo."
        
        text_13_1 = f"<b>13.</b> El plazo inicial de ejecución del contrato de prestación de servicios <b>No. {no_contrato} de {anio_fin}</b> se pactó hasta el {fecha_fin_larga_lower}, a partir de la orden de inicio, impartida mediante oficio <b>No. {radicado_val}</b> suscrito por LA SUBDIRECTORA DE REGLAMENTACION TECNICA E INNOVACION."
        
        text_13_2 = f"<b>13.</b> El valor de los honorarios pactados fue pagado al contratista en mensualidades vencidas y proporcional al periodo en el cual se prestaron sus servicios profesionales, previa certificación de cumplimiento a satisfacción expedida por el SUPERVISOR del contrato, con cargo al registro presupuestal <b>No. {rp_val} del {fecha_rp_str}</b>."
        
        text_14 = f"<b>14.</b> El contratista cumplió con el pago de los aportes al sistema de seguridad social en salud, pensión y riesgos profesionales de acuerdo con los recibos soporte del pago de los aportes a seguridad social y parafiscales durante todo el plazo de ejecución del contrato."

        # Inventario
        linea1 = "No se tiene inventario a cargo."
        linea2 = ""
        linea3 = ""
        if tiene_inventario and desc_inventario:
            words = desc_inventario.split()
            lines = []
            curr_line = []
            curr_len = 0
            for w in words:
                if curr_len + len(w) + 1 > 70:
                    lines.append(" ".join(curr_line))
                    curr_line = [w]
                    curr_len = len(w)
                else:
                    curr_line.append(w)
                    curr_len += len(w) + 1
            if curr_line:
                lines.append(" ".join(curr_line))
            
            linea1 = lines[0] if len(lines) > 0 else ""
            linea2 = lines[1] if len(lines) > 1 else ""
            linea3 = lines[2] if len(lines) > 2 else ""

        t_inventario_row = Table(
            [
                [
                    Paragraph("<b>15. VERIFICACION Y ENTREGA DE INVENTARIO:</b>", s_lbl_contrato),
                    [Paragraph(linea1, s_val_center) if linea1 else Spacer(1, 1), Spacer(1, 3), DottedLine(10.39 * cm, 0.6, black)]
                ],
                [
                    [Paragraph(linea2, s_val_center) if linea2 else Spacer(1, 1), Spacer(1, 3), DottedLine(16.59 * cm, 0.6, black)],
                    ""
                ],
                [
                    [Paragraph(linea3, s_val_center) if linea3 else Spacer(1, 1), Spacer(1, 3), DottedLine(16.59 * cm, 0.6, black)],
                    ""
                ]
            ],
            colWidths=[6.2 * cm, 10.39 * cm],
            rowHeights=[0.6 * cm, 0.6 * cm, 0.6 * cm]
        )
        t_inventario_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("SPAN", (0, 1), (1, 1)),
            ("SPAN", (0, 2), (1, 2)),
        ]))

        narrativas_flowables = [
            Paragraph(text_12, s_narrative),
            Spacer(1, 0.25 * cm),
            Paragraph(text_13_1, s_narrative),
            Spacer(1, 0.25 * cm),
            Paragraph(text_13_2, s_narrative),
            Spacer(1, 0.25 * cm),
            Paragraph(text_14, s_narrative),
            Spacer(1, 0.25 * cm),
            t_inventario_row,
            Spacer(1, 0.45 * cm),
            Paragraph("<b>16. BALANCE FINANCIERO:</b>", s_lbl_contrato)
        ]
        
        t_wrapper_narrativas = Table(
            [["", narrativas_flowables, ""]],
            colWidths=[1.5 * cm, 16.59 * cm, 1.5 * cm]
        )
        t_wrapper_narrativas.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # --- Sección 16: BALANCE FINANCIERO ---
        tipo_contrato_str = "CONTRATO DE PRESTACIÓN DE SERVICIOS"
        if contrato_vig and contrato_vig.get("tipo"):
            tipo_contrato_str = f"CONTRATO DE {contrato_vig.get('tipo').replace('_', ' ').upper()}"
        desc_text = f"{tipo_contrato_str}<br/>No. {no_contrato} de {anio_fin}"

        # Col 1: Valor Contratado (Valor del contrato + adición si existe)
        valor_inicial_int = contrato_vig.get("valor") or 0
        valor_adicion_int = adiciones.get("valor_adicion") or 0 if tiene_adiciones else 0
        valor_total_int = valor_inicial_int + valor_adicion_int
        
        try:
            valor_total_str = f"{valor_total_int:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            valor_total_str = "0,00"

        # Col 2: Valor Ejecutado
        valor_ejecutado_int = contrato_vig.get("valor_total_ejecutado_contrato") or 0
        try:
            valor_ejecutado_str = f"{valor_ejecutado_int:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            valor_ejecutado_str = "0,00"

        # Col 3: Saldo Presupuestal a liberar
        saldo_liberar_int = contrato_vig.get("saldo_presp_lib_contrato") or 0
        try:
            saldo_liberar_str = f"{saldo_liberar_int:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            saldo_liberar_str = "0,00"

        s_desc_style = ParagraphStyle(
            "desc_style", parent=estilos["Normal"],
            fontSize=6.0, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=8.0, textColor=NEGRO
        )

        s_balance_val_left = ParagraphStyle(
            "balance_val_left", parent=estilos["Normal"],
            fontSize=6.0, fontName="Helvetica-Bold", alignment=TA_LEFT, leading=8.0, textColor=NEGRO
        )

        s_balance_val_right = ParagraphStyle(
            "balance_val_right", parent=estilos["Normal"],
            fontSize=6.0, fontName="Helvetica", alignment=TA_RIGHT, leading=8.0, textColor=NEGRO
        )

        t_val_contratado = Table(
            [[Paragraph("<b>$</b>", s_balance_val_left), Paragraph(valor_total_str, s_balance_val_right)]],
            colWidths=[0.5 * cm, 2.3 * cm],
            rowHeights=[0.45 * cm]
        )
        t_val_contratado.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        t_val_ejecutado = Table(
            [[Paragraph("<b>$</b>", s_balance_val_left), Paragraph(valor_ejecutado_str, s_balance_val_right)]],
            colWidths=[0.5 * cm, 2.3 * cm],
            rowHeights=[0.45 * cm]
        )
        t_val_ejecutado.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        t_val_saldo = Table(
            [[Paragraph("<b>$</b>", s_balance_val_left), Paragraph(saldo_liberar_str, s_balance_val_right)]],
            colWidths=[0.5 * cm, 2.3 * cm],
            rowHeights=[0.45 * cm]
        )
        t_val_saldo.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        s_balance_header = ParagraphStyle(
            "balance_header", parent=estilos["Normal"],
            fontSize=6.0, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=8.0, textColor=NEGRO
        )

        AZUL_CABECERA_LIGHT = HexColor("#8DB4E2")

        t_balance_tabla = Table(
            [
                [
                    Paragraph("DESCRIPCIÓN", s_balance_header),
                    Paragraph("VALOR CONTRATADO", s_balance_header),
                    Paragraph("VALOR EJECUTADO", s_balance_header),
                    Paragraph("SALDO NO EJECUTADO", s_balance_header)
                ],
                [
                    Paragraph(desc_text, s_desc_style),
                    t_val_contratado,
                    t_val_ejecutado,
                    t_val_saldo
                ]
            ],
            colWidths=[5.59 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm],
            rowHeights=[0.45 * cm, 0.95 * cm]
        )
        t_balance_tabla.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 1.0, NEGRO),
            ("BACKGROUND", (0, 0), (-1, 0), AZUL_CABECERA_LIGHT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))

        t_wrapper_balance = Table(
            [["", t_balance_tabla, ""]],
            colWidths=[2.0 * cm, 14.59 * cm, 0.0 * cm]
        )
        t_wrapper_balance.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # --- Firma de constancia final ---
        mes_fin_lower = mes_fin.lower() if mes_fin else "—"
        text_constancia = f"Para constancia de lo anterior, firman la presente acta los que en ella intervinieron a los <b>{dia_fin}</b> días del mes de <b>{mes_fin_lower}</b> de <b>{anio_fin}</b>."
        p_constancia = Paragraph(text_constancia, s_narrative)

        t_wrapper_constancia = Table(
            [["", p_constancia, ""]],
            colWidths=[1.5 * cm, 16.59 * cm, 1.5 * cm]
        )
        t_wrapper_constancia.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # --- Bloque de Firmas ---
        from app.services.firma_service import FirmaService
        firma_contratista_bytes = FirmaService().obtener_imagen(usuario_id)
        firma_contratista_img = ""
        if firma_contratista_bytes:
            firma_contratista_img = Image(io.BytesIO(firma_contratista_bytes), width=4.0 * cm, height=1.2 * cm, kind="proportional")

        # Buscar nombres e IDs de Financiera, Abogado y Jefe
        config_firmantes = self.obtener_firmantes_config("firmantes_formatos_actas", TIPOS_FIRMA_ACTAS)
        
        # Financiera
        firma_fin_doc = certificacion.get("firmas", {}).get("financiera")
        fin_nombre = "sin nombre_financiera"
        fin_id_str = None
        if firma_fin_doc:
            fin_nombre = firma_fin_doc.get("firmante_nombre", fin_nombre)
            fin_id_str = str(firma_fin_doc.get("firmante_id", ""))
        else:
            fin_config = config_firmantes.get("financiera") or {}
            fin_nombre = fin_config.get("nombre", fin_nombre)
            fin_id_str = fin_config.get("usuario_id")

        # Abogado
        firma_abog_doc = certificacion.get("firmas", {}).get("abogado")
        abog_nombre = "sin nombre_abogado"
        abog_id_str = None
        if firma_abog_doc:
            abog_nombre = firma_abog_doc.get("firmante_nombre", abog_nombre)
            abog_id_str = str(firma_abog_doc.get("firmante_id", ""))
        else:
            abog_config = config_firmantes.get("abogado") or {}
            abog_nombre = abog_config.get("nombre", abog_nombre)
            abog_id_str = abog_config.get("usuario_id")

        # Jefe (Supervisor)
        firma_jefe_doc = certificacion.get("firmas", {}).get("jefe")
        jefe_nombre = "GLADYS GUTIÉRREZ BUITRAGO"
        jefe_id_str = None
        if firma_jefe_doc:
            jefe_nombre = firma_jefe_doc.get("firmante_nombre", jefe_nombre)
            jefe_id_str = str(firma_jefe_doc.get("firmante_id", ""))
        else:
            jefe_config = config_firmantes.get("jefe") or {}
            jefe_nombre = jefe_config.get("nombre", jefe_nombre)
            jefe_id_str = jefe_config.get("usuario_id")

        # Cargar firma del Jefe
        jefe_firma_img = None
        if jefe_id_str:
            jefe_firma_bytes = FirmaService().obtener_imagen(jefe_id_str)
            if jefe_firma_bytes:
                jefe_firma_img = Image(io.BytesIO(jefe_firma_bytes), width=4.0 * cm, height=1.2 * cm, kind="proportional")

        # Fallback a Gladys si no hay firma registrada y es su nombre
        if not jefe_firma_img and jefe_nombre.upper() in ["GLADYS GUTIERREZ BUITRAGO", "GLADYS GUTIÉRREZ BUITRAGO"]:
            firma_gladys_path = os.path.join("app", "assets", "firma_gla.png")
            if os.path.exists(firma_gladys_path):
                jefe_firma_img = Image(firma_gladys_path, width=4.0 * cm, height=1.2 * cm, kind="proportional")

        s_firma_side_lbl = ParagraphStyle(
            "firma_side_lbl", parent=estilos["Normal"],
            fontSize=6.5, fontName="Helvetica", alignment=TA_LEFT, leading=8.0, textColor=NEGRO
        )
        s_firma_name = ParagraphStyle(
            "firma_name", parent=estilos["Normal"],
            fontSize=7.0, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=9.0, textColor=NEGRO
        )
        s_firma_role = ParagraphStyle(
            "firma_role", parent=estilos["Normal"],
            fontSize=6.5, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=8.0, textColor=NEGRO
        )

        nombre_contratista_caps = nombre_contratista.upper() if nombre_contratista else "—"

        col_contratista = [
            firma_contratista_img if firma_contratista_img else Spacer(1, 1.2 * cm),
            Paragraph(nombre_contratista_caps, s_firma_name),
            Paragraph("CONTRATISTA", s_firma_role)
        ]

        col_supervisor = [
            Spacer(1, 1.2 * cm),
            Paragraph(jefe_nombre.upper(), s_firma_name),
            Paragraph("SUPERVISOR DEL CONTRATO", s_firma_role)
        ]

        card_contratista = Table(
            [
                [Paragraph("Firma", s_firma_side_lbl), col_contratista[0]],
                [Paragraph("Nombre", s_firma_side_lbl), col_contratista[1]],
                ["", col_contratista[2]]
            ],
            colWidths=[1.2 * cm, 5.8 * cm],
            rowHeights=[1.3 * cm, 0.4 * cm, 0.4 * cm]
        )
        card_contratista.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("LINEABOVE", (1, 1), (1, 1), 1.0, NEGRO),
        ]))

        card_supervisor = Table(
            [
                [Paragraph("Firma", s_firma_side_lbl), col_supervisor[0]],
                [Paragraph("Nombre", s_firma_side_lbl), col_supervisor[1]],
                ["", col_supervisor[2]]
            ],
            colWidths=[1.2 * cm, 5.8 * cm],
            rowHeights=[1.3 * cm, 0.4 * cm, 0.4 * cm]
        )
        card_supervisor.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("LINEABOVE", (1, 1), (1, 1), 1.0, NEGRO),
        ]))

        t_firmas = Table(
            [[card_contratista, "", card_supervisor]],
            colWidths=[7.0 * cm, 2.59 * cm, 7.0 * cm]
        )
        t_firmas.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        t_wrapper_firmas = Table(
            [["", t_firmas, ""]],
            colWidths=[1.5 * cm, 16.59 * cm, 1.5 * cm]
        )
        t_wrapper_firmas.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # --- Metadata (Elaboró/Revisó/Anexo) ---
        s_metadata_text = ParagraphStyle(
            "metadata_text", parent=estilos["Normal"],
            fontSize=6.5, fontName="Helvetica", alignment=TA_LEFT,
            leading=8.0, textColor=NEGRO
        )

        # Cargar firmas pequeñas para Financiera y Abogado
        firma_fin_img = ""
        if fin_id_str and firma_fin_doc:
            fin_bytes = FirmaService().obtener_imagen(fin_id_str)
            if fin_bytes:
                firma_fin_img = Image(io.BytesIO(fin_bytes), width=1.4 * cm, height=0.4 * cm, kind="proportional")

        firma_abog_img = ""
        if abog_id_str and firma_abog_doc:
            abog_bytes = FirmaService().obtener_imagen(abog_id_str)
            if abog_bytes:
                firma_abog_img = Image(io.BytesIO(abog_bytes), width=1.4 * cm, height=0.4 * cm, kind="proportional")

        p_meta_elaboro = Paragraph(f"<b>Elaboró:</b> {nombre_contratista}", s_metadata_text)
        
        # Tablas anidadas para alinear firmas pequeñas al frente de los nombres (estrechas)
        t_reviso1 = Table(
            [[Paragraph(f"<b>Revisó:</b> {fin_nombre}", s_metadata_text), firma_fin_img]],
            colWidths=[6.0 * cm, 2.0 * cm]
        )
        t_reviso1.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        t_reviso2 = Table(
            [[Paragraph(f"<b>Revisó:</b> {abog_nombre}", s_metadata_text), firma_abog_img]],
            colWidths=[6.0 * cm, 2.0 * cm]
        )
        t_reviso2.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        p_meta_acta = Paragraph(f"<b>Acta de Entrega y Recibo del Contrato No</b> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {no_contrato} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Un (1) Folio", s_metadata_text)

        t_wrapper_metadata = Table(
            [
                ["", p_meta_elaboro, ""],
                ["", t_reviso1, ""],
                ["", t_reviso2, ""],
                ["", p_meta_acta, ""]
            ],
            colWidths=[0.15 * cm, 17.94 * cm, 1.5 * cm]
        )
        t_wrapper_metadata.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))

        # Contenedor principal con todos los datos, narrativas, balance, constancia, firmas y metadata alineados
        t_cuerpo = Table(
            [
                [t_wrapper_datos, "", ""],             # Contrato y sus datos
                ["", "", ""],                          # Espacio intermedio
                [t_wrapper_narrativas, "", ""],        # Secciones narrativas 12-16
                ["", "", ""],                          # Espacio intermedio
                [t_wrapper_balance, "", ""],           # Tabla Balance Financiero (Centrada)
                ["", "", ""],                          # Espacio intermedio
                [t_wrapper_constancia, "", ""],        # Firma de constancia final
                ["", "", ""],                          # Espacio intermedio
                [t_wrapper_firmas, "", ""],            # Bloque de Firmas
                ["", "", ""],                          # Espacio intermedio
                [t_wrapper_metadata, "", ""],          # Metadata (Elaboró/Revisó/Anexo)
                ["", "", ""]                           # Espacio final de cierre
            ],
            colWidths=[1.0 * cm, 5.0 * cm, 13.59 * cm],
            rowHeights=[None, 0.4 * cm, None, 0.4 * cm, None, 0.4 * cm, None, 0.4 * cm, None, 0.4 * cm, None, 0.4 * cm]
        )
        t_cuerpo.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBEFORE", (0, 0), (0, -1), 0.7, NEGRO),
            ("LINEAFTER", (2, 0), (2, -1), 0.7, NEGRO),
            ("LINEBELOW", (0, -1), (-1, -1), 0.7, NEGRO),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            
            # SPAN para las filas completas
            ("SPAN", (0, 0), (2, 0)),
            ("SPAN", (0, 2), (2, 2)),
            ("SPAN", (0, 4), (2, 4)),
            ("SPAN", (0, 6), (2, 6)),
            ("SPAN", (0, 8), (2, 8)),
            ("SPAN", (0, 10), (2, 10)),
        ]))
        story.append(t_cuerpo)

        # Calcular altura dinámica de la página para que se adapte exactamente a 1 hoja
        ancho_util = custom_width - 4.0 * cm  # Margen izquierdo y derecho de 2cm cada uno
        altura_total = 0
        for elemento in story:
            _, h_el = elemento.wrap(ancho_util, 100000)
            altura_total += h_el
            
        custom_height = altura_total + 4.0 * cm + 0.5 * cm
        custom_pagesize = (custom_width, custom_height)
        
        doc = SimpleDocTemplate(
            buf,
            pagesize=custom_pagesize,
            leftMargin=2.0 * cm,
            rightMargin=2.0 * cm,
            topMargin=2.0 * cm,
            bottomMargin=2.0 * cm,
        )

        def draw_page_number(canvas, doc_obj):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(NEGRO)
            w, h = doc_obj.pagesize
            canvas.drawCentredString(w / 2.0, 0.8 * cm, "1")
            canvas.drawRightString(w - 2.0 * cm, 0.8 * cm, "1")
            canvas.restoreState()

        doc.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)
        buf.seek(0)
        return buf.getvalue()




     