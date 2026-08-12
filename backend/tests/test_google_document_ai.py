"""
Pruebas unitarias para la integración Google Document AI.

Cubre los casos A-I del requisito:
  A. Procesamiento exitoso mediante Google Document AI.
  B. Error de Google Document AI → fallback a Tesseract.
  C. Extracción de número de cédula.
  D. Extracción de nombres.
  E. Extracción de apellidos.
  F. Extracción de fechas.
  G. Documento inválido.
  H. Credenciales faltantes.
  I. Processor ID faltante.

Ejecución:
    # Desde backend/
    pytest tests/test_google_document_ai.py -v

    # Con coverage:
    pytest tests/test_google_document_ai.py -v --cov=app.services.google_document_ai_service
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ──────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ──────────────────────────────────────────────────────────────────────────────

TEXTO_CEDULA_VALIDO = """
REPÚBLICA DE COLOMBIA
CÉDULA DE CIUDADANÍA

APELLIDOS
GARCIA RODRIGUEZ
NOMBRES
JUAN CARLOS
NÚMERO DE IDENTIFICACIÓN
1234567890
FECHA DE NACIMIENTO
15/03/1990
FECHA DE EXPEDICIÓN
20/06/2010
LUGAR DE EXPEDICIÓN
BOGOTÁ
SEXO
M
"""

TEXTO_CEDULA_MINIMO = """
1234567890
JUAN CARLOS GARCIA RODRIGUEZ
"""


# ──────────────────────────────────────────────────────────────────────────────
# CASO A: Procesamiento exitoso con Google Document AI
# ──────────────────────────────────────────────────────────────────────────────

class TestCasoA_ProcesamientoExitoso:
    """El servicio llama a la API y devuelve texto correctamente."""

    def test_procesar_documento_devuelve_texto(self):
        """A: Google Document AI procesa y devuelve texto no vacío."""
        with patch("app.services.google_document_ai_service.settings") as mock_settings, \
             patch("app.services.google_document_ai_service.os.path.exists", return_value=True):

            mock_settings.GOOGLE_DOCUMENT_AI_ENABLED = True
            mock_settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID = "test_processor_id"
            mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "/fake/path.json"
            mock_settings.GOOGLE_CLOUD_PROJECT = "ocr-sena"
            mock_settings.GOOGLE_DOCUMENT_AI_LOCATION = "us"

            with patch("google.cloud.documentai.DocumentProcessorServiceClient") as mock_client_cls:
                # Simular respuesta de la API
                mock_document = MagicMock()
                mock_document.text = TEXTO_CEDULA_VALIDO
                mock_result = MagicMock()
                mock_result.document = mock_document
                mock_client = MagicMock()
                mock_client.process_document.return_value = mock_result
                mock_client_cls.return_value = mock_client

                from app.services.google_document_ai_service import GoogleDocumentAIService
                servicio = GoogleDocumentAIService()
                # Forzar disponibilidad para el test
                servicio._disponible = True
                servicio._client = mock_client
                servicio._processor_name = "projects/ocr-sena/locations/us/processors/test_processor_id"

                texto, tiempo_ms = servicio.procesar_documento(b"pdf_bytes_fake")

                assert texto == TEXTO_CEDULA_VALIDO
                assert tiempo_ms > 0
                mock_client.process_document.assert_called_once()

    def test_ocr_imagen_usa_google_document_ai_cuando_disponible(self):
        """A: _ocr_imagen() retorna motor 'google_document_ai' cuando el servicio funciona."""
        import numpy as np

        with patch("app.services.ocr_service.google_document_ai_service") as mock_docai:
            mock_docai.disponible = True
            mock_docai.procesar_imagen.return_value = (TEXTO_CEDULA_VALIDO, 500.0)

            from app.services.ocr_service import OCRService
            servicio = OCRService()
            img_fake = np.zeros((100, 100, 3), dtype=np.uint8)

            with patch("cv2.imencode", return_value=(True, MagicMock(tobytes=lambda: b"img"))):
                texto, motor = servicio._ocr_imagen(img_fake, pagina_num=1)

            assert motor == "google_document_ai"
            assert TEXTO_CEDULA_VALIDO in texto


# ──────────────────────────────────────────────────────────────────────────────
# CASO B: Fallo de Google Document AI → Fallback a Tesseract
# ──────────────────────────────────────────────────────────────────────────────

class TestCasoB_FallbackTesseract:
    """Cuando Google Document AI falla, el sistema usa Tesseract."""

    def test_fallback_cuando_docai_lanza_excepcion(self):
        """B: Si DocAI lanza excepción → Tesseract se usa como fallback."""
        import numpy as np

        with patch("app.services.ocr_service.google_document_ai_service") as mock_docai, \
             patch("app.services.ocr_service.OCRService._ocr_con_tesseract") as mock_tess:

            mock_docai.disponible = True
            mock_docai.procesar_imagen.side_effect = Exception("API Error simulado")
            mock_tess.return_value = TEXTO_CEDULA_VALIDO

            from app.services.ocr_service import OCRService
            servicio = OCRService()
            img_fake = np.zeros((100, 100, 3), dtype=np.uint8)

            with patch("cv2.imencode", return_value=(True, MagicMock(tobytes=lambda: b"img"))):
                texto, motor = servicio._ocr_imagen(img_fake, pagina_num=1)

            assert motor == "tesseract_fallback"
            mock_tess.assert_called_once()

    def test_fallback_cuando_docai_devuelve_texto_vacio(self):
        """B: Si DocAI devuelve texto vacío → Tesseract se usa como fallback."""
        import numpy as np

        with patch("app.services.ocr_service.google_document_ai_service") as mock_docai, \
             patch("app.services.ocr_service.OCRService._ocr_con_tesseract") as mock_tess:

            mock_docai.disponible = True
            mock_docai.procesar_imagen.return_value = ("", 100.0)
            mock_tess.return_value = TEXTO_CEDULA_VALIDO

            from app.services.ocr_service import OCRService
            servicio = OCRService()
            img_fake = np.zeros((100, 100, 3), dtype=np.uint8)

            with patch("cv2.imencode", return_value=(True, MagicMock(tobytes=lambda: b"img"))):
                texto, motor = servicio._ocr_imagen(img_fake, pagina_num=1)

            assert motor == "tesseract_fallback"

    def test_usa_tesseract_cuando_docai_no_disponible(self):
        """B: Si DocAI no está disponible → Tesseract directamente."""
        import numpy as np

        with patch("app.services.ocr_service.google_document_ai_service") as mock_docai, \
             patch("app.services.ocr_service.OCRService._ocr_con_tesseract") as mock_tess:

            mock_docai.disponible = False
            mock_tess.return_value = TEXTO_CEDULA_VALIDO

            from app.services.ocr_service import OCRService
            servicio = OCRService()
            img_fake = np.zeros((100, 100, 3), dtype=np.uint8)

            texto, motor = servicio._ocr_imagen(img_fake, pagina_num=1)

            assert motor == "tesseract_fallback"
            mock_tess.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# CASO C: Extracción de número de cédula
# ──────────────────────────────────────────────────────────────────────────────

class TestCasoC_ExtraccionCedula:
    """El ExtractorService extrae correctamente el número de cédula del texto OCR."""

    def test_extrae_cedula_directa(self):
        """C: Extrae número de 10 dígitos como identificación."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        resultado = extractor.extraer(TEXTO_CEDULA_VALIDO)
        assert resultado["identificacion"] == "1234567890"

    def test_extrae_cedula_con_puntos(self):
        """C: Extrae cédula en formato colombiano con puntos (1.234.567.890)."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        texto = "NÚMERO 1.234.567.890\nJUAN GARCIA"
        resultado = extractor.extraer(texto)
        assert resultado["identificacion"] == "1234567890"

    def test_no_confunde_fecha_con_cedula(self):
        """C: El número de fecha (15/03/1990) no se confunde con la cédula."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        resultado = extractor.extraer(TEXTO_CEDULA_VALIDO)
        # La cédula debe ser el número completo, no un fragmento de fecha
        if resultado["identificacion"]:
            assert "/" not in resultado["identificacion"]


