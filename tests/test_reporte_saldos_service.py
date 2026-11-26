from datetime import datetime

import openpyxl
import pytest

from app.core.autorizacion import ValidacionAutorizacion
from app.services.reporte_saldos_service import ReporteSaldosService, construir_filas


def _pago(numero, mes, bruto, deducciones=0):
    return {
        "numero_pago": numero,
        "fecha_pago": datetime(2026, mes, 1),
        "valor_bruto_pago": bruto,
        "deducciones_pago": deducciones,
        "valor_neto_pago": bruto - deducciones,
    }


def _usuario(**contrato):
    base = {"numero": "100", "valor": 1000, "fecha_inicio": datetime(2026, 1, 15)}
    base.update(contrato)
    return {"nombre_completo": "Persona Prueba", "numero_documento": "123", "contratos": [base]}


class RepoFalso:
    def __init__(self, usuarios):
        self.usuarios = usuarios

    def listar_con_contratos(self):
        return self.usuarios


def test_saldo_incluye_adicion_y_descuenta_pagos_brutos():
    usuario = _usuario(
        adiciones_contrato={"tiene_adiciones": True, "valor_adicion": 500},
        pagos=[_pago("B", 3, 300, 30), _pago("A", 2, 200, 20)],
    )

    resumen, pagos, _ = construir_filas([usuario])

    assert resumen[0]["valor_total"] == 1500
    assert resumen[0]["total_bruto"] == 500
    assert resumen[0]["total_neto"] == 450
    assert resumen[0]["saldo"] == 1000
    assert [(p["numero_pago"], p["saldo"]) for p in pagos] == [("A", 1300), ("B", 1000)]


def test_adicion_desmarcada_no_se_suma():
    usuario = _usuario(adiciones_contrato={"tiene_adiciones": False, "valor_adicion": 500})

    resumen, _, _ = construir_filas([usuario])

    assert resumen[0]["valor_total"] == 1000
    assert resumen[0]["saldo"] == 1000


def test_pagos_mayores_al_contrato_dejan_saldo_negativo():
    resumen, _, _ = construir_filas([_usuario(pagos=[_pago("A", 2, 1200)])])

    assert resumen[0]["saldo"] == -200
    assert "superan" in resumen[0]["observaciones"]


def test_contrato_sin_valor_no_calcula_saldo():
    resumen, pagos, _ = construir_filas([_usuario(valor=None, pagos=[_pago("A", 2, 100)])])

    assert resumen[0]["saldo"] is None
    assert pagos[0]["saldo"] is None
    assert "Sin valor" in resumen[0]["observaciones"]


def test_filtro_por_anio_cuenta_los_contratos_sin_fecha():
    usuarios = [_usuario(), _usuario(numero="200", fecha_inicio=None)]

    assert len(construir_filas(usuarios, 2026)[0]) == 1
    assert construir_filas(usuarios, 2026)[2] == 1
    assert construir_filas(usuarios, 2025)[0] == []
    assert len(construir_filas(usuarios)[0]) == 2


@pytest.mark.parametrize("roles", [[], ["coordinador"], ["direccion"]])
def test_solo_admin_puede_generar(roles):
    servicio = ReporteSaldosService(repositorio=RepoFalso([_usuario()]))

    with pytest.raises(ValidacionAutorizacion):
        servicio.generar_excel(roles)
    with pytest.raises(ValidacionAutorizacion):
        servicio.anios_disponibles(roles)


def test_excel_tiene_dos_hojas_con_formulas_y_totales():
    usuario = _usuario(pagos=[_pago("A", 2, 200)])
    usuario["nombre_completo"] = "=1+1"
    servicio = ReporteSaldosService(repositorio=RepoFalso([usuario]))

    reporte = servicio.generar_excel(["admin"], 2026)
    libro = openpyxl.load_workbook(reporte["buffer"])

    assert libro.sheetnames == ["Resumen", "Pagos"]
    resumen = libro["Resumen"]
    assert resumen["A2"].value == "=1+1" and resumen["A2"].data_type == "s"
    assert resumen["C2"].value == "123"
    assert resumen["L2"].value == "=J2+K2"
    assert resumen["Q2"].value == "=L2-N2"
    assert resumen["Q3"].value == "=SUBTOTAL(9,Q2:Q2)"
    assert libro["Pagos"]["K2"].value == 800


def test_excel_sin_contratos():
    reporte = ReporteSaldosService(repositorio=RepoFalso([])).generar_excel(["admin"])

    assert reporte["contratos"] == 0
    assert openpyxl.load_workbook(reporte["buffer"])["Resumen"].max_row == 1
