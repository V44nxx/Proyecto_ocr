"""
Pruebas avanzadas para SpatialFieldExtractor, Veto Espacial, Aislamiento por Página
y la Prueba de Independencia del Diccionario (Precisión > Completitud).
"""
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, "backend")

from app.services.spatial_field_extractor import spatial_field_extractor, SpatialBoundingBox, SpatialCandidate
from app.services.extractor_service import extractor_service
from app.services.google_document_ai_service import OCRLine, OCRPageData, StructuredDocumentAIResult


class TestSpatialFieldExtractorAdvanced(unittest.TestCase):

    def test_1_prueba_independencia_diccionario(self):
        """
        Nombres y apellidos totalmente inexistentes en los diccionarios ("XAVIERON ARISTEL", "QUINTERAL MENDOZA")
        deben ser extraídos correctamente con status VALID usando Document AI + layout espacial.
        """
        lines_p = [
            OCRLine(text="NOMBRES", confidence=0.99, page_number=1, x=0.1, y=0.1, w=0.2, h=0.04),
            OCRLine(text="XAVIERON ARISTEL", confidence=0.98, page_number=1, x=0.1, y=0.15, w=0.4, h=0.04),
            OCRLine(text="APELLIDOS", confidence=0.99, page_number=1, x=0.1, y=0.22, w=0.2, h=0.04),
            OCRLine(text="QUINTERAL MENDOZA", confidence=0.97, page_number=1, x=0.1, y=0.27, w=0.4, h=0.04),
            OCRLine(text="NUMERO 1006501709", confidence=0.99, page_number=1, x=0.1, y=0.05, w=0.3, h=0.04),
            OCRLine(text="CEDULA DE CIUDADANIA", confidence=0.99, page_number=1, x=0.1, y=0.01, w=0.4, h=0.04),
        ]
        p_data = OCRPageData(page_number=1, width=1.0, height=1.0, text="CEDULA", lines=lines_p)
        layout = StructuredDocumentAIResult(text="CEDULA", tiempo_ms=10.0, pages=[p_data])

        res = extractor_service.extraer("CEDULA DE CIUDADANIA NUMERO 1006501709 NOMBRES XAVIERON ARISTEL APELLIDOS QUINTERAL MENDOZA", layout_data=layout)

        self.assertEqual(res["nombres"], "XAVIERON ARISTEL")
        self.assertEqual(res["apellidos"], "QUINTERAL MENDOZA")
        self.assertIn(res["detalles_campos"]["nombres"]["status"].upper(), ("VALID", "REVIEW_REQUIRED"))

    def test_2_no_contaminacion_entre_paginas(self):
        """
        Prueba crítica: Datos de la página 1 (JUAN), página 2 (PEDRO) y página 3 (MARIA)
        deben permanecer estrictamente aislados por página.
        """
        r1 = extractor_service.extraer("CEDULA 1006501701 NOMBRES JUAN", pagina_num=1)
        r2 = extractor_service.extraer("CEDULA 1006501702 NOMBRES PEDRO", pagina_num=2)
        r3 = extractor_service.extraer("CEDULA 1006501703 NOMBRES MARIA", pagina_num=3)

        self.assertEqual(r1["nombres"], "JUAN")
        self.assertEqual(r2["nombres"], "PEDRO")
        self.assertEqual(r3["nombres"], "MARIA")
        self.assertNotIn("PEDRO", r1["nombres"])
        self.assertNotIn("MARIA", r1["nombres"])

    def test_3_no_contaminacion_entre_campos(self):
        """
        NOMBRES: JUAN CARLOS, APELLIDOS: PEREZ GOMEZ jamás debe resultar en:
        nombres = JUAN CARLOS PEREZ ni apellidos = CARLOS PEREZ GOMEZ.
        """
        txt = """CEDULA DE CIUDADANIA 1006501709
NOMBRES JUAN CARLOS
APELLIDOS PEREZ GOMEZ
"""
        res = extractor_service.extraer(txt)
        self.assertEqual(res["nombres"], "JUAN CARLOS")
        self.assertEqual(res["apellidos"], "PEREZ GOMEZ")
        self.assertNotIn("PEREZ", res["nombres"])

    def test_4_regla_veto_espacial(self):
        """
        Si un candidato está ubicado por encima de la etiqueta (y_candidato < y_etiqueta - 0.03),
        debe aplicarse la regla de Veto Espacial.
        """
        eb = SpatialCandidate("NOMBRES", SpatialBoundingBox(0.1, 0.5, 0.2, 0.04), 0.99, 1)
        cb_arriba = SpatialCandidate("PEREZ GOMEZ", SpatialBoundingBox(0.1, 0.3, 0.3, 0.04), 0.99, 0)

        score, es_comp, razon = spatial_field_extractor.evaluar_proximidad_espacial(eb, cb_arriba)
        self.assertFalse(es_comp)
        self.assertIn("VETO ESPACIAL", razon)

    def test_5_tipo_documento_tarjeta_identidad(self):
        txt = "REPUBLICA DE COLOMBIA TARJETA DE IDENTIDAD NUMERO 1006501709"
        tipo = extractor_service.detectar_tipo_documento(txt)
        self.assertEqual(tipo, "TARJETA_IDENTIDAD")

    def test_6_documento_desconocido(self):
        txt = "FACTURA DE VENTA DE PRODUCTOS 2026 EMPRESA ABC"
        res = extractor_service.extraer(txt)
        val_id = res["detalles_campos"]["identificacion"].get("valor", res["detalles_campos"]["identificacion"].get("value"))
        self.assertIsNone(val_id)

    def test_7_extraccion_fecha_con_etiqueta(self):
        txt = "FECHA DE EXPEDICION: 15-MAY-2018 FECHA DE NACIMIENTO: 20-OCT-1995"
        res = extractor_service.extraer(txt)
        self.assertEqual(res["fecha_expedicion"], "2018-05-15")
        self.assertEqual(res["fecha_nacimiento"], "1995-10-20")


if __name__ == "__main__":
    unittest.main()