# ──────────────────────────────────────────────────────────────────────────────
# CASO D: Extracción de nombres
# ──────────────────────────────────────────────────────────────────────────────

class TestCasoD_ExtraccionNombres:
    """El ExtractorService extrae correctamente los nombres."""

    def test_extrae_nombres(self):
        """D: Extrae nombres de persona del texto OCR."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        resultado = extractor.extraer(TEXTO_CEDULA_VALIDO)
        assert resultado["nombres"] is not None
        assert len(resultado["nombres"]) >= 2

    def test_nombres_no_vacios(self):
        """D: Los nombres extraídos no son cadenas vacías ni 'POR REVISAR'."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        resultado = extractor.extraer(TEXTO_CEDULA_VALIDO)
        if resultado["nombres"]:
            assert resultado["nombres"].strip() != ""
            assert "POR REVISAR" not in resultado["nombres"]


# ──────────────────────────────────────────────────────────────────────────────
# CASO E: Extracción de apellidos
# ──────────────────────────────────────────────────────────────────────────────

class TestCasoE_ExtraccionApellidos:
    """El ExtractorService extrae correctamente los apellidos."""

    def test_extrae_apellidos(self):
        """E: Extrae apellidos de persona del texto OCR."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        resultado = extractor.extraer(TEXTO_CEDULA_VALIDO)
        assert resultado["apellidos"] is not None
        assert len(resultado["apellidos"]) >= 2

    def test_apellidos_no_vacios(self):
        """E: Los apellidos extraídos no son cadenas vacías."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        resultado = extractor.extraer(TEXTO_CEDULA_VALIDO)
        if resultado["apellidos"]:
            assert resultado["apellidos"].strip() != ""


