import re
from datetime import datetime, timedelta, timezone

import pytz

from app.core.autorizacion import ValidacionAutorizacion, validar_permiso
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

    @classmethod
    def _contrato_para_validacion(cls, contratos: list) -> dict:
        """Contrato a usar al validar requisitos de un formato: el último activo
        (dentro de los días de gracia) si existe; si todos los contratos ya
        finalizaron y no hay uno más reciente, el último por fecha_inicio, para
        que el formato se siga pudiendo generar con los datos del contrato cerrado."""
        if not contratos:
            return {}
        activos = [
            c for c in contratos
            if not cls._contrato_finalizado(c, dias_gracia=DIAS_GRACIA_DESCARGA_FORMATOS)
        ]
        if activos:
            return activos[-1]
        return max(contratos, key=lambda c: c.get("fecha_inicio") or datetime.min)

    @staticmethod
    def _afiliacion(datos) -> dict:
        """Normaliza una afiliación {entidad, paga, valor, radicado}; campos vacíos → None.

        'paga' indica quién cubre el aporte: si lo paga el contratista se conserva el
        'valor'; si lo paga la entidad se conserva el 'radicado'. Se descarta el dato
        que no corresponde a la opción elegida para evitar inconsistencias.
        """
        datos = datos or {}
        entidad = (datos.get("entidad") or "").strip() or None
        paga = (datos.get("paga") or "").strip() or None
        if paga not in ("contratista", "entidad"):
            paga = None
        valor = datos.get("valor")
        valor = int(valor) if valor not in (None, "", 0) and int(valor) > 0 else None
        radicado = (datos.get("radicado") or "").strip() or None
        if paga == "entidad":
            valor = None
        elif paga == "contratista":
            radicado = None
        return {"entidad": entidad, "paga": paga, "valor": valor, "radicado": radicado}

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
    def _construir_contrato(numero: str, datos: dict) -> dict:
        contrato: dict = {"numero": numero}
        if datos.get("tipo"):
            contrato["tipo"] = datos["tipo"]
        objeto = (datos.get("objeto") or "").strip()
        if objeto:
            contrato["objeto"] = objeto
        radicado = (datos.get("radicado_del_contrato") or "").strip()
        if radicado:
            contrato["radicado_del_contrato"] = radicado
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
        
        # Valores numéricos
        for key in ["valor_total_ejecutado_contrato", "saldo_presp_lib_contrato", "valor_total_pagado"]:
            val = datos.get(key)
            contrato[key] = int(val) if val is not None else None

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
                "valor_bruto_total": int(p.get("valor_bruto_total") or 0),
                "deducciones_pago": int(p.get("deducciones_pago") or 0),
                "deducciones_pago_total": int(p.get("deducciones_pago_total") or 0),
                "valor_neto_pago": int(p.get("valor_neto_pago") or 0),
                "valor_neto_pago_total": int(p.get("valor_neto_pago_total") or 0),
            })
        contrato["pagos"] = pagos_procesados

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

    @classmethod
    def _contrato_campos_faltantes(cls, contrato: dict) -> list:
        """Etiquetas de los campos del contrato que faltan por diligenciar o no son válidos."""
        import re
        faltantes = []
        for clave, etiqueta in _CAMPOS_CONTRATO:
            val = contrato.get(clave)
            if cls._vacio(val):
                faltantes.append(etiqueta)
            elif clave == "numero":
                if not re.fullmatch(r"[0-9]+", str(val).strip()):
                    faltantes.append("Número de contrato (debe ser estrictamente numérico, ej: 3123123)")
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

    def faltantes_para_formatos(self, id_usuario: str) -> dict:
        """Evalúa si el usuario tiene todos los datos necesarios para descargar
        formatos de contrato.

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
            elif paga == "contratista" and self._vacio(af.get("valor")):
                faltan_laboral.append(f"{etiqueta} (valor mensual)")
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

    def validar_datos_balance_general_cps(self, id_usuario: str) -> dict:
        """Evalúa si el usuario cumple con los requisitos específicos para el formato
        Balance General CPS.

        Retorna {"valido": bool, "faltantes": [str]}
        """
        usuario = self.repositorio.buscar_por_id(id_usuario) or {}
        contratos = usuario.get("contratos") or []
        contrato_activo = self._contrato_para_validacion(contratos)

        faltantes = []

        if not contrato_activo:
            faltantes.append("No tienes ningún contrato registrado.")
            return {"valido": False, "faltantes": faltantes}

        # 1. Valor contratado (campo 'valor')
        valor_contratado = contrato_activo.get("valor")
        if self._vacio(valor_contratado):
            faltantes.append("Valor contratado (debe ser mayor a cero)")

        # 2. Valor total Pagado
        valor_total_pagado = contrato_activo.get("valor_total_pagado")
        if self._vacio(valor_total_pagado):
            faltantes.append("Valor total pagado (debe ser mayor a cero)")

        # 3. Pagos: al menos un pago registrado en el último contrato activo
        pagos = contrato_activo.get("pagos") or []
        if not pagos:
            faltantes.append("Plan de pagos: al menos un pago registrado")
        else:
            # 4. Valores acumulados en los pagos
            primer_pago = pagos[0]
            val_bruto_tot = primer_pago.get("valor_bruto_total")
            deduc_tot = primer_pago.get("deducciones_pago_total")
            val_neto_tot = primer_pago.get("valor_neto_pago_total")

            if self._vacio(val_bruto_tot):
                faltantes.append("Valor Bruto Total (Acumulado) (debe ser mayor a cero)")

            if deduc_tot is None or (isinstance(deduc_tot, str) and not deduc_tot.strip()):
                faltantes.append("Deducciones Total (Acumulado) (debe estar diligenciado)")

            if self._vacio(val_neto_tot):
                faltantes.append("Valor Neto Total (Acumulado) (debe ser mayor a cero)")

        return {"valido": not faltantes, "faltantes": faltantes}

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

        # 4. Radicado del contrato (del último contrato activo)
        if self._vacio(contrato_activo.get("radicado_del_contrato")):
            faltantes.append("Radicado del contrato")

        # 5. RP / compromiso presupuestal
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
