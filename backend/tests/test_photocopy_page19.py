import pytest
from app.services.extractor_service import ExtractorService
from app.services.spatial_field_extractor import spatial_field_extractor
from app.services.document_side_classifier import document_side_classifier
from app.utils.name_cleaner import resolver_nombre_completo

SAMPLE_TEXT = """OFICINA DEPARTAMENTAL DE LA MUJER
EMPRENDEDORA
FLORENCIA-CAQUETÁ
FOTOCOPIA TARJETA DE IDENTIDAD PARA PROCESO DE INSCRIPCION/MATRICULA CAMPESENA - FULLPOPULAR

REPÚBLICA DE COLOMBIA
IDENTIFICACIÓN PERSONAL
TARJETA DE IDENTIDAD
NUMERO 1.125.182.543
QUIÑONES GOMEZ
APELLIDOS
NADIA YULIETH
NOMBRES
Documento de identidad facilitado para proceso de inscripción y matrícula en el SENA CAQUETA en el Centro Tecnológico de la Amazonía en la Estrategia CAMPESINA-FULL POPULAR
Septiembre de 2026
FECHA DE NACIMIENTO 13-ENE-2010
PUERTO GUZMAN (PUTUMAYO)
LUGAR DE NACIMIENTO
13-ENE-2028 FECHA DE VENCIMIENTO
0+ RH F SEXO
29-JUN-2017 FLORENCIA FECHA Y LUGAR DE EXPEDICIÓN
"""


def test_clasificacion_dos_caras_en_una_hoja():
    clasif = document_side_classifier.clasificar_cara(SAMPLE_TEXT)
    assert clasif.get("cara") == "CEDULA_AMBOS_LADOS"
    assert clasif.get("tipo_documento") == "TARJETA_IDENTIDAD"


def test_extraccion_espacial_tarjeta_identidad():
    lineas = [l.strip() for l in SAMPLE_TEXT.split("\n") if l.strip()]

    class PseudoOCRLine:
        def __init__(self, text_val, y_pos):
            self.text = text_val
            self.x = 0.3
            self.y = y_pos
            self.w = 0.4
            self.h = 0.03
            self.confidence = 0.95

    lines = [PseudoOCRLine(l, (idx + 1) * 0.04) for idx, l in enumerate(lineas)]

    res_esp = spatial_field_extractor.extraer_todos_los_campos(lines, 1, 0.95)

    assert res_esp.get("identificacion", {}).get("value") == "1125182543"
    assert res_esp.get("apellidos", {}).get("value") == "QUIÑONES GOMEZ"
    assert res_esp.get("nombres", {}).get("value") == "NADIA YULIETH"
    assert res_esp.get("fecha_nacimiento", {}).get("value") == "2010-01-13"
    assert res_esp.get("fecha_expedicion", {}).get("value") == "2017-06-29"
    assert res_esp.get("lugar_expedicion", {}).get("value") == "FLORENCIA"
    assert res_esp.get("sexo", {}).get("value") == "F"


def test_extractor_service_completo():
    extractor = ExtractorService()
    res_ext = extractor.extraer(SAMPLE_TEXT)

    assert res_ext.get("identificacion") == "1125182543"
    assert res_ext.get("apellidos") == "QUIÑONES GOMEZ"
    assert res_ext.get("nombres") == "NADIA YULIETH"
    assert res_ext.get("fecha_nacimiento") == "2010-01-13"
    assert res_ext.get("fecha_expedicion") == "2017-06-29"
    assert "EMPRENDEDORA" not in str(res_ext.get("nombres"))
    assert "FOTOCOPIA" not in str(res_ext.get("nombres"))
    assert "EMPRENDEDORA" not in str(res_ext.get("apellidos"))


def test_resolver_nombre_completo_sin_ruido_administrativo():
    nom_res = resolver_nombre_completo(
        nombres="NADIA YULIETH",
        apellidos="QUIÑONES GOMEZ",
        actual="FOTOCOPIA DE PARA PROCESO INSCRIPCION EMPRENDEDORA"
    )
    assert nom_res == "NADIA YULIETH QUIÑONES GOMEZ"


def test_filtro_geografico_fused():
    from app.services.colombia_geo_service import colombia_geo
    assert colombia_geo.es_geografico("FLORENCIACAQUETÁ") is True
    assert colombia_geo.es_geografico("FLORENCIA-CAQUETÁ") is True
    assert colombia_geo.es_geografico("ARMENIAQUINDIO") is True
    assert colombia_geo.es_geografico("NEIVAHUILA") is True
    assert colombia_geo.es_geografico("NADIA YULIETH") is False
    assert colombia_geo.es_geografico("QUIÑONES GOMEZ") is False

