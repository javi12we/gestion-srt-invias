import re
from datetime import datetime, timedelta, timezone

import pytz

from app.core.autorizacion import ValidacionAutorizacion, validar_permiso
from app.core.balance_contrato import calcular_balance_pagos
from app.core.catalogos import PERMISOS_SUIT_CARGUE
from app.core.seguridad import generar_hash_password
from app.config import configuracion
from app.repositories.usuario_repo import UsuarioRepositorio
from app.services.auditoria_service import AuditoriaService

_CLAVES_SUIT_CARGUE = {p["clave"] for p in PERMISOS_SUIT_CARGUE}

_ZONA_BOGOTA = pytz.timezone("America/Bogota")

# ── Requisitos para descargar "Formatos de contrato" ──────────────────────────
# Conjuntos de campos que deben estar diligenciados para habilitar la descarga
# de formatos de contrato. (clave, etiqueta visible para el usuario)
_CAMPOS_PERSONALES = [
    ("nombre_completo", "Nombre completo"),
    ("tipo_documento", "Tipo de documento"),
    ("numero_documento", "Número de documento"),
    ("lugar_expedicion_documento", "Lugar de expedición del documento"),
    ("email", "Correo electrónico"),
]
_CAMPOS_CONTRATO = [
    ("numero", "Número de contrato"),
    ("tipo", "Tipo de contrato"),
    ("objeto", "Objeto del contrato"),
    ("valor", "Valor del contrato"),
    ("valor_mensual", "Valor mensual"),
    ("rp_compromiso_presupuestal", "RP / compromiso presupuestal"),
    ("fecha_recurso_presupuestal", "Fecha recurso presupuestal"),
    ("fecha_inicio", "Fecha de inicio"),
    ("fecha_fin", "Fecha de finalización"),
]
# Afiliaciones de seguridad social requeridas (CCF queda excluida por ser opcional).
_AFILIACIONES_REQUERIDAS = [
    ("eps", "EPS"),
    ("arl", "ARL"),
    ("afp", "Fondo de pensiones (AFP)"),
]

# Días de gracia tras la fecha de fin del contrato (o su prórroga) durante los
# cuales el contratista sigue pudiendo descargar/generar formatos.
DIAS_GRACIA_DESCARGA_FORMATOS = 60

MSG_NUMERO_CONTRATO_INVALIDO = "Número de contrato (debe ser estrictamente numérico, ej: 3123123)"


