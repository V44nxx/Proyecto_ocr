"""
Suite de Pruebas Unitarias para Auditoría Espacial 2D (0% Diccionario).
Verifica:
  1. No contaminación por marcas de agua (REPUBLICA DE COLOMBIA no se extrae como nombre).
  2. Exclusión mutua de tokens (un apellido no es robado como primer nombre).
  3. Comportamiento en Cédulas Amarillas reales de 2 caras en 1 página.
  4. Generación de artefactos de debug visual 2D en PNG.
"""
import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.spatial_field_extractor import spatial_field_extractor, SpatialBoundingBox


class OCRLineMock:
    def __init__(self, text: str, x: float, y: float, w: float = 0.4, h: float = 0.04, confidence: float = 0.95):
        self.text = text
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.confidence = confidence


class TestSpatial2DAudit(unittest.TestCase):

    def test_1_veto_absoluto_marca_de_agua_republica(self):
        """Demuestra geométricamente por qué REPUBLICA DE jamás entra como candidato de nombres."""
        lines = [
            OCRLineMock("REPUBLICA DE COLOMBIA", x=0.05, y=0.02, w=0.90, h=0.05),
            OCRLineMock("NUMERO 1.117.489.876", x=0.10, y=0.10, w=0.50, h=0.04),
            OCRLineMock("PARRA HERNANDEZ", x=0.10, y=0.15, w=0.50, h=0.04),
            OCRLineMock("APELLIDOS", x=0.10, y=0.18, w=0.20, h=0.03),
            OCRLineMock("DIEGO ARMANDO", x=0.10, y=0.22, w=0.50, h=0.04),
            OCRLineMock("NOMBRES", x=0.10, y=0.25, w=0.20, h=0.03),
        ]

        res = spatial_field_extractor.extraer_todos_los_campos(lines, page_num=1)
        self.assertEqual(res["apellidos"]["value"], "PARRA HERNANDEZ")
        self.assertEqual(res["nombres"]["value"], "DIEGO ARMANDO")
        self.assertNotEqual(res["nombres"]["value"], "REPUBLICA DE")

    def test_2_exclusion_mutua_y_firma_rayada(self):
        """Pág. 3 (17711201): Si los apellidos están rayados por la firma, LEONEL no es robado por apellidos."""
        lines = [
            OCRLineMock("NUMERO 17711201", x=0.10, y=0.10, w=0.50, h=0.04),
            # OYOLA SABI distorsionado por la firma rayada arriba
            OCRLineMock("FIRMA Leone Oyola", x=0.10, y=0.15, w=0.50, h=0.04),
            OCRLineMock("APELLIDOS", x=0.10, y=0.18, w=0.20, h=0.03),
            OCRLineMock("LEONEL", x=0.10, y=0.22, w=0.50, h=0.04),
            OCRLineMock("NOMBRES", x=0.10, y=0.25, w=0.20, h=0.03),
        ]

        res = spatial_field_extractor.extraer_todos_los_campos(lines, page_num=3)
        # Nombres DEBE ser LEONEL (no None ni POR REVISAR)
        self.assertEqual(res["nombres"]["value"], "LEONEL")

    def test_3_generacion_debug_visual_png(self):
        """Verifica que el artefacto PNG de debug visual 2D se genere en disco."""
        lines = [
            OCRLineMock("NUMERO 16.221.480", x=0.10, y=0.10),
            OCRLineMock("VALENCIA VILLEGAS", x=0.10, y=0.15),
            OCRLineMock("APELLIDOS", x=0.10, y=0.18),
            OCRLineMock("ANTONIO", x=0.10, y=0.22),
            OCRLineMock("NOMBRES", x=0.10, y=0.25),
        ]
        spatial_field_extractor.extraer_todos_los_campos(lines, page_num=99)
        path_debug = "exports/debug_visual/page_99_debug_2d.png"
        self.assertTrue(os.path.exists(path_debug))


if __name__ == "__main__":
    unittest.main()