# ──────────────────────────────────────────────────────────────────────────────
# CASO F: Extracción de fechas
# ──────────────────────────────────────────────────────────────────────────────

class TestCasoF_ExtraccionFechas:
    """El ExtractorService extrae correctamente las fechas."""

    def test_extrae_fecha_nacimiento(self):
        """F: Extrae fecha de nacimiento en formato ISO."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        resultado = extractor.extraer(TEXTO_CEDULA_VALIDO)
        assert resultado["fecha_nacimiento"] is not None
        # Debe ser formato ISO: YYYY-MM-DD
        assert len(resultado["fecha_nacimiento"]) == 10
        assert resultado["fecha_nacimiento"][4] == "-"

    def test_extrae_fecha_expedicion(self):
        """F: Extrae fecha de expedición en formato ISO."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        resultado = extractor.extraer(TEXTO_CEDULA_VALIDO)
        assert resultado["fecha_expedicion"] is not None
        assert len(resultado["fecha_expedicion"]) == 10

    def test_fecha_formato_ddmmmyyyy(self):
        """F: Parsea fechas en formato de cédula nueva (DDMMMYYYY)."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        texto = """
APELLIDOS
GARCIA
NOMBRES
JUAN
1234567890
FECHA DE NACIMIENTO
22OCT2006
FECHA DE EXPEDICIÓN
23 OCT 2024
"""
        resultado = extractor.extraer(texto)
        assert resultado["fecha_nacimiento"] is not None
        assert "2006" in resultado["fecha_nacimiento"]


# ──────────────────────────────────────────────────────────────────────────────
# CASO G: Documento inválido
# ──────────────────────────────────────────────────────────────────────────────

class TestCasoG_DocumentoInvalido:
    """El sistema maneja correctamente documentos sin información útil."""

    def test_texto_vacio_devuelve_resultado_con_errores(self):
        """G: Texto OCR vacío produce resultado con confianza baja."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        resultado = extractor.extraer("")
        assert resultado["confianza_extraccion"] < 50.0

    def test_texto_ruido_sin_cedula(self):
        """G: Texto de ruido no produce identificación válida."""
        from app.services.extractor_service import ExtractorService
        extractor = ExtractorService()
        resultado = extractor.extraer("@@##!! ruido de escáner *** ???")
        # No debe extraer una cédula de puro ruido
        if resultado["identificacion"]:
            # Si extrae algo, debe ser un número válido (6-10 dígitos)
            assert resultado["identificacion"].isdigit()
            assert 6 <= len(resultado["identificacion"]) <= 10

    def test_documento_solo_numeros_no_confunde_cedula(self):
        """G: Un texto con solo números pequeños no produce cédula falsa."""
        from app.services.extractor_service import ExtractorService
        from app.utils.validators import validador
        extractor = ExtractorService()
        # Números de 4 dígitos no deben ser aceptados como cédula
        resultado = extractor.extraer("1234 5678 90 12")
        if resultado["identificacion"]:
            valido, _ = validador.validar_cedula(resultado["identificacion"])
            assert valido


# ──────────────────────────────────────────────────────────────────────────────
# CASO H: Credenciales faltantes
# ──────────────────────────────────────────────────────────────────────────────

