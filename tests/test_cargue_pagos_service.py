import io
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.services.cargue_pagos_service import (
    limpiar_cedula,
    limpiar_numero_pago,
    limpiar_valor_monetario,
    limpiar_fecha_pago,
    CarguePagosService,
    CAT_VALIDO,
    CAT_DUPLICADO_INTERNO,
    CAT_USUARIO_NO_ENCONTRADO,
    CAT_SIN_CONTRATO_ACTIVO,
    CAT_DATO_INVALIDO,
    CAT_YA_EXISTE,
    CAT_EXCEDE_LIMITE,
)


def test_limpiar_cedula_entero():
    assert limpiar_cedula(79334686) == "79334686"


def test_limpiar_cedula_con_decimal_de_lectura_float():
    assert limpiar_cedula("79334686.0") == "79334686"


def test_limpiar_cedula_con_puntos_y_espacios():
    assert limpiar_cedula(" 79.334.686 ") == "79334686"


def test_limpiar_cedula_invalida_retorna_none():
    assert limpiar_cedula("ABC123") is None
    assert limpiar_cedula(None) is None
    assert limpiar_cedula("") is None


def test_limpiar_numero_pago_entero_a_string():
    assert limpiar_numero_pago(100185826) == "100185826"


def test_limpiar_numero_pago_vacio_es_none():
    assert limpiar_numero_pago(None) is None
    assert limpiar_numero_pago("   ") is None


def test_limpiar_valor_monetario_con_comas_y_decimales():
    assert limpiar_valor_monetario("26,026,880.00") == 26026880


def test_limpiar_valor_monetario_cero():
    assert limpiar_valor_monetario("0.00") == 0


def test_limpiar_valor_monetario_invalido_es_none():
    assert limpiar_valor_monetario("no es un numero") is None
    assert limpiar_valor_monetario(None) is None
    assert limpiar_valor_monetario(float("nan")) is None


def test_limpiar_fecha_pago_con_hora():
    resultado = limpiar_fecha_pago("2026-03-31 03:41:42")
    assert resultado == datetime(2026, 3, 31, tzinfo=timezone.utc)


def test_limpiar_fecha_pago_invalida_es_none():
    assert limpiar_fecha_pago("fecha invalida") is None
    assert limpiar_fecha_pago(None) is None
    assert limpiar_fecha_pago("") is None


class _FakeRepo:
    def __init__(self, usuarios):
        self._usuarios = usuarios

    def listar(self):
        return self._usuarios


def _fila_excel(numero_doc=100185826, fecha="2026-03-31 03:41:42", bruto="1,000,000.00",
                 deducciones="0.00", neto="1,000,000.00", tipo_id="Cédula de Ciudadanía",
                 identificacion=79334686, concepto="HONORARIOS FEBRERO"):
    return {
        "Numero Documento": numero_doc,
        "Fecha de Registro": fecha,
        "Fecha de pago": fecha,
        "Estado": "Pagada",
        "Valor Bruto": bruto,
        "Valor Deducciones": deducciones,
        "Valor Neto": neto,
        "Tipo Identificacion": tipo_id,
        "Identificacion": identificacion,
        "Concepto Pago": concepto,
        "Objeto del Compromiso": concepto,
    }


def _excel_bytes(filas: list[dict]) -> io.BytesIO:
    df = pd.DataFrame(filas)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return buffer


def _usuario_con_contrato_activo(numero_documento="79334686", numero_contrato="3123123"):
    return {
        "_id": "u1",
        "numero_documento": numero_documento,
        "nombre_completo": "Carlos Acosta",
        "contratos": [
            {
                "numero": numero_contrato,
                "valor": 50_000_000,
                "fecha_inicio": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "fecha_fin": datetime(2026, 12, 31, tzinfo=timezone.utc),
                "pagos": [],
            }
        ],
    }


def test_fila_valida_se_clasifica_como_valido():
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel()]))

    assert resultado["resumen"][CAT_VALIDO] == 1
    fila = resultado["filas"][0]
    assert fila["categoria"] == CAT_VALIDO
    assert fila["id_usuario"] == "u1"
    assert fila["numero_contrato"] == "3123123"
    assert fila["valor_bruto_pago"] == 1_000_000
    assert fila["seleccionable"] is True


