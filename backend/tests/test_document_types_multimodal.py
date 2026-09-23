"""
Tests automatizados para los nuevos tipos de documentos:
- CC (Cédula de Ciudadanía)
- TI (Tarjeta de Identidad)
- CE (Cédula de Extranjería con cédulas de 6 dígitos)
- PPT (Permiso por Protección Temporal sin prefijo 'VEN' en nombres)
- Contraseña (Comprobante de Documento en Trámite)
- Pasaporte
"""
import pytest
from app.utils.validators import validador
from app.services.extractor_service import extractor_service
from app.services.document_detector import document_detector
from app.services.document_side_classifier import document_side_classifier
from app.services.document_layout_classifier import document_layout_classifier


def test_validar_cedula_6_digitos():
    """Valida que números de identificación de 6 dígitos (ej: Cédula de Extranjería) sean aceptados."""
    valido, num = validador.validar_cedula("984581")
    assert valido is True
    assert num == "984581"

    # Menor a 6 dígitos no es admisible
    valido_corto, _ = validador.validar_cedula("12345")
    assert valido_corto is False


def test_es_secuencia_fecha():
    """Valida que fechas no sean confundidas con números de cédula."""
    assert validador.es_secuencia_fecha("19850323") is True
    assert validador.es_secuencia_fecha("20051231") is True
    assert validador.es_secuencia_fecha("31122005") is True
    assert validador.es_secuencia_fecha("1117513499") is False
    assert validador.es_secuencia_fecha("984581") is False


def test_limpiar_nombres_ignora_nacionalidad_ven_ecu():
    """Valida que códigos de país (VEN, ECU, COL) no se adjunten al nombre."""
    nombre_limpio = validador.normalizar_nombre("VEN ROSSLYN DEL VALLE")
    assert "VEN" not in nombre_limpio.split()
    assert "ROSSLYN DEL VALLE" in nombre_limpio

    nombre_ecu = validador.normalizar_nombre("ECU VERONICA ELIZABETH")
    assert "ECU" not in nombre_ecu.split()
    assert "VERONICA ELIZABETH" in nombre_ecu


def test_extraccion_cedula_extranjeria_6_digitos():
    """
    Simula el caso real del screenshot 1:
    Cédula de Extranjería de 6 dígitos (984581) donde previamente se extraía
    la fecha de nacimiento (19850323) como identificación.
    """
    texto_ce = """
    COL REPUBLICA DE COLOMBIA
    Cedula de Extranjeria
    RESIDENTE No. 984581
    APELLIDOS
    MOSQUERA CERCADO
    NOMBRES
    VERONICA ELIZABETH
    NACIONALIDAD ECU
    FECHA DE NACIMIENTO 1985/03/23
    SEXO F
    EXPEDICION 2024/07/10
    VENCE 2029/07/09
    I<COL984581<<<1<<<<<<<<<<<<<<<
    8503231F2907099ECU<<<<<<<<<<<0
    MOSQUERA<CERCADO<<VERONICA<ELI
    """
    res = extractor_service.extraer(texto_ce, pagina_num=1)

    assert res["tipo_documento"] == "CEDULA_EXTRANJERIA"
    assert res["identificacion"] == "984581"
    assert res["identificacion"] != "19850323"
    assert "MOSQUERA" in (res["apellidos"] or "")
    assert "VERONICA" in (res["nombres"] or "")


def test_extraccion_ppt_sin_nacionalidad_en_nombre():
    """
    Simula el caso real del screenshot 2:
    Permiso por Protección Temporal (PPT) con 'VEN' adyacente a 'ROSSLYN DEL VALLE'.
    """
    texto_ppt = """
    REPUBLICA DE COLOMBIA
    PERMISO POR PROTECCION TEMPORAL
    MIGRACION COLOMBIA
    No. 4969970
    APELLIDOS
    REYES
    NOMBRES
    ROSSLYN DEL VALLE
    NACIONALIDAD VEN
    SEXO F
    FECHA DE NACIMIENTO 04-01-1991
    17-02-2023 BOGOTA D.C.
    30-05-2031
    VISIBLES
    """
    res = extractor_service.extraer(texto_ppt, pagina_num=1)

    assert res["tipo_documento"] == "PPT"
    assert res["identificacion"] == "4969970"
    # El nombre NO debe tener el prefijo 'VEN'
    assert "VEN" not in (res["nombres"] or "").split()
    assert "ROSSLYN" in (res["nombres"] or "")
    assert res["fecha_nacimiento"] == "1991-01-04"
    assert res["fecha_expedicion"] == "2023-02-17"


def test_deteccion_layout_direcciones():
    """Verifica que el clasificador de layout asigne VALUE_BELOW_LABEL a PPT, CE, Pasaporte y Contraseña."""
    class LineMock:
        def __init__(self, text):
            self.text = text

    lines_ppt = [LineMock("REPUBLICA DE COLOMBIA"), LineMock("PERMISO POR PROTECCION TEMPORAL"), LineMock("APELLIDOS")]
    layout_ppt = document_layout_classifier.clasificar_layout(lines_ppt)
    assert layout_ppt["layout_type"] == "PPT"
    assert layout_ppt["expected_direction"] == "VALUE_BELOW_LABEL"

    lines_ce = [LineMock("REPUBLICA DE COLOMBIA"), LineMock("CEDULA DE EXTRANJERIA"), LineMock("APELLIDOS")]
    layout_ce = document_layout_classifier.clasificar_layout(lines_ce)
    assert layout_ce["layout_type"] == "CEDULA_EXTRANJERIA"
    assert layout_ce["expected_direction"] == "VALUE_BELOW_LABEL"


def test_detector_documento_nuevos_tipos():
    """Verifica la detección por palabras clave de los nuevos documentos."""
    assert document_detector.detectar_tipo_documento("PERMISO POR PROTECCION TEMPORAL MIGRACION") == "PPT"
    assert document_detector.detectar_tipo_documento("CEDULA DE EXTRANJERIA RESIDENTE") == "CEDULA_EXTRANJERIA"
    assert document_detector.detectar_tipo_documento("COMPROBANTE DE DOCUMENTO EN TRAMITE CONTRASEÑA") == "CONTRASEÑA"
    assert document_detector.detectar_tipo_documento("REPUBLICA DE COLOMBIA PASAPORTE PASSPORT") == "PASAPORTE"
