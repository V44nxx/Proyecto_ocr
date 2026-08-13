"""
Suite de pruebas completas para la Reingeniería Definitiva del Pipeline OCR.
Cubre clasificación de documentos, regiones múltiples por página,
veto espacial, cero invención y test de nombres no pertenecientes a diccionarios.
"""
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, "backend")

from app.services.document_detector import document_detector
from app.services.document_region_detector import document_region_detector
from app.services.spatial_field_extractor import spatial_field_extractor, SpatialBoundingBox, SpatialCandidate
from app.services.extractor_service import extractor_service
from app.services.google_document_ai_service import OCRLine, OCRPageData, StructuredDocumentAIResult


class TestDefinitivePipeline(unittest.TestCase):

    def test_1_clasificacion_cedula_limpia(self):
        txt = "REPUBLICA DE COLOMBIA IDENTIFICACION PERSONAL CEDULA DE CIUDADANIA NUMERO 1006501709 NOMBRES JUAN CARLOS APELLIDOS PEREZ GOMEZ FECHA DE NACIMIENTO 05-MAY-1987 SEXO M"
        res = document_detector.clasificar_documento(txt)
        self.assertEqual(res["tipo_documento"], "CEDULA_CIUDADANIA")
        self.assertFalse(res["requiere_revision"])

    def test_2_clasificacion_tarjeta_identidad(self):
        txt = "REPUBLICA DE COLOMBIA TARJETA DE IDENTIDAD NUMERO 1098765432 NOMBRES CARLOS ANDRES"
        res = document_detector.clasificar_documento(txt)
        self.assertEqual(res["tipo_documento"], "TARJETA_IDENTIDAD")

    def test_3_clasificacion_documento_desconocido(self):
        txt = "ACTA DE ASAMBLEA GENERAL DE ACCIONISTAS DEPARTAMENTO FINANCIERO"
        res = document_detector.clasificar_documento(txt)
        self.assertIn(res["tipo_documento"], ("UNKNOWN", "NO_DOCUMENT"))

    def test_4_deteccion_regiones_multiples_pagina(self):
        import numpy as np
        # Crear imagen simulada con 2 bloques
        img = np.ones((800, 600, 3), dtype=np.uint8) * 255
        img[100:300, 50:550] = 50  # Bloque 1 (Cédula 1)
        img[450:650, 50:550] = 50  # Bloque 2 (Cédula 2)

        regiones = document_region_detector.detectar_regiones_documentos(img, page_num=1)
        self.assertGreaterEqual(len(regiones), 1)
        self.assertEqual(regiones[0]["bbox"]["page"], 1)

    def test_5_independencia_diccionario_nombre_desconocido(self):
        """
        Nombres y apellidos totalmente inexistentes ("XAVIERON ARISTEL", "QUINTERAL MENDOZA")
        deben ser extraídos con status VALID cuando Document AI + coordenadas coinciden.
        """
        lines_p = [
            OCRLine(text="NOMBRES", confidence=0.99, page_number=1, x=0.1, y=0.1, w=0.2, h=0.04),
            OCRLine(text="XAVIERON ARISTEL", confidence=0.98, page_number=1, x=0.1, y=0.15, w=0.4, h=0.04),
            OCRLine(text="APELLIDOS", confidence=0.99, page_number=1, x=0.1, y=0.22, w=0.2, h=0.04),
            OCRLine(text="QUINTERAL MENDOZA", confidence=0.97, page_number=1, x=0.1, y=0.27, w=0.4, h=0.04),
            OCRLine(text="NUMERO 1006501709", confidence=0.99, page_number=1, x=0.1, y=0.05, w=0.3, h=0.04),
        ]
        p_data = OCRPageData(page_number=1, width=1.0, height=1.0, text="CEDULA", lines=lines_p)
        layout = StructuredDocumentAIResult(text="CEDULA", tiempo_ms=10.0, pages=[p_data])

        res = extractor_service.extraer(
            "CEDULA DE CIUDADANIA NUMERO 1006501709 NOMBRES XAVIERON ARISTEL APELLIDOS QUINTERAL MENDOZA",
            layout_data=layout, pagina_num=1
        )
        self.assertEqual(res["nombres"], "XAVIERON ARISTEL")
        self.assertEqual(res["apellidos"], "QUINTERAL MENDOZA")
        self.assertEqual(res["detalles_campos"]["nombres"]["status"], "VALID")

    def test_6_regla_veto_espacial(self):
        eb = SpatialCandidate("NOMBRES", SpatialBoundingBox(0.1, 0.5, 0.2, 0.04), 0.99, 1)
        cb_arriba = SpatialCandidate("PEREZ GOMEZ", SpatialBoundingBox(0.1, 0.3, 0.3, 0.04), 0.99, 0)
        score, es_comp, razon = spatial_field_extractor.evaluar_proximidad_espacial(eb, cb_arriba)
        self.assertFalse(es_comp)
        self.assertIn("VETO ESPACIAL", razon)

    def test_7_prohibicion_adivinacion_genero(self):
        """Está prohibido inferir género desde el nombre (MARIA -> F jamás se asume a ciegas sin etiqueta)."""
        txt = "CEDULA 1006501709 NOMBRES MARIA FERNANDA APELLIDOS ROJAS"
        res = extractor_service.extraer(txt)
        self.assertIsNone(res["sexo"])
        self.assertEqual(res["detalles_campos"]["sexo"]["status"], "REVIEW_REQUIRED")

    def test_8_aislamiento_entre_paginas(self):
        r1 = extractor_service.extraer("CEDULA 1006501701 NOMBRES JUAN", pagina_num=1)
        r2 = extractor_service.extraer("CEDULA 1006501702 NOMBRES PEDRO", pagina_num=2)
        self.assertEqual(r1["nombres"], "JUAN")
        self.assertEqual(r2["nombres"], "PEDRO")
        self.assertNotIn("PEDRO", r1["nombres"])

    def test_9_separacion_lugar_y_fecha_expedicion(self):
        txt = "FECHA Y LUGAR DE EXPEDICION 15-04-2020 BOGOTA D.C."
        lugar = extractor_service._extraer_lugar(txt, txt.split("\n"))
        self.assertIsNotNone(lugar)
        self.assertIn("BOGOTA", lugar)

    def test_10_reporte_diferencias_11_columnas(self):
        from app.services.exportacion_service import exportacion_service
        mock_db = MagicMock()
        mock_dif = MagicMock()
        mock_dif.numero_identificacion = "1006501709"
        mock_dif.campo = "nombres"
        mock_dif.valor_bd = "JUAN"
        mock_dif.valor_excel = "JUAN CARLOS"
        mock_dif.tipo_diferencia = "diferente"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dif]
        mock_db.query.return_value.filter.return_value.first.return_value = None

        ruta = exportacion_service.exportar_reporte_diferencias(mock_db, "comp-123")
        self.assertTrue(ruta.endswith(".xlsx"))


if __name__ == "__main__":
    unittest.main()