def test_fila_con_nit_se_ignora_sin_generar_error():
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel(tipo_id="NIT", identificacion=800098911)]))

    assert resultado["filas"] == []
    assert sum(resultado["resumen"].values()) == 0


def test_usuario_no_encontrado():
    repo = _FakeRepo([])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel()]))

    assert resultado["filas"][0]["categoria"] == CAT_USUARIO_NO_ENCONTRADO


def test_usuario_sin_contrato_activo():
    usuario = _usuario_con_contrato_activo()
    usuario["contratos"][0]["fecha_fin"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
    repo = _FakeRepo([usuario])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel()]))

    assert resultado["filas"][0]["categoria"] == CAT_SIN_CONTRATO_ACTIVO


def test_fecha_vacia_es_dato_invalido():
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel(fecha=None)]))

    assert resultado["filas"][0]["categoria"] == CAT_DATO_INVALIDO


def test_valor_neto_negativo_es_dato_invalido():
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel(neto="-50,000.00")]))

    assert resultado["filas"][0]["categoria"] == CAT_DATO_INVALIDO


def test_filas_duplicadas_en_el_mismo_archivo():
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    fila = _fila_excel()
    resultado = servicio.procesar_archivo(_excel_bytes([fila, dict(fila)]))

    categorias = [f["categoria"] for f in resultado["filas"]]
    assert categorias.count(CAT_VALIDO) == 1
    assert categorias.count(CAT_DUPLICADO_INTERNO) == 1


def test_pago_ya_existente_en_bd():
    # fecha_pago naive (sin tzinfo): así es como PyMongo realmente devuelve una
    # fecha leída de un documento existente, porque el MongoClient de
    # app/db/mongo.py no usa tz_aware=True. El lado del Excel (limpiar_fecha_pago)
    # sí produce un datetime tz-aware, así que este test fuerza exactamente el
    # desajuste naive-vs-aware que _fecha_utc debe resolver.
    usuario = _usuario_con_contrato_activo()
    usuario["contratos"][0]["pagos"] = [{
        "numero_pago": "100185826",
        "fecha_pago": datetime(2026, 3, 31),
        "valor_bruto_pago": 1_000_000,
        "deducciones_pago": 0,
        "valor_neto_pago": 1_000_000,
    }]
    repo = _FakeRepo([usuario])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(_excel_bytes([_fila_excel()]))

    assert resultado["filas"][0]["categoria"] == CAT_YA_EXISTE


def test_excede_limite_de_20_pagos_rechaza_el_contrato_completo():
    usuario = _usuario_con_contrato_activo()
    usuario["contratos"][0]["pagos"] = [
        {
            "numero_pago": f"existente-{i}",
            "fecha_pago": datetime(2026, 3, 31),  # naive, como lo devuelve Mongo realmente
            "valor_bruto_pago": 100,
            "deducciones_pago": 0,
            "valor_neto_pago": 100,
        }
        for i in range(19)
    ]
    repo = _FakeRepo([usuario])
    servicio = CarguePagosService(repositorio=repo)
    filas = [
        _fila_excel(numero_doc=200000000 + i, fecha=f"2026-0{(i % 9) + 1}-15 00:00:00", neto=f"{1000 + i}.00", bruto=f"{1000 + i}.00")
        for i in range(2)
    ]
    resultado = servicio.procesar_archivo(_excel_bytes(filas))

    categorias = [f["categoria"] for f in resultado["filas"]]
    assert categorias == [CAT_EXCEDE_LIMITE, CAT_EXCEDE_LIMITE]


def test_archivo_sin_columnas_requeridas_lanza_error_claro():
    df = pd.DataFrame([{"Columna random": 1}])
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    servicio = CarguePagosService(repositorio=_FakeRepo([]))
    with pytest.raises(ValueError, match="columnas"):
        servicio.procesar_archivo(buffer)


def datetime_import_helper():
    """Fecha de pago fija reutilizada por los fixtures de confirmar_carga."""
    return datetime(2026, 3, 31, tzinfo=timezone.utc)


