"""
Pruebas Unitarias para el Modo Smart Dual OCR (Opción A).
Verifica:
1. Fast-Path activo cuando DocAI extrae una cédula completa y confiable -> motor 'google_document_ai'.
2. Rescate activo por RapidOCR cuando DocAI tiene datos incompletos o solo encabezados -> motor 'google_document_ai+rapid_ocr'.
3. Fusión de textos enriquecida entre ambos motores.
4. Trazabilidad del motor real guardado en base de datos.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from app.services.ocr_service import ocr_service, OCRService
from app.services.google_document_ai_service import StructuredDocumentAIResult, OCRPageData, OCRLine
from app.services.document_pairing_service import DocumentGroup


TEXTO_COMPLETO_CEDULA = """
REPÚBLICA DE COLOMBIA
IDENTIFICACIÓN PERSONAL
CÉDULA DE CIUDADANÍA
NÚMERO 1.006.501.709
APELLIDOS
PEREZ GOMEZ
NOMBRES
JUAN CARLOS
FECHA DE NACIMIENTO 15-MAR-1990
SEXO M
"""

TEXTO_INCOMPLETO_SOLO_HEADER = """
REPÚBLICA DE COLOMBIA
IDENTIFICACIÓN PERSONAL
CÉDULA DE CIUDADANÍA
"""

TEXTO_RESCATADO_RAPID = """
NÚMERO 1006501709
NOMBRES JUAN CARLOS
APELLIDOS PEREZ GOMEZ
"""


def test_evaluacion_docai_completa_con_cedula_valida():
    """Valida que una cédula completa sea reconocida como completa por el Fast-Path."""
    lines = [
        OCRLine(text="REPÚBLICA DE COLOMBIA", confidence=0.98, page_number=1, x=0.1, y=0.1, w=0.8, h=0.05),
        OCRLine(text="NÚMERO 1.006.501.709", confidence=0.97, page_number=1, x=0.1, y=0.2, w=0.5, h=0.05),
        OCRLine(text="JUAN CARLOS PEREZ GOMEZ", confidence=0.96, page_number=1, x=0.1, y=0.3, w=0.6, h=0.05),
    ]
    p_data = OCRPageData(page_number=1, width=800, height=600, text=TEXTO_COMPLETO_CEDULA, lines=lines)
    struct_res = StructuredDocumentAIResult(text=TEXTO_COMPLETO_CEDULA, tiempo_ms=450.0, pages=[p_data])

    completo, motivo = ocr_service._es_extraccion_docai_completa(TEXTO_COMPLETO_CEDULA, struct_res, pagina_num=1)
    assert completo is True
    assert "1006501709" in motivo


def test_evaluacion_docai_incompleta_solo_header():
    """Valida que solo tener el encabezado sin número de cédula NO active el Fast-Path."""
    lines = [
        OCRLine(text="REPÚBLICA DE COLOMBIA", confidence=0.95, page_number=1, x=0.1, y=0.1, w=0.8, h=0.05),
        OCRLine(text="IDENTIFICACIÓN PERSONAL", confidence=0.95, page_number=1, x=0.1, y=0.15, w=0.8, h=0.05),
    ]
    p_data = OCRPageData(page_number=1, width=800, height=600, text=TEXTO_INCOMPLETO_SOLO_HEADER, lines=lines)
    struct_res = StructuredDocumentAIResult(text=TEXTO_INCOMPLETO_SOLO_HEADER, tiempo_ms=400.0, pages=[p_data])

    completo, motivo = ocr_service._es_extraccion_docai_completa(TEXTO_INCOMPLETO_SOLO_HEADER, struct_res, pagina_num=1)
    assert completo is False
    assert "Sin número de identificación" in motivo


def test_ocr_imagen_activa_rescate_rapid_cuando_docai_incompleto():
    """
    Verifica que si DocAI devuelve texto incompleto, _ocr_imagen ejecuta RapidOCR
    y retorna el motor fusionado 'google_document_ai+rapid_ocr'.
    """
    servicio = OCRService()
    img_fake = np.ones((400, 600, 3), dtype=np.uint8) * 255

    mock_docai_res = StructuredDocumentAIResult(
        text=TEXTO_INCOMPLETO_SOLO_HEADER,
        tiempo_ms=350.0,
        pages=[OCRPageData(page_number=1, width=600, height=400, text=TEXTO_INCOMPLETO_SOLO_HEADER, lines=[])]
    )

    mock_rapid_res = StructuredDocumentAIResult(
        text=TEXTO_RESCATADO_RAPID,
        tiempo_ms=500.0,
        pages=[OCRPageData(page_number=1, width=600, height=400, text=TEXTO_RESCATADO_RAPID, lines=[])]
    )

    with patch("app.services.ocr_service.google_document_ai_service") as mock_gdoc, \
         patch("app.services.ocr_service.rapid_ocr_service") as mock_rapid, \
         patch("cv2.imencode", return_value=(True, MagicMock(tobytes=lambda: b"fake_jpeg"))):

        mock_gdoc.disponible = True
        mock_gdoc.procesar_documento_estructurado.return_value = mock_docai_res

        mock_rapid.disponible = True
        mock_rapid.procesar_imagen.return_value = (TEXTO_RESCATADO_RAPID, 92.0, mock_rapid_res)

        texto_final, motor_final, struct_final = servicio._ocr_imagen(img_fake, pagina_num=1)

        # Debe haber ejecutado RapidOCR como rescate
        mock_rapid.procesar_imagen.assert_called_once()
        assert motor_final == "google_document_ai+rapid_ocr"
        # El texto fusionado debe tener la cédula rescatada
        assert "1006501709" in texto_final
        assert "REPÚBLICA DE COLOMBIA" in texto_final


def test_ocr_imagen_fast_path_omite_rapid_cuando_docai_completo():
    """
    Verifica que si DocAI devuelve la cédula completa y confiable,
    RapidOCR NO se ejecuta y se retorna 'google_document_ai' de inmediato.
    """
    servicio = OCRService()
    img_fake = np.ones((400, 600, 3), dtype=np.uint8) * 255

    lines = [
        OCRLine(text="REPÚBLICA DE COLOMBIA", confidence=0.98, page_number=1, x=0.1, y=0.1, w=0.8, h=0.05),
        OCRLine(text="NÚMERO 1006501709", confidence=0.97, page_number=1, x=0.1, y=0.2, w=0.5, h=0.05),
        OCRLine(text="NOMBRES JUAN CARLOS", confidence=0.96, page_number=1, x=0.1, y=0.3, w=0.6, h=0.05),
        OCRLine(text="APELLIDOS PEREZ GOMEZ", confidence=0.96, page_number=1, x=0.1, y=0.4, w=0.6, h=0.05),
    ]
    mock_docai_res = StructuredDocumentAIResult(
        text=TEXTO_COMPLETO_CEDULA,
        tiempo_ms=300.0,
        pages=[OCRPageData(page_number=1, width=600, height=400, text=TEXTO_COMPLETO_CEDULA, lines=lines)]
    )

    with patch("app.services.ocr_service.google_document_ai_service") as mock_gdoc, \
         patch("app.services.ocr_service.rapid_ocr_service") as mock_rapid, \
         patch("cv2.imencode", return_value=(True, MagicMock(tobytes=lambda: b"fake_jpeg"))):

        mock_gdoc.disponible = True
        mock_gdoc.procesar_documento_estructurado.return_value = mock_docai_res

        mock_rapid.disponible = True

        texto_final, motor_final, struct_final = servicio._ocr_imagen(img_fake, pagina_num=1)

        # En Fast-Path, RapidOCR NO debe ser invocado
        mock_rapid.procesar_imagen.assert_not_called()
        assert motor_final == "google_document_ai"


def test_trazabilidad_motor_en_grupo_y_persona():
    """
    Verifica que si una página fue procesada con 'google_document_ai+rapid_ocr',
    el grupo y la persona guarden ese motor exacto.
    """
    servicio = OCRService()
    grp = DocumentGroup("DOC-999")
    grp.front_page = {
        "pagina_numero": 1,
        "texto": TEXTO_COMPLETO_CEDULA,
        "motor": "google_document_ai+rapid_ocr",
        "cara": "CEDULA_FRONT",
        "tipo_documento": "CEDULA_CIUDADANIA",
        "confianza": 0.95,
        "numero_identificacion": "1006501709",
    }
    grp.back_page = None

    # Simular resolución de motor
    motores_grp = set()
    if grp.front_page and grp.front_page.get("motor"):
        motores_grp.add(grp.front_page["motor"])

    assert "google_document_ai+rapid_ocr" in motores_grp

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    persona_dict = servicio._guardar_persona(
        datos={
            "identificacion": "1006501709",
            "nombres": "JUAN CARLOS",
            "apellidos": "PEREZ GOMEZ",
            "tipo_documento": "CEDULA_CIUDADANIA",
            "confianza_extraccion": 95.0,
            "detalles_campos": {},
        },
        texto_ocr="test",
        documento_id="doc-123",
        db=mock_db,
        ocr_engine="google_document_ai+rapid_ocr",
        pagina_num=1
    )

    assert persona_dict is not None
    assert persona_dict["motor_ocr"] == "google_document_ai+rapid_ocr"

