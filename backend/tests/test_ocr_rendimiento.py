"""
Velocidad del OCR sin cambiar lo que lee:
  - con Document AI casi todo el tiempo es esperar a Google, así que se leen más páginas a la vez;
  - si Google responde que se pasó el límite de solicitudes (429), se espera y se reintenta, en vez de leer
    esa página con RapidOCR, que lee peor.
"""
import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.google_document_ai_service import GoogleDocumentAIService
from app.services.ocr_service import ocr_service


@pytest.fixture
def servicio():
    with patch.object(GoogleDocumentAIService, "_inicializar", lambda self: None):
        s = GoogleDocumentAIService()
    s._disponible = True
    s._endpoint = "us-documentai.googleapis.com"
    s._processor_name = "projects/p/locations/us/processors/x"
    s._client = MagicMock()
    return s


def _respuesta(texto="REPUBLICA DE COLOMBIA"):
    return MagicMock(document=MagicMock(text=texto, pages=[]))


def test_limite_de_solicitudes_se_reintenta_y_no_pasa_a_rapidocr(servicio, monkeypatch):
    from google.api_core import exceptions as gexc
    esperas = []
    monkeypatch.setattr("app.services.google_document_ai_service.time.sleep", esperas.append)
    servicio._client.process_document.side_effect = [gexc.ResourceExhausted("cuota"), gexc.TooManyRequests("429"),
                                                      _respuesta()]
    resultado = servicio.procesar_documento_estructurado(b"x", mime_type="image/jpeg")

    assert "COLOMBIA" in resultado.text
    assert servicio._client.process_document.call_count == 3
    assert esperas and all(e > 0 for e in esperas) and esperas == sorted(esperas)   # esperas crecientes


def test_si_el_limite_sigue_se_rinde_y_lo_deja_a_rapidocr(servicio, monkeypatch):
    from google.api_core import exceptions as gexc
    monkeypatch.setattr("app.services.google_document_ai_service.time.sleep", lambda s: None)
    servicio._client.process_document.side_effect = gexc.ResourceExhausted("cuota")
    with pytest.raises(gexc.ResourceExhausted):
        servicio.procesar_documento_estructurado(b"x", mime_type="image/jpeg")
    assert servicio._client.process_document.call_count == 1 + len(GoogleDocumentAIService.ESPERAS_LIMITE_SOLICITUDES)


def test_otros_errores_no_se_reintentan(servicio, monkeypatch):
    from google.api_core import exceptions as gexc
    monkeypatch.setattr("app.services.google_document_ai_service.time.sleep", lambda s: None)
    servicio._client.process_document.side_effect = gexc.InvalidArgument("imagen dañada")
    with pytest.raises(gexc.InvalidArgument):
        servicio.procesar_documento_estructurado(b"x", mime_type="image/jpeg")
    assert servicio._client.process_document.call_count == 1


def test_con_document_ai_se_leen_mas_paginas_a_la_vez(monkeypatch):
    monkeypatch.setattr("os.cpu_count", lambda: 2)                 # el VPS de producción
    with patch("app.services.ocr_service.google_document_ai_service") as docai:
        docai.disponible = True
        docai.en_linea.return_value = True
        con_docai = ocr_service._paginas_en_paralelo(40)
        docai.en_linea.return_value = False
        sin_docai = ocr_service._paginas_en_paralelo(40)
    assert con_docai == ocr_service.PAGINAS_EN_PARALELO_DOCAI > sin_docai == 2
    with patch("app.services.ocr_service.google_document_ai_service") as docai:
        docai.disponible = True
        docai.en_linea.return_value = True
        assert ocr_service._paginas_en_paralelo(1) == 1


def test_rapidocr_no_corre_en_mas_hilos_que_nucleos(monkeypatch):
    from app.services.rapid_ocr_service import rapid_ocr_service
    en_curso, maximo, candado = [0], [0], threading.Lock()

    def motor(img):
        with candado:
            en_curso[0] += 1
            maximo[0] = max(maximo[0], en_curso[0])
        time.sleep(0.05)
        with candado:
            en_curso[0] -= 1
        return [], [0.0]

    monkeypatch.setattr(rapid_ocr_service, "_engine", motor)
    monkeypatch.setattr(rapid_ocr_service, "_disponible", True)
    img = np.full((50, 50, 3), 250, dtype=np.uint8)
    hilos = [threading.Thread(target=rapid_ocr_service.procesar_imagen, args=(img,)) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert maximo[0] <= rapid_ocr_service.LECTURAS_A_LA_VEZ