class UsuarioService:
    def __init__(self) -> None:
        self.repositorio = UsuarioRepositorio()
        self.auditoria = AuditoriaService()

    @staticmethod
    def _normalizar_numero_documento(numero: str) -> str:
        numero = numero.strip()
        if not re.fullmatch(r"[0-9]+", numero):
            raise ValueError(
                "El número de documento solo puede contener números, sin letras, espacios, puntos ni símbolos."
            )
        return numero

    @staticmethod
    def _contrato_finalizado(contrato, dias_gracia: int = 0) -> bool:
        """``dias_gracia`` permite seguir considerando el contrato como no finalizado
        durante N días después de su fecha de fin (o de la prórroga), para dar margen
        a trámites posteriores al cierre del contrato (p. ej. descarga de formatos)."""
        if not contrato:
            return False
        fecha_fin = contrato.get("fecha_fin")

        # Considerar prórroga si existe para la fecha de fin efectiva
        prorroga = contrato.get("prorrogra_contrato") or {}
        if prorroga.get("tiene_prorroga") and prorroga.get("fecha_prorrogra"):
            fecha_fin = prorroga.get("fecha_prorrogra")

        if not fecha_fin:
            return False
        hoy = datetime.now(_ZONA_BOGOTA).date()
        if fecha_fin.tzinfo is None:
            fecha_fin = fecha_fin.replace(tzinfo=timezone.utc)
        fecha_limite = fecha_fin.astimezone(_ZONA_BOGOTA).date()
        if dias_gracia:
            fecha_limite += timedelta(days=dias_gracia)
        return fecha_limite < hoy

    @staticmethod
    def _afiliacion(datos) -> dict:
        """Normaliza una afiliación {entidad, paga, valor, valor_primer_mes,
        valor_ultimo_mes, radicado}; campos vacíos → None.

        'paga' indica quién cubre el aporte: si lo paga el contratista se conservan
        los tres valores mensuales ('valor_primer_mes' para el primer mes del
        contrato, 'valor' para los meses intermedios y 'valor_ultimo_mes' para el
        último mes); si lo paga la entidad se conserva el 'radicado'. Se descarta el
        dato que no corresponde a la opción elegida para evitar inconsistencias.
        """
        datos = datos or {}
        entidad = (datos.get("entidad") or "").strip() or None
        paga = (datos.get("paga") or "").strip() or None
        if paga not in ("contratista", "entidad"):
            paga = None

        def _valor(clave):
            valor = datos.get(clave)
            return int(valor) if valor not in (None, "", 0) and int(valor) > 0 else None

        valor = _valor("valor")
        valor_primer_mes = _valor("valor_primer_mes")
        valor_ultimo_mes = _valor("valor_ultimo_mes")
        radicado = (datos.get("radicado") or "").strip() or None
        if paga == "entidad":
            valor = valor_primer_mes = valor_ultimo_mes = None
        elif paga == "contratista":
            radicado = None
        return {
            "entidad": entidad,
            "paga": paga,
            "valor": valor,
            "valor_primer_mes": valor_primer_mes,
            "valor_ultimo_mes": valor_ultimo_mes,
            "radicado": radicado,
        }

    @staticmethod
    def _construir_informacion_laboral(datos) -> dict:
        """Sanea el bloque de información laboral proveniente del formulario.

        Mantiene la forma estable del sub-documento; los campos sin valor quedan
        en None y los dependientes sin nombre se descartan.
        """
        datos = datos or {}
        ss = datos.get("seguridad_social") or {}
        bancaria = datos.get("bancaria") or {}
        tributaria = datos.get("tributaria") or {}

        dependientes = []
        for dep in datos.get("dependientes") or []:
            nombre = (dep.get("nombre") or "").strip()
            if not nombre:
                continue
            ndoc = (dep.get("numero_documento") or "").strip()
            if ndoc and not re.fullmatch(r"[0-9]+", ndoc):
                raise ValueError(
                    "El número de documento del dependiente solo puede contener números, sin letras, espacios, puntos ni símbolos."
                )
            dependientes.append({
                "nombre": nombre,
                "tipo_documento": (dep.get("tipo_documento") or "").strip().upper() or None,
                "numero_documento": ndoc or None,
                "tipo": (dep.get("tipo") or "").strip() or None,
            })

        ibc_ps = datos.get("ibc_prestaciones_sociales")
        if ibc_ps is not None:
            try:
                ibc_ps = int(ibc_ps)
            except (ValueError, TypeError):
                ibc_ps = None
        else:
            ibc_ps = None

        paga_iva = bool(datos.get("paga_iva"))
        valor_iva = datos.get("valor_iva")
        if paga_iva and valor_iva is not None:
            try:
                valor_iva = int(valor_iva)
            except (ValueError, TypeError):
                valor_iva = None
        else:
            valor_iva = None

        return {
            "es_pensionado": bool(datos.get("es_pensionado")),
            "planilla_mes_vencido": bool(datos.get("planilla_mes_vencido")),
            "grupo_trabajo": (datos.get("grupo_trabajo") or "").strip() or None,
            "ibc_prestaciones_sociales": ibc_ps if ibc_ps and ibc_ps > 0 else None,
            "paga_iva": paga_iva,
            "valor_iva": valor_iva if paga_iva else None,
            "seguridad_social": {
                "eps": UsuarioService._afiliacion(ss.get("eps")),
                "arl": UsuarioService._afiliacion(ss.get("arl")),
                "afp": UsuarioService._afiliacion(ss.get("afp")),
                "ccf": UsuarioService._afiliacion(ss.get("ccf")),
            },
            "bancaria": {
                "banco": (bancaria.get("banco") or "").strip() or None,
                "numero_cuenta": (bancaria.get("numero_cuenta") or "").strip() or None,
                "tipo_cuenta": (bancaria.get("tipo_cuenta") or "").strip() or None,
            },
            "tributaria": {
                "rut": (tributaria.get("rut") or "").strip() or None,
                "declarante_renta": bool(tributaria.get("declarante_renta")),
                "regimen": (tributaria.get("regimen") or "").strip() or None,
            },
            "dependientes": dependientes,
        }

    @staticmethod
    def _fecha_a_datetime(d):
        if d is None:
            return None
        if isinstance(d, datetime):
            return d if d.tzinfo is not None else d.replace(tzinfo=timezone.utc)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

    def obtener_usuario(self, id_usuario: str):
        return self.repositorio.buscar_por_id(id_usuario)

    def listar_usuarios(self):
        return self.repositorio.listar()

    def listar_usuarios_grupo_trabajo(self, grupo: str):
        return self.repositorio.listar_por_grupo_trabajo(grupo)

    def actualizar_permisos_suit_usuario(self, id_usuario: str, claves_seleccionadas: list, actor: str) -> None:
        """Asigna/quita los permisos de cargue SUIT de un usuario, sin tocar el resto de sus permisos_extra."""
        usuario = self.repositorio.buscar_por_id(id_usuario)
        if not usuario:
            raise ValueError("El usuario no existe")

        permisos_extra = set(usuario.get("permisos_extra", [])) - _CLAVES_SUIT_CARGUE
        permisos_extra |= (set(claves_seleccionadas) & _CLAVES_SUIT_CARGUE)
        self.repositorio.actualizar(id_usuario, {"permisos_extra": sorted(permisos_extra)})

        self.auditoria.registrar_accion(
            actor,
            "editar_permisos_suit",
            "usuario",
            {"usuario_id": id_usuario, "permisos_suit": sorted(set(claves_seleccionadas) & _CLAVES_SUIT_CARGUE)},
        )

    def crear_usuario(self, datos: dict, validar_permisos: bool = True, permisos_usuario: list = None):
        usuario_existente = self.repositorio.buscar_por_usuario(datos["usuario"])
        if usuario_existente:
            raise ValueError("Ya existe un usuario con ese nombre de acceso")

        if validar_permisos and permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "usuario.crear")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))

        datos = datos.copy()

        numero_doc = datos.get("numero_documento", "").strip()
        if numero_doc:
            datos["numero_documento"] = self._normalizar_numero_documento(numero_doc)
            existente = self.repositorio.buscar_por_numero_documento(datos["numero_documento"])
            if existente:
                raise ValueError("Ya existe un usuario con ese número de documento")
        else:
            datos.pop("numero_documento", None)

        if datos.get("tipo_documento"):
            datos["tipo_documento"] = datos["tipo_documento"].strip().upper()
        else:
            datos.pop("tipo_documento", None)

        lugar = (datos.get("lugar_expedicion_documento") or "").strip()
        if lugar:
            datos["lugar_expedicion_documento"] = lugar
        else:
            datos.pop("lugar_expedicion_documento", None)

        if "informacion_laboral" in datos:
            datos["informacion_laboral"] = self._construir_informacion_laboral(datos.get("informacion_laboral"))

        datos["password_hash"] = generar_hash_password(datos.pop("password"))
        datos.setdefault("activo", True)
        datos.setdefault("roles", [])
        datos.setdefault("permisos_extra", [])
        id_nuevo = self.repositorio.crear(datos)
        
        self.auditoria.registrar_accion(
            datos.get("creado_por", "sistema"),
            "crear",
            "usuario",
            {"usuario_creado": datos["usuario"]},
        )
        return id_nuevo

    def actualizar_usuario(self, id_usuario: str, datos: dict, validar_permisos: bool = True, permisos_usuario: list = None):
        datos = datos.copy()
        usuario_actual = self.repositorio.buscar_por_id(id_usuario)
        if not usuario_actual:
            raise ValueError("El usuario no existe")

        if validar_permisos and permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "usuario.editar")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))

        nuevo_usuario = datos.get("usuario")
        if nuevo_usuario:
            usuario_existente = self.repositorio.buscar_por_usuario(nuevo_usuario)
            if usuario_existente and str(usuario_existente["_id"]) != id_usuario:
                raise ValueError("Ya existe un usuario con ese nombre de acceso")

        numero_doc = datos.get("numero_documento", "").strip()
        if numero_doc:
            datos["numero_documento"] = self._normalizar_numero_documento(numero_doc)
            existente = self.repositorio.buscar_por_numero_documento(datos["numero_documento"])
            if existente and str(existente["_id"]) != id_usuario:
                raise ValueError("Ya existe un usuario con ese número de documento")
        else:
            datos.pop("numero_documento", None)

        if datos.get("tipo_documento"):
            datos["tipo_documento"] = datos["tipo_documento"].strip().upper()
        else:
            datos.pop("tipo_documento", None)

        if "lugar_expedicion_documento" in datos:
            datos["lugar_expedicion_documento"] = (datos.get("lugar_expedicion_documento") or "").strip() or None

        if "informacion_laboral" in datos:
            datos["informacion_laboral"] = self._construir_informacion_laboral(datos.get("informacion_laboral"))

        if datos.get("password"):
            datos["password_hash"] = generar_hash_password(datos.pop("password"))
        else:
            datos.pop("password", None)

        datos.pop("contrato", None)
        datos.pop("contratos", None)

        resultado = self.repositorio.actualizar(id_usuario, datos)

        self.auditoria.registrar_accion(
            datos.get("actualizado_por", "sistema"),
            "editar",
            "usuario",
            {"usuario_editado": usuario_actual["usuario"]},
        )
        return resultado

    @staticmethod
    def texto_orden_inicio(valor) -> str:
        """'Radicado/ Fecha de orden de inicio Contrato' como texto libre. Los
        contratos guardados cuando el campo era solo fecha se muestran dd/mm/aaaa."""
        if not valor:
            return ""
        if hasattr(valor, "strftime"):
            return valor.strftime("%d/%m/%Y")
        return str(valor).strip()

    @staticmethod
    def _construir_contrato(numero: str, datos: dict) -> dict:
        contrato: dict = {"numero": numero}
        if datos.get("tipo"):
            contrato["tipo"] = datos["tipo"]
        objeto = (datos.get("objeto") or "").strip()
        if objeto:
            contrato["objeto"] = objeto
        orden_inicio = UsuarioService.texto_orden_inicio(datos.get("fecha_orden_inicio_contrato"))
        if orden_inicio:
            contrato["fecha_orden_inicio_contrato"] = orden_inicio
        valor = datos.get("valor")
        if valor is not None and valor > 0:
            contrato["valor"] = int(valor)
        rp = (datos.get("rp_compromiso_presupuestal") or "").strip()
        if rp:
            contrato["rp_compromiso_presupuestal"] = rp
        fecha_inicio = datos.get("fecha_inicio")
        if fecha_inicio:
            contrato["fecha_inicio"] = UsuarioService._fecha_a_datetime(fecha_inicio)
        fecha_fin = datos.get("fecha_fin")
        if fecha_fin:
            contrato["fecha_fin"] = UsuarioService._fecha_a_datetime(fecha_fin)
        fecha_rp = datos.get("fecha_recurso_presupuestal")
        if fecha_rp:
            contrato["fecha_recurso_presupuestal"] = UsuarioService._fecha_a_datetime(fecha_rp)
        fecha_firma_secop = datos.get("firma_cps_secop")
        if fecha_firma_secop:
            contrato["firma_cps_secop"] = UsuarioService._fecha_a_datetime(fecha_firma_secop)
        valor_mensual = datos.get("valor_mensual")
        if valor_mensual is not None and valor_mensual > 0:
            contrato["valor_mensual"] = int(valor_mensual)
        
        valor_primer_pago = datos.get("valor_primer_pago")
        if valor_primer_pago is not None and valor_primer_pago > 0:
            contrato["valor_primer_pago"] = int(valor_primer_pago)
        else:
            contrato["valor_primer_pago"] = None

        # NUEVAS VARIABLES DE CONTRATO
        contrato["tiene_inventario"] = bool(datos.get("tiene_inventario"))
        contrato["desc_inventario"] = (datos.get("desc_inventario") or "").strip() or None
        
        # Prórroga
        prorroga = datos.get("prorrogra_contrato") or {}
        tiene_pror = bool(prorroga.get("tiene_prorroga"))
        f_pror = prorroga.get("fecha_prorrogra")
        
        if tiene_pror and f_pror and fecha_fin:
            dt_fin = UsuarioService._fecha_a_datetime(fecha_fin)
            dt_pror = UsuarioService._fecha_a_datetime(f_pror)
            if dt_pror <= dt_fin:
                raise ValueError("La fecha de la prórroga debe ser posterior a la fecha de fin del contrato.")

        contrato["prorrogra_contrato"] = {
            "tiene_prorroga": tiene_pror,
            "fecha_prorrogra": UsuarioService._fecha_a_datetime(f_pror) if tiene_pror and f_pror else None,
            "radicado_prorrogra": (prorroga.get("radicado_prorrogra") or "").strip() or None
        }

        # Adiciones
        adiciones = datos.get("adiciones_contrato") or {}
        tiene_adi = bool(adiciones.get("tiene_adiciones"))
        val_adi = adiciones.get("valor_adicion")
        contrato["adiciones_contrato"] = {
            "tiene_adiciones": tiene_adi,
            "valor_adicion": int(val_adi) if tiene_adi and val_adi is not None else None
        }

        # Arreglo de pagos (máximo 20)
        pagos_entrada = datos.get("pagos") or []
        pagos_procesados = []
        for p in pagos_entrada[:20]:
            num_p = (p.get("numero_pago") or "").strip()
            if not num_p:
                continue
            
            f_pago = p.get("fecha_pago")
            pagos_procesados.append({
                "numero_pago": num_p,
                "fecha_pago": UsuarioService._fecha_a_datetime(f_pago),
                "valor_bruto_pago": int(p.get("valor_bruto_pago") or 0),
                "deducciones_pago": int(p.get("deducciones_pago") or 0),
                "valor_neto_pago": int(p.get("valor_neto_pago") or 0),
            })
        contrato["pagos"] = pagos_procesados

        # El balance no se digita: siempre se deriva de los pagos y del valor del
        # contrato, porque alimenta los formatos de Balance General CPS.
        (
            contrato["valor_total_pagado"],
            contrato["valor_total_por_pagar_contrato"],
        ) = calcular_balance_pagos(datos.get("valor"), pagos_procesados)

        # Personalizar última cuenta
        contrato["personalizar_ultimacuenta"] = bool(datos.get("personalizar_ultimacuenta"))
        val_personalizar = datos.get("valor_personalizar_ultimacuenta")
        contrato["valor_personalizar_ultimacuenta"] = int(val_personalizar) if contrato["personalizar_ultimacuenta"] and val_personalizar is not None else None

        return contrato

    def agregar_contrato(self, id_usuario: str, datos_contrato: dict):
        usuario = self.repositorio.buscar_por_id(id_usuario)
        if not usuario:
            raise ValueError("El usuario no existe.")
        numero = (datos_contrato.get("numero") or "").strip()
        if not numero:
            raise ValueError("El número de contrato es obligatorio.")
        if not self.numero_contrato_valido(numero):
            raise ValueError(MSG_NUMERO_CONTRATO_INVALIDO)
        existente = self.repositorio.buscar_por_numero_contrato(numero)
        if existente:
            raise ValueError("Ya existe un empleado registrado con ese número de contrato.")
        contratos_actuales = usuario.get("contratos") or []
        if any(c.get("numero") == numero for c in contratos_actuales):
            raise ValueError("Este usuario ya tiene registrado ese número de contrato.")
        contrato = self._construir_contrato(numero, datos_contrato)
        self.repositorio.agregar_contrato_a_usuario(id_usuario, contrato)

    def editar_contrato(self, id_usuario: str, numero_contrato: str, datos_contrato: dict):
        usuario = self.repositorio.buscar_por_id(id_usuario)
        if not usuario:
            raise ValueError("El usuario no existe.")
        contratos = usuario.get("contratos") or []
        contrato_actual = next((c for c in contratos if c.get("numero") == numero_contrato), None)
        if not contrato_actual:
            raise ValueError("Contrato no encontrado.")
        if self._contrato_finalizado(contrato_actual, dias_gracia=DIAS_GRACIA_DESCARGA_FORMATOS):
            raise ValueError(
                f"El contrato finalizó hace más de {DIAS_GRACIA_DESCARGA_FORMATOS} días y ya no puede ser modificado."
            )
        nuevo_numero = (datos_contrato.get("numero") or "").strip()
        if not nuevo_numero:
            raise ValueError("El número de contrato es obligatorio.")
        if not self.numero_contrato_valido(nuevo_numero):
            raise ValueError(MSG_NUMERO_CONTRATO_INVALIDO)
        if nuevo_numero != numero_contrato:
            existente = self.repositorio.buscar_por_numero_contrato(nuevo_numero)
            if existente:
                raise ValueError("Ya existe un empleado con ese número de contrato.")
            if any(c.get("numero") == nuevo_numero for c in contratos if c.get("numero") != numero_contrato):
                raise ValueError("Este usuario ya tiene registrado ese número de contrato.")
        nuevo_contrato = self._construir_contrato(nuevo_numero, datos_contrato)
        self.repositorio.editar_contrato_en_usuario(id_usuario, numero_contrato, nuevo_contrato)

    # ──────────────────────────────────────────────────────────────
    # Validación de completitud para descargar formatos de contrato
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _vacio(valor) -> bool:
        """True si el valor cuenta como 'no diligenciado' (None, vacío o cero)."""
        if valor is None:
            return True
        if isinstance(valor, str):
            return not valor.strip()
        if isinstance(valor, (int, float)):
            return valor == 0
        return False

    @staticmethod
    def numero_contrato_valido(numero) -> bool:
        """El número de contrato debe ser únicamente dígitos (sin espacios internos,
        letras, años, guiones ni otros símbolos). Rechaza registros históricos como
        '0192 2026'."""
        return bool(re.fullmatch(r"[0-9]+", str(numero if numero is not None else "").strip()))

    @classmethod
    def _faltantes_numero_contrato_periodo(cls, usuario: dict, año, mes) -> list:
        """Faltantes de formato en el número del contrato relevante para (año, mes),
        sin importar si otros contratos del usuario están completos. Vacío si el número
        es válido o si no hay contrato relevante (eso lo reportan otras validaciones)."""
        if año is None or mes is None:
            return []
        from app.services.certificacion_service import CertificacionService
        contrato = CertificacionService()._contrato_relevante(usuario.get("contratos") or [], año, mes)
        numero = (contrato or {}).get("numero")
        if cls._vacio(numero) or cls.numero_contrato_valido(numero):
            return []
        return [
            f"El número registrado «{str(numero).strip()}» no es válido: debe contener solo "
            "dígitos, sin espacios, letras, años ni guiones (ej: 3123123)"
        ]

    def validar_numero_contrato_periodo(self, id_usuario: str, año: int, mes: int) -> dict:
        """Valida el número del contrato relevante del período (año, mes).

        Retorna {"valido": bool, "faltantes": [str]}
        """
        usuario = self.repositorio.buscar_por_id(id_usuario) or {}
        faltantes = self._faltantes_numero_contrato_periodo(usuario, año, mes)
        return {"valido": not faltantes, "faltantes": faltantes}

    @classmethod
    def _contrato_campos_faltantes(cls, contrato: dict) -> list:
        """Etiquetas de los campos del contrato que faltan por diligenciar o no son válidos."""
        faltantes = []
        for clave, etiqueta in _CAMPOS_CONTRATO:
            val = contrato.get(clave)
            if cls._vacio(val):
                faltantes.append(etiqueta)
            elif clave == "numero":
                if not cls.numero_contrato_valido(val):
                    faltantes.append(MSG_NUMERO_CONTRATO_INVALIDO)
        # Validar Valor primer pago
        es_requerido = True
        fecha_inicio = contrato.get("fecha_inicio")
        if fecha_inicio:
            from datetime import datetime
            from app.core.zona_horaria import ZONA_BOGOTA, utc_a_bogota
            ahora = datetime.now(ZONA_BOGOTA)
            fi_bog = utc_a_bogota(fecha_inicio) if fecha_inicio.tzinfo else ZONA_BOGOTA.localize(fecha_inicio)
            
            ref_fin = ahora
            fecha_fin = contrato.get("fecha_fin")
            if fecha_fin:
                ff_bog = utc_a_bogota(fecha_fin) if fecha_fin.tzinfo else ZONA_BOGOTA.localize(fecha_fin)
                if ff_bog < ahora:
                    ref_fin = ff_bog
            
            dias_transcurridos = (ref_fin - fi_bog).days
            if dias_transcurridos >= 60:  # 2 meses
                es_requerido = False
                
        if es_requerido and cls._vacio(contrato.get("valor_primer_pago")):
            faltantes.append("Valor primer pago")

        return faltantes

    @staticmethod
    def _campos_seguridad_social_periodo(usuario: dict, año, mes) -> list:
        """Campos adicionales de seguridad social exigidos para el período (año, mes).

        Si (año, mes) coincide con el primer mes del contrato vigente en ese
        período (según su fecha de inicio), exige también 'valor_primer_mes'
        (usado por el formato de Retención en la Fuente - Primera Cuenta). Si
        coincide con el último mes (según su fecha de fin), exige
        'valor_ultimo_mes' (Retención en la Fuente - Segunda Cuenta ++, cuando
        corresponde a la cuenta final). Un contrato de un solo mes puede exigir
        ambos a la vez. Los meses intermedios no agregan nada aquí: ya se
        validan con 'valor' más abajo.
        """
        if año is None or mes is None:
            return []
        from app.services.certificacion_service import CertificacionService
        contrato = CertificacionService._contrato_para_periodo(usuario.get("contratos") or [], año, mes)
        if not contrato:
            return []
        fecha_inicio = contrato.get("fecha_inicio")
        fecha_fin = contrato.get("fecha_fin")
        campos = []
        if fecha_inicio and mes == fecha_inicio.month and año == fecha_inicio.year:
            campos.append(("valor_primer_mes", "primera cuenta"))
        if fecha_fin and mes == fecha_fin.month and año == fecha_fin.year:
            campos.append(("valor_ultimo_mes", "última cuenta"))
        return campos

    def faltantes_para_formatos(self, id_usuario: str, año: int = None, mes: int = None) -> dict:
        """Evalúa si el usuario tiene todos los datos necesarios para descargar
        formatos de contrato.

        Si se indican ``año``/``mes`` (el período seleccionado en "Formatos de
        contrato"), además exige el valor de seguridad social específico de ese
        período cuando coincide con el primer o el último mes del contrato
        vigente (ver ``_campos_seguridad_social_periodo``); sin período, se
        omite esa validación adicional (comportamiento previo).

        Devuelve ``{"puede_descargar": bool, "secciones": [...]}`` donde cada
        sección es ``{"titulo", "destino", "faltantes": [etiquetas]}`` y solo se
        incluyen las secciones con datos pendientes. ``puede_descargar`` es True
        cuando no hay ninguna sección con faltantes.
        """
        usuario = self.repositorio.buscar_por_id(id_usuario) or {}
        secciones = []

        # 1) Datos personales
        faltan_personales = [
            etiqueta for clave, etiqueta in _CAMPOS_PERSONALES if self._vacio(usuario.get(clave))
        ]
        if faltan_personales:
            secciones.append({
                "titulo": "Datos personales",
                "destino": "Mi perfil › 👤 Perfil",
                "faltantes": faltan_personales,
            })

        # 2) Al menos un contrato activo con todos sus datos completos
        contratos = usuario.get("contratos") or []
        activos = [
            c for c in contratos
            if not self._contrato_finalizado(c, dias_gracia=DIAS_GRACIA_DESCARGA_FORMATOS)
        ]
        if not activos:
            secciones.append({
                "titulo": "Contrato activo",
                "destino": "Mi perfil › 📄 Contratos",
                "faltantes": ["No tienes ningún contrato activo registrado"],
            })
        else:
            faltan_por_contrato = [(c, self._contrato_campos_faltantes(c)) for c in activos]
            if not any(not faltan for _, faltan in faltan_por_contrato):
                # Ningún contrato activo está completo: reportar el menos incompleto.
                contrato, faltan = min(faltan_por_contrato, key=lambda t: len(t[1]))
                numero = contrato.get("numero") or "—"
                secciones.append({
                    "titulo": f"Contrato activo {numero}",
                    "destino": "Mi perfil › 📄 Contratos",
                    "faltantes": faltan,
                })

        # 2b) Número del contrato del período: debe ser numérico aunque otro contrato
        # del usuario esté completo (registros históricos tipo "0192 2026").
        faltan_numero = self._faltantes_numero_contrato_periodo(usuario, año, mes)
        if faltan_numero:
            # Evitar reportar dos veces el mismo error desde la sección del paso 2.
            for sec in secciones:
                if sec["titulo"].startswith("Contrato activo"):
                    sec["faltantes"] = [f for f in sec["faltantes"] if f != MSG_NUMERO_CONTRATO_INVALIDO]
            secciones = [s for s in secciones if s["faltantes"]]
            secciones.append({
                "titulo": "Número de contrato incorrecto",
                "destino": "Mi perfil › 📄 Contratos",
                "faltantes": faltan_numero,
            })

        # 3) Firma cargada
        from app.services.firma_service import FirmaService
        if not FirmaService().tiene_firma(id_usuario):
            secciones.append({
                "titulo": "Firma",
                "destino": "Mi perfil › ✍️ Firma",
                "faltantes": ["No tienes una firma cargada"],
            })

        # 4) Información laboral (CCF, declarante de renta y dependientes son opcionales)
        il = usuario.get("informacion_laboral") or {}
        es_pensionado = bool(il.get("es_pensionado"))
        ss = il.get("seguridad_social") or {}
        bancaria = il.get("bancaria") or {}
        tributaria = il.get("tributaria") or {}
        faltan_laboral = []
        campos_periodo = self._campos_seguridad_social_periodo(usuario, año, mes)
        for cod, etiqueta in _AFILIACIONES_REQUERIDAS:
            if es_pensionado and cod in ("afp", "ccf"):
                continue
            af = ss.get(cod) or {}
            if self._vacio(af.get("entidad")):
                faltan_laboral.append(f"{etiqueta} (entidad)")
            paga = af.get("paga")
            # Inferir quién paga en registros antiguos sin el campo 'paga'.
            if not paga:
                if not self._vacio(af.get("valor")):
                    paga = "contratista"
                elif not self._vacio(af.get("radicado")):
                    paga = "entidad"
            if not paga:
                faltan_laboral.append(f"{etiqueta} (indicar quién paga el aporte)")
            elif paga == "contratista":
                if self._vacio(af.get("valor")):
                    faltan_laboral.append(f"{etiqueta} (valor mensual)")
                for campo, etiqueta_periodo in campos_periodo:
                    if self._vacio(af.get(campo)):
                        faltan_laboral.append(f"{etiqueta} (valor mensual {etiqueta_periodo})")
            elif paga == "entidad" and self._vacio(af.get("radicado")):
                faltan_laboral.append(f"{etiqueta} (número de radicado)")
        if self._vacio(bancaria.get("banco")):
            faltan_laboral.append("Banco")
        if self._vacio(bancaria.get("numero_cuenta")):
            faltan_laboral.append("Número de cuenta")
        if self._vacio(bancaria.get("tipo_cuenta")):
            faltan_laboral.append("Tipo de cuenta bancaria")
        if self._vacio(tributaria.get("rut")):
            faltan_laboral.append("RUT")
        regimen_actual = tributaria.get("regimen")
        regimenes_validos = {"no_responsable_iva", "responsable_iva", "simple_rst", "especial_rte"}
        if self._vacio(regimen_actual):
            faltan_laboral.append("Régimen tributario")
        elif regimen_actual not in regimenes_validos:
            faltan_laboral.append("Régimen tributario (Valor actual no válido o desactualizado. Selecciona uno nuevo en Mi Perfil)")
        if self._vacio(il.get("grupo_trabajo")):
            faltan_laboral.append("Grupo de trabajo")
        if faltan_laboral:
            secciones.append({
                "titulo": "Información laboral",
                "destino": "Mi perfil › 💼 Información laboral",
                "faltantes": faltan_laboral,
            })

        return {"puede_descargar": not secciones, "secciones": secciones}

    def validar_firma_secop_contrato(self, id_usuario: str, año: int, mes: int) -> dict:
        """Evalúa si el contrato relevante del período (año, mes) tiene diligenciada
        la fecha de firma del contrato en SECOP. Es requisito para generar los
        últimos formatos de contrato (acta de compromiso, balance general CPS y
        acta de recibo y entrega CPS).

        Retorna {"valido": bool, "faltantes": [str]}
        """
        from app.services.certificacion_service import CertificacionService
        usuario = self.repositorio.buscar_por_id(id_usuario) or {}
        contrato = CertificacionService()._contrato_relevante(usuario.get("contratos") or [], año, mes)

        if not contrato or self._vacio(contrato.get("numero")):
            return {"valido": False, "faltantes": ["No se detectó un contrato vigente para este período."]}
        if not contrato.get("firma_cps_secop"):
            numero = contrato.get("numero")
            return {
                "valido": False,
                "faltantes": [f"Fecha de firma del contrato SECOP (contrato {numero})"],
            }
        return {"valido": True, "faltantes": []}

    def validar_datos_acta_recibo_entrega_cps(self, id_usuario: str) -> dict:
        """Evalúa si el usuario cumple con los requisitos específicos para el formato
        Acta de Recibo y Entrega CPS.

        Retorna {"valido": bool, "faltantes": [str]}
        """
        usuario = self.repositorio.buscar_por_id(id_usuario) or {}
        contratos = usuario.get("contratos") or []
        activos = [
            c for c in contratos
            if not self._contrato_finalizado(c, dias_gracia=DIAS_GRACIA_DESCARGA_FORMATOS)
        ]

        faltantes = []

        if not activos:
            faltantes.append("No tienes ningún contrato activo registrado.")
            return {"valido": False, "faltantes": faltantes}

        contrato_activo = activos[-1]

        # 1. Contrato Nº (campo 'numero')
        if self._vacio(contrato_activo.get("numero")):
            faltantes.append("Número de contrato")

        # 2. Fecha de inicio del contrato
        if not contrato_activo.get("fecha_inicio"):
            faltantes.append("Fecha de inicio del contrato")

        # 3. Objeto del contrato
        if self._vacio(contrato_activo.get("objeto")):
            faltantes.append("Objeto del contrato")

        # 4. RP / compromiso presupuestal
        if self._vacio(contrato_activo.get("rp_compromiso_presupuestal")):
            faltantes.append("RP / compromiso presupuestal")

        return {"valido": not faltantes, "faltantes": faltantes}

    def activar_usuario(self, id_usuario: str, validar_permisos: bool = True, permisos_usuario: list = None, usuario_actual: str = None):
        if validar_permisos and permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "usuario.desactivar")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))
        
        usuario = self.repositorio.buscar_por_id(id_usuario)
        resultado = self.repositorio.cambiar_estado(id_usuario, True)
        self.auditoria.registrar_accion(usuario_actual or "sistema", "activar", "usuario", {"usuario_activado": usuario.get("usuario")})
        return resultado

    def desactivar_usuario(self, id_usuario: str, validar_permisos: bool = True, permisos_usuario: list = None, usuario_actual: str = None):
        if validar_permisos and permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "usuario.desactivar")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))
        
        usuario = self.repositorio.buscar_por_id(id_usuario)
        resultado = self.repositorio.cambiar_estado(id_usuario, False)
        self.auditoria.registrar_accion(usuario_actual or "sistema", "desactivar", "usuario", {"usuario_desactivado": usuario.get("usuario")})
        return resultado

    def asegurar_usuario_admin_inicial(self):
        if self.repositorio.buscar_por_usuario("admin"):
            return None

        if not configuracion.admin_inicial_password:
            return None

        datos = {
            "usuario": "admin",
            "nombre_completo": "Administrador del sistema",
            "email": "admin@local",
            "password": configuracion.admin_inicial_password,
            "activo": True,
            "roles": ["admin"],
            "permisos_extra": [],
            "creado_por": "sistema",
        }
        return self.crear_usuario(datos, validar_permisos=False)
