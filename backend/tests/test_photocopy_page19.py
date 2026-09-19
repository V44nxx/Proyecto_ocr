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


def test_deteccion_ti_multilinea_y_alerta_mayor_de_edad():
    extractor = ExtractorService()
    # Texto con salto de línea entre TARJETA y DE IDENTIDAD y con IDENTIFICACION PERSONAL
    texto_ti_multilinea = """
    REPÚBLICA DE COLOMBIA
    IDENTIFICACIÓN PERSONAL
    TARJETA
    DE IDENTIDAD
    NUMERO 1.005.123.456
    GOMEZ PEREZ
    JUAN CAMILO
    FECHA DE NACIMIENTO 10-MAY-2006
    """
    # Debe detectar TARJETA_IDENTIDAD y NO CEDULA_CIUDADANIA
    tipo = extractor.detectar_tipo_documento(texto_ti_multilinea)
    assert tipo == "TARJETA_IDENTIDAD"

    # Clasificador de caras debe clasificarlo como TARJETA_IDENTIDAD
    clasif = document_side_classifier.clasificar_cara(texto_ti_multilinea)
    assert clasif.get("tipo_documento") == "TARJETA_IDENTIDAD"

    # Si la persona tiene 18 años o más y tiene Tarjeta de Identidad, debe disparar la alerta
    from app.utils.validators import validador
    detalles = {}
    completo, motivos = validador.evaluar_persona_completa(
        numero_identificacion="1005123456",
        nombres="JUAN CAMILO",
        apellidos="GOMEZ PEREZ",
        nombre_completo="JUAN CAMILO GOMEZ PEREZ",
        fecha_nacimiento="2006-05-10",
        fecha_expedicion="2020-05-10",
        confianza=95.0,
        detalles_campos=detalles,
        tipo_documento=tipo
    )
    assert completo is False
    assert "discrepancia_documento_edad" in detalles
    disc = detalles["discrepancia_documento_edad"]
    assert disc["tipo"] == "MAYOR_CON_TI"
    assert "sola corresponde a menores de edad" in disc["motivo"] or "solo corresponde a menores de edad" in disc["motivo"]


def test_cero_descarte_y_sin_id_en_blanco():
    from unittest.mock import MagicMock
    from app.services.ocr_service import ocr_service
    from app.models.persona import Persona
    import uuid

    mock_db = MagicMock()
    mock_db.query().filter().first.return_value = None

    # Datos incompletos sin ID y sin nombres válidos
    datos_incompletos = {
        "grupo_documento_id": "DOC-002",
        "pagina_frente": 2,
        "pagina_reverso": None,
        "identificacion": None,
        "nombres": None,
        "apellidos": None,
        "nombre_completo": None,
        "confianza_extraccion": 40.0,
        "tipo_documento": "TARJETA_IDENTIDAD"
    }

    persona_dict = ocr_service._guardar_persona(
        datos=datos_incompletos,
        texto_ocr="Frente Pag 2 | Reverso None",
        documento_id=str(uuid.uuid4()),
        db=mock_db,
        ocr_engine="google_document_ai",
        pagina_num=2
    )

    # 1. Regla Cero Descarte: NUNCA debe retornar None
    assert persona_dict is not None
    # 2. No generar códigos artificiales SIN_ID_..., debe ser cadena vacía para edición limpia
    assert persona_dict["numero_identificacion"] == ""
    assert "SIN_ID" not in persona_dict["numero_identificacion"]
    # 3. Requiere revisión obligatoria
    assert persona_dict["requiere_revision"] is True
    assert persona_dict["estado_registro"] == "REVIEW_REQUIRED"


def test_evaluar_persona_completa_sin_id_no_genera_falsos_6_digitos():
    from app.utils.validators import validador

    completo, motivos = validador.evaluar_persona_completa(
        numero_identificacion="",
        nombres="NADIA YULIETH",
        apellidos="QUIÑONES GOMEZ",
        nombre_completo="NADIA YULIETH QUIÑONES GOMEZ",
        fecha_nacimiento="2010-01-13",
        fecha_expedicion="2017-06-29",
        confianza=80.0,
        tipo_documento="TARJETA_IDENTIDAD"
    )

    assert completo is False
    assert any("no detectado" in m for m in motivos)
    # NUNCA debe decir "Muy corto (6 dígitos)" por códigos hexadecimales de UUID
    assert not any("Muy corto (6 dígitos)" in m for m in motivos)
    assert not any("dudoso" in m for m in motivos)