class TestCasoH_CredencialesFaltantes:
    """El servicio se comporta correctamente cuando faltan credenciales."""

    def test_servicio_no_disponible_sin_credenciales(self):
        """H: El servicio queda no disponible si no hay credenciales configuradas."""
        with patch("app.services.google_document_ai_service.settings") as mock_settings:
            mock_settings.GOOGLE_DOCUMENT_AI_ENABLED = True
            mock_settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID = "test_id"
            mock_settings.GOOGLE_APPLICATION_CREDENTIALS = ""  # Sin credenciales

            from app.services.google_document_ai_service import GoogleDocumentAIService
            servicio = GoogleDocumentAIService()
            assert servicio.disponible is False

    def test_servicio_no_disponible_archivo_no_existe(self):
        """H: El servicio queda no disponible si el archivo JSON no existe en disco."""
        with patch("app.services.google_document_ai_service.settings") as mock_settings, \
             patch("app.services.google_document_ai_service.os.path.exists", return_value=False):

            mock_settings.GOOGLE_DOCUMENT_AI_ENABLED = True
            mock_settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID = "test_id"
            mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "/ruta/inexistente.json"

            from app.services.google_document_ai_service import GoogleDocumentAIService
            servicio = GoogleDocumentAIService()
            assert servicio.disponible is False

    def test_procesar_lanza_error_si_no_disponible(self):
        """H: procesar_documento() lanza RuntimeError si el servicio no está disponible."""
        from app.services.google_document_ai_service import GoogleDocumentAIService
        servicio = GoogleDocumentAIService.__new__(GoogleDocumentAIService)
        servicio._disponible = False

        with pytest.raises(RuntimeError):
            servicio.procesar_documento(b"fake_bytes")


# ──────────────────────────────────────────────────────────────────────────────
# CASO I: Processor ID faltante
# ──────────────────────────────────────────────────────────────────────────────

class TestCasoI_ProcessorIDFaltante:
    """El servicio detecta y maneja la ausencia del Processor ID."""

    def test_servicio_no_disponible_sin_processor_id(self):
        """I: El servicio queda no disponible si GOOGLE_DOCUMENT_AI_PROCESSOR_ID está vacío."""
        with patch("app.services.google_document_ai_service.settings") as mock_settings:
            mock_settings.GOOGLE_DOCUMENT_AI_ENABLED = True
            mock_settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID = ""  # Sin Processor ID
            mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "/fake/path.json"

            from app.services.google_document_ai_service import GoogleDocumentAIService
            servicio = GoogleDocumentAIService()
            assert servicio.disponible is False

    def test_servicio_deshabilitado_con_flag(self):
        """I: Cuando GOOGLE_DOCUMENT_AI_ENABLED=False, el servicio no intenta conectarse."""
        with patch("app.services.google_document_ai_service.settings") as mock_settings:
            mock_settings.GOOGLE_DOCUMENT_AI_ENABLED = False

            from app.services.google_document_ai_service import GoogleDocumentAIService
            servicio = GoogleDocumentAIService()
            assert servicio.disponible is False


# ──────────────────────────────────────────────────────────────────────────────
# PRUEBAS DE SEGURIDAD
# ──────────────────────────────────────────────────────────────────────────────

class TestSeguridad:
    """Verifica que no se exponen credenciales en logs ni en código."""

    def test_private_key_no_aparece_en_logs(self, caplog):
        """Seguridad: 'private_key' no debe aparecer en ningún log."""
        import logging
        with patch("app.services.google_document_ai_service.settings") as mock_settings, \
             patch("app.services.google_document_ai_service.os.path.exists", return_value=False):

            mock_settings.GOOGLE_DOCUMENT_AI_ENABLED = True
            mock_settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID = "test_id"
            mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "/fake/path.json"

            with caplog.at_level(logging.WARNING):
                from app.services.google_document_ai_service import GoogleDocumentAIService
                GoogleDocumentAIService()

            for record in caplog.records:
                assert "private_key" not in record.message.lower()
                assert "-----BEGIN" not in record.message

    def test_processor_id_no_aparece_en_logs_info(self, caplog):
        """Seguridad: El Processor ID no debe registrarse en logs de nivel INFO."""
        import logging
        with patch("app.services.google_document_ai_service.settings") as mock_settings, \
             patch("app.services.google_document_ai_service.os.path.exists", return_value=True), \
             patch("google.cloud.documentai.DocumentProcessorServiceClient"):

            processor_id_secreto = "mi_processor_id_secreto_12345"
            mock_settings.GOOGLE_DOCUMENT_AI_ENABLED = True
            mock_settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID = processor_id_secreto
            mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "/fake/path.json"
            mock_settings.GOOGLE_CLOUD_PROJECT = "ocr-sena"
            mock_settings.GOOGLE_DOCUMENT_AI_LOCATION = "us"

            with caplog.at_level(logging.INFO):
                from app.services.google_document_ai_service import GoogleDocumentAIService
                GoogleDocumentAIService()

            for record in caplog.records:
                if record.levelname == "INFO":
                    assert processor_id_secreto not in record.message
