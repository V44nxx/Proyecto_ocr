"""
Pruebas avanzadas para SpatialFieldExtractor, Veto Espacial, Aislamiento por Página,
calculate_spatial_relation y la Prueba de Independencia del Diccionario (Precisión > Completitud).
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

    def test_4_calculate_spatial_relation_veto(self):
        """
        Si un candidato está ubicado por encima de la etiqueta, calculate_spatial_relation retorna ABOVE (0.0).
        """
        label_b = SpatialBoundingBox(0.1, 0.5, 0.2, 0.04)
        cand_arriba = SpatialBoundingBox(0.1, 0.3, 0.3, 0.04)

        rel, score, desc = spatial_field_extractor.calculate_spatial_relation(label_b, cand_arriba)
        self.assertEqual(rel, "ABOVE")
        self.assertEqual(score, 0.0)
        self.assertIn("VETO ESPACIAL", desc)

    def test_5_variantes_ocr_etiquetas(self):
        """
        Reconocimiento de etiquetas con errores OCR ("N0MBRES", "APELL1DOS").
        """
        lines = [
            OCRLine(text="N0MBRES", confidence=0.95, page_number=1, x=0.1, y=0.1, w=0.2, h=0.03),
            OCRLine(text="APELL1DOS", confidence=0.95, page_number=1, x=0.1, y=0.3, w=0.2, h=0.03),
        ]
        etiquetas = spatial_field_extractor.identificar_etiquetas_espaciales(lines)
        self.assertIn("nombres", etiquetas)
        self.assertIn("apellidos", etiquetas)

    def test_6_veto_encabezados_ruido(self):
        """
        Palabras como REPUBLICA DE COLOMBIA jamás deben ser seleccionadas como nombre.
        """
        lines = [
            OCRLine(text="REPUBLICA DE COLOMBIA", confidence=0.99, page_number=1, x=0.1, y=0.01, w=0.8, h=0.04),
            OCRLine(text="NOMBRES", confidence=0.99, page_number=1, x=0.1, y=0.10, w=0.2, h=0.03),
            OCRLine(text="EMERSON", confidence=0.98, page_number=1, x=0.1, y=0.15, w=0.3, h=0.03),
        ]
        res = spatial_field_extractor.extraer_campo_con_layout("nombres", lines, page_num=1)
        self.assertEqual(res["value"], "EMERSON")
        self.assertNotIn("REPUBLICA", res["value"])

    def test_7_sin_etiqueta_retorna_review_required(self):
        """
        Si no hay etiqueta explícita de nombres, retornar null + REVIEW_REQUIRED (jamás la línea 0 del PDF).
        """
        lines = [
            OCRLine(text="REPUBLICA DE COLOMBIA", confidence=0.99, page_number=1, x=0.1, y=0.01, w=0.8, h=0.04),
            OCRLine(text="TEXTO CUALQUIERA SIN ETIQUETA", confidence=0.90, page_number=1, x=0.1, y=0.10, w=0.5, h=0.03),
        ]
        res = spatial_field_extractor.extraer_campo_con_layout("nombres", lines, page_num=1)
        self.assertIsNone(res["value"])
        self.assertEqual(res["status"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