class _FakeRepoEscritura(_FakeRepo):
    def __init__(self, usuarios):
        super().__init__(usuarios)
        self._por_id = {u["_id"]: u for u in usuarios}
        self.llamadas_editar = []

    def buscar_por_id(self, id_usuario):
        return self._por_id.get(id_usuario)

    def editar_contrato_en_usuario(self, id_usuario, numero_contrato, nuevo_contrato):
        self.llamadas_editar.append((id_usuario, numero_contrato, nuevo_contrato))
        usuario = self._por_id[id_usuario]
        for i, c in enumerate(usuario["contratos"]):
            if c["numero"] == numero_contrato:
                usuario["contratos"][i] = nuevo_contrato


class _FakeAuditoria:
    def __init__(self):
        self.registros = []

    def registrar_accion(self, usuario, accion, recurso, detalle=None, exito=True):
        self.registros.append((usuario, accion, recurso, detalle, exito))


def _fila_valida_para_confirmar(id_usuario="u1", numero_contrato="3123123", numero_pago="100185826",
                                  valor_bruto=1_000_000, valor_neto=1_000_000):
    return {
        "categoria": CAT_VALIDO,
        "id_usuario": id_usuario,
        "numero_contrato": numero_contrato,
        "numero_pago": numero_pago,
        "fecha_pago": datetime_import_helper(),
        "valor_bruto_pago": valor_bruto,
        "deducciones_pago": 0,
        "valor_neto_pago": valor_neto,
    }


def test_confirmar_carga_agrega_pago_y_recalcula_totales():
    usuario = _usuario_con_contrato_activo()
    repo = _FakeRepoEscritura([usuario])
    auditoria = _FakeAuditoria()
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = auditoria

    resultado = servicio.confirmar_carga(
        [_fila_valida_para_confirmar()], usuario_que_carga="admin1", nombre_archivo="balances_marzo.xlsx"
    )

    assert resultado["ok"] == [{"id_usuario": "u1", "numero_contrato": "3123123", "agregados": 1}]
    assert resultado["fallidos"] == []
    _, _, contrato_guardado = repo.llamadas_editar[0]
    assert contrato_guardado["pagos"][0]["numero_pago"] == "100185826"
    assert contrato_guardado["valor_total_pagado"] == 1_000_000
    assert contrato_guardado["valor_total_por_pagar_contrato"] == 49_000_000  # 50M - 1M
    assert len(auditoria.registros) == 1
    _, _, _, detalle, _ = auditoria.registros[0]
    assert detalle == {"pagos_agregados": 1, "archivo": "balances_marzo.xlsx"}


def test_confirmar_carga_ignora_filas_que_no_son_validas():
    usuario = _usuario_con_contrato_activo()
    repo = _FakeRepoEscritura([usuario])
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    fila_no_valida = _fila_valida_para_confirmar()
    fila_no_valida["categoria"] = CAT_DATO_INVALIDO

    resultado = servicio.confirmar_carga([fila_no_valida], usuario_que_carga="admin1")

    assert resultado["ok"] == []
    assert repo.llamadas_editar == []


def test_confirmar_carga_es_idempotente_si_se_llama_dos_veces():
    usuario = _usuario_con_contrato_activo()
    repo = _FakeRepoEscritura([usuario])
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    fila = _fila_valida_para_confirmar()
    primera = servicio.confirmar_carga([fila], usuario_que_carga="admin1")

    # Simula el round-trip real por Mongo: una fecha recién escrita por este mismo
    # proceso queda tz-aware en memoria, pero al releerla de una BD real (el
    # MongoClient no usa tz_aware=True) vuelve naive. Forzamos esa forma aquí para
    # que la segunda llamada ejercite el mismo desajuste naive-vs-aware que en
    # producción, no una comparación aware-contra-aware que nunca falla.
    pago_guardado = repo._por_id["u1"]["contratos"][0]["pagos"][0]
    pago_guardado["fecha_pago"] = pago_guardado["fecha_pago"].replace(tzinfo=None)

    segunda = servicio.confirmar_carga([fila], usuario_que_carga="admin1")

    assert primera["ok"][0]["agregados"] == 1
    assert segunda["ok"] == []  # ya existe, no se vuelve a agregar ni duplicar
    assert len(repo._por_id["u1"]["contratos"][0]["pagos"]) == 1


