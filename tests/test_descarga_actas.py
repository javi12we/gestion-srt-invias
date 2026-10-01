import pytest

from app.services.certificacion_service import CertificacionService

_FIRMA = {"firmante_id": "x", "firmante_nombre": "Alguien"}

descargable = CertificacionService.acta_descargable_por_contratista


@pytest.mark.parametrize("tipo", ["acta_recibo_entrega_cps", "acta_recibo_entrega_cps_real"])
def test_con_financiera_y_juridico_ya_se_puede_descargar_aunque_falte_jefe(tipo):
    cert = {"tipo_formato": tipo, "estado": "pendiente", "firmas": {"financiera": _FIRMA, "abogado": _FIRMA}}

    assert descargable(cert) is True


@pytest.mark.parametrize("firmas", [
    None,
    {},
    {"financiera": _FIRMA},
    {"abogado": _FIRMA},
    {"financiera": _FIRMA, "abogado": None},
    {"extra_balance_general": _FIRMA},
])
def test_sin_los_dos_vistos_buenos_no_se_puede_descargar(firmas):
    cert = {"tipo_formato": "acta_recibo_entrega_cps", "estado": "pendiente", "firmas": firmas}

    assert descargable(cert) is False


def test_formato_aprobado_siempre_se_puede_descargar():
    assert descargable({"tipo_formato": "acta_recibo_entrega_cps_real", "estado": "aprobado"}) is True


def test_acta_de_compromiso_pendiente_no_entra_en_la_regla():
    cert = {"tipo_formato": "acta_compromiso", "estado": "pendiente", "firmas": {"financiera": _FIRMA, "abogado": _FIRMA}}

    assert descargable(cert) is False
    assert descargable(None) is False
