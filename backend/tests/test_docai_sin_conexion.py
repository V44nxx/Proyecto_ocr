"""
Sin internet (ej. el proyecto corriendo en un portátil sin red), el OCR pasa directo a RapidOCR:
no se espera a que Document AI falle en cada página.
"""
import socket
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.google_document_ai_service import GoogleDocumentAIService


@pytest.fixture
def servicio():
    with patch.object(GoogleDocumentAIService, "_inicializar", lambda self: None):
        s = GoogleDocumentAIService()
    s._disponible = True
    s._endpoint = "us-documentai.googleapis.com"
    s._client = MagicMock()
    return s


def test_sin_red_no_esta_en_linea_y_no_vuelve_a_probar_enseguida(servicio):
    with patch("socket.create_connection", side_effect=socket.gaierror("sin red")) as conectar:
        assert servicio.en_linea() is False
        assert servicio.en_linea() is False
    assert conectar.call_count == 1                                    # el resultado se recuerda


def test_con_red_esta_en_linea_y_no_prueba_en_cada_pagina(servicio):
    with patch("socket.create_connection") as conectar:
        assert servicio.en_linea() is True
        assert servicio.en_linea() is True
    assert conectar.call_count == 1


def test_vuelve_a_probar_cuando_pasa_el_tiempo(servicio, monkeypatch):
    with patch("socket.create_connection", side_effect=OSError("sin red")):
        assert servicio.en_linea() is False
    servicio._sin_conexion_hasta = 0.0                                 # pasó el tiempo
    with patch("socket.create_connection"):
        assert servicio.en_linea() is True


def test_deshabilitado_nunca_esta_en_linea(servicio):
    servicio._disponible = False
    with patch("socket.create_connection") as conectar:
        assert servicio.en_linea() is False
    conectar.assert_not_called()


def test_errores_de_conexion():
    from google.api_core import exceptions as gexc
    assert GoogleDocumentAIService.es_error_de_conexion(gexc.ServiceUnavailable("x"))
    assert GoogleDocumentAIService.es_error_de_conexion(gexc.DeadlineExceeded("x"))
    assert GoogleDocumentAIService.es_error_de_conexion(OSError("x"))
    assert not GoogleDocumentAIService.es_error_de_conexion(gexc.InvalidArgument("x"))
    assert not GoogleDocumentAIService.es_error_de_conexion(ValueError("x"))


def test_la_llamada_tiene_tiempo_maximo(servicio):
    servicio._processor_name = "projects/p/locations/us/processors/x"
    servicio._client.process_document.return_value = MagicMock(document=MagicMock(text="", pages=[]))
    servicio.procesar_documento_estructurado(b"x", mime_type="image/jpeg")
    assert servicio._client.process_document.call_args.kwargs["timeout"] > 0


def test_ocr_sin_conexion_va_directo_a_rapidocr(servicio):
    from app.services.ocr_service import ocr_service

    img = np.full((100, 100, 3), 255, dtype=np.uint8)
    with patch("app.services.ocr_service.google_document_ai_service", servicio), \
         patch("app.services.ocr_service.rapid_ocr_service") as rapid, \
         patch("socket.create_connection", side_effect=OSError("sin red")):
        rapid.disponible = True
        rapid.procesar_imagen.return_value = ("REPUBLICA DE COLOMBIA CEDULA DE CIUDADANIA NUMERO 1003218765", 0.95, None)
        texto, motor, _ = ocr_service._ocr_imagen(img, pagina_num=1)
        ocr_service._ocr_imagen(img, pagina_num=2)

    assert motor != "google_document_ai"
    servicio._client.process_document.assert_not_called()             # ni siquiera se intentó


def test_un_error_de_red_en_una_pagina_salta_document_ai_en_las_siguientes(servicio):
    from google.api_core import exceptions as gexc
    from app.services.ocr_service import ocr_service

    servicio._processor_name = "projects/p/locations/us/processors/x"
    servicio._client.process_document.side_effect = gexc.ServiceUnavailable("se cayó la red")
    img = np.full((100, 100, 3), 255, dtype=np.uint8)
    with patch("app.services.ocr_service.google_document_ai_service", servicio), \
         patch("app.services.ocr_service.rapid_ocr_service") as rapid, \
         patch("socket.create_connection"):
        rapid.disponible = True
        rapid.procesar_imagen.return_value = ("REPUBLICA DE COLOMBIA CEDULA DE CIUDADANIA", 0.95, None)
        for pagina in (1, 2, 3):
            ocr_service._ocr_imagen(img, pagina_num=pagina)

    assert servicio._client.process_document.call_count == 1