def test_confirmar_carga_revalida_cupo_al_momento_de_escribir():
    usuario = _usuario_con_contrato_activo()
    usuario["contratos"][0]["pagos"] = [
        {"numero_pago": f"x{i}", "fecha_pago": datetime(2026, 3, 31),  # naive, como Mongo
         "valor_bruto_pago": 1, "deducciones_pago": 0, "valor_neto_pago": 1}
        for i in range(20)
    ]
    repo = _FakeRepoEscritura([usuario])
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    resultado = servicio.confirmar_carga([_fila_valida_para_confirmar()], usuario_que_carga="admin1")

    assert resultado["ok"] == []
    assert len(resultado["fallidos"]) == 1
    assert "20" in resultado["fallidos"][0]["motivo"] or "límite" in resultado["fallidos"][0]["motivo"].lower()


def test_confirmar_carga_aisla_fallos_entre_contratos():
    usuario_ok = _usuario_con_contrato_activo(numero_documento="1", numero_contrato="A")
    usuario_ok["_id"] = "u_ok"
    usuario_sin_contrato = _usuario_con_contrato_activo(numero_documento="2", numero_contrato="B")
    usuario_sin_contrato["_id"] = "u_fail"
    usuario_sin_contrato["contratos"] = []  # ya no tiene el contrato "B" al momento de confirmar

    repo = _FakeRepoEscritura([usuario_ok, usuario_sin_contrato])
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    filas = [
        _fila_valida_para_confirmar(id_usuario="u_ok", numero_contrato="A"),
        _fila_valida_para_confirmar(id_usuario="u_fail", numero_contrato="B"),
    ]
    resultado = servicio.confirmar_carga(filas, usuario_que_carga="admin1")

    assert len(resultado["ok"]) == 1
    assert resultado["ok"][0]["id_usuario"] == "u_ok"
    assert len(resultado["fallidos"]) == 1
    assert resultado["fallidos"][0]["id_usuario"] == "u_fail"


def test_contrato_en_periodo_de_gracia_es_valido_en_preview_y_confirma_ok():
    """Un contrato cuya fecha_fin quedó hace ~30 días (dentro de los 60 días de
    gracia de CertificacionService._contrato_vigente) debe clasificarse como
    CAT_VALIDO en procesar_archivo Y debe poder confirmarse con éxito: antes de
    este fix, confirmar_carga usaba UsuarioService._contrato_finalizado(contrato)
    con dias_gracia=0 (sin gracia), por lo que una fila "válida" en el preview
    fallaba igual al confirmar con "El contrato ya no está activo."."""
    usuario = _usuario_con_contrato_activo()
    usuario["contratos"][0]["fecha_fin"] = datetime.now(timezone.utc) - timedelta(days=30)
    repo = _FakeRepoEscritura([usuario])
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    resultado_preview = servicio.procesar_archivo(_excel_bytes([_fila_excel()]))
    assert resultado_preview["filas"][0]["categoria"] == CAT_VALIDO

    resultado_confirmar = servicio.confirmar_carga(resultado_preview["filas"], usuario_que_carga="admin1")

    assert resultado_confirmar["fallidos"] == []
    assert resultado_confirmar["ok"] == [{"id_usuario": "u1", "numero_contrato": "3123123", "agregados": 1}]


class _FakeRepoEscrituraConFalloInesperado(_FakeRepoEscritura):
    """Simula que editar_contrato_en_usuario lanza una excepción que NO es
    ValueError (p. ej. un pymongo.errors.WriteError por validación de esquema,
    o un KeyError por un documento existente malformado) para un contrato
    puntual, mientras otro contrato independiente en el mismo lote se procesa
    con normalidad."""

    def __init__(self, usuarios, numero_contrato_que_falla, excepcion):
        super().__init__(usuarios)
        self._numero_contrato_que_falla = numero_contrato_que_falla
        self._excepcion = excepcion

    def editar_contrato_en_usuario(self, id_usuario, numero_contrato, nuevo_contrato):
        if numero_contrato == self._numero_contrato_que_falla:
            raise self._excepcion
        super().editar_contrato_en_usuario(id_usuario, numero_contrato, nuevo_contrato)


def test_confirmar_carga_aisla_fallos_que_no_son_value_error():
    """Antes de este fix, el loop de confirmar_carga solo capturaba ValueError;
    cualquier otra excepción (RuntimeError, KeyError, un WriteError real de
    pymongo por la validación de esquema de la colección) escapaba del loop
    completo, abortando el resto del lote sin reportar nada al admin."""
    usuario_ok = _usuario_con_contrato_activo(numero_documento="1", numero_contrato="A")
    usuario_ok["_id"] = "u_ok"
    usuario_falla = _usuario_con_contrato_activo(numero_documento="2", numero_contrato="B")
    usuario_falla["_id"] = "u_falla"

    repo = _FakeRepoEscrituraConFalloInesperado(
        [usuario_ok, usuario_falla],
        numero_contrato_que_falla="B",
        excepcion=RuntimeError("fallo de conexión inesperado"),
    )
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    filas = [
        _fila_valida_para_confirmar(id_usuario="u_ok", numero_contrato="A"),
        _fila_valida_para_confirmar(id_usuario="u_falla", numero_contrato="B"),
    ]
    resultado = servicio.confirmar_carga(filas, usuario_que_carga="admin1")

    assert len(resultado["ok"]) == 1
    assert resultado["ok"][0]["id_usuario"] == "u_ok"
    assert len(resultado["fallidos"]) == 1
    assert resultado["fallidos"][0]["id_usuario"] == "u_falla"
    assert "fallo de conexión inesperado" in resultado["fallidos"][0]["motivo"]


def test_confirmar_carga_aisla_key_error_sin_abortar_el_lote():
    """Mismo caso que arriba pero con KeyError, el ejemplo concreto que el
    reviewer señaló para datos malformados leídos de un pagos[] existente."""
    usuario_ok = _usuario_con_contrato_activo(numero_documento="1", numero_contrato="A")
    usuario_ok["_id"] = "u_ok"
    usuario_falla = _usuario_con_contrato_activo(numero_documento="2", numero_contrato="B")
    usuario_falla["_id"] = "u_falla"

    repo = _FakeRepoEscrituraConFalloInesperado(
        [usuario_ok, usuario_falla],
        numero_contrato_que_falla="B",
        excepcion=KeyError("numero_pago"),
    )
    servicio = CarguePagosService(repositorio=repo)
    servicio.auditoria = _FakeAuditoria()

    filas = [
        _fila_valida_para_confirmar(id_usuario="u_ok", numero_contrato="A"),
        _fila_valida_para_confirmar(id_usuario="u_falla", numero_contrato="B"),
    ]
    resultado = servicio.confirmar_carga(filas, usuario_que_carga="admin1")

    assert len(resultado["ok"]) == 1
    assert resultado["ok"][0]["id_usuario"] == "u_ok"
    assert len(resultado["fallidos"]) == 1
    assert resultado["fallidos"][0]["id_usuario"] == "u_falla"


def test_concepto_vacio_en_excel_no_se_vuelve_literal_nan():
    """Una celda vacía de 'Concepto Pago' y 'Objeto del Compromiso' llega como
    NaN (float) desde pandas; sin guarda, str(nan) produce la cadena literal
    'nan', que no ayuda al admin a juzgar si el pago corresponde a honorarios."""
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    fila = _fila_excel(concepto=None)
    resultado = servicio.procesar_archivo(_excel_bytes([fila]))

    assert resultado["filas"][0]["concepto"] == ""


def test_tipo_identificacion_con_espacios_se_reconoce_como_cedula():
    """Un espacio accesorio alrededor de 'Cédula de Ciudadanía' no debe hacer que
    la fila se trate como si no tuviera ningún tipo de identificación reconocido."""
    repo = _FakeRepo([_usuario_con_contrato_activo()])
    servicio = CarguePagosService(repositorio=repo)
    resultado = servicio.procesar_archivo(
        _excel_bytes([_fila_excel(tipo_id="  Cédula de Ciudadanía  ")])
    )

    assert resultado["filas"][0]["categoria"] == CAT_VALIDO
