"""
Pruebas unitarias para el extractor espacial de cédulas y pipeline OCR.
Cubre las 15 condiciones exigidas sin requerir credenciales reales de GCP (usan Mocks).
"""
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, "backend")

from app.services.extractor_service import extractor_service
from app.services.google_document_ai_service import OCRToken, OCRLine, OCRPageData, StructuredDocumentAIResult
from app.utils.validators import validador


class TestSpatialExtractorPipeline(unittest.TestCase):

    def test_1_cedula_correctamente_leida(self):
        txt = """REPUBLICA DE COLOMBIA
IDENTIFICACION PERSONAL
CEDULA DE CIUDADANIA
NUMERO 1.117.489.876
APELLIDOS BIABOS
NOMBRES DIEGO ARMANDO
FECHA Y LUGAR DE EXPEDICION 26-JUN-2007 FLORENCIA
FECHA DE NACIMIENTO 05-MAY-1987 SEXO M
"""
        res = extractor_service.extraer(txt)
        self.assertEqual(res["identificacion"], "1117489876")
        self.assertEqual(res["nombres"], "DIEGO ARMANDO")
        self.assertEqual(res["apellidos"], "BIABOS")
        self.assertEqual(res["fecha_nacimiento"], "1987-05-05")
        self.assertEqual(res["fecha_expedicion"], "2007-06-26")
        self.assertEqual(res["lugar_expedicion"], "FLORENCIA")
        self.assertEqual(res["sexo"], "M")
        self.assertEqual(res["tipo_documento"], "CEDULA_CIUDADANIA")

    def test_2_numero_con_errores_ocr(self):
        txt = "NUMERO CEDULA 1.006.501.709"
        raw_id = extractor_service._extraer_identificacion(txt, txt.split("\n"))
        self.assertEqual(raw_id, "1006501709")

    def test_3_nombre_apellido_confundidos_layout(self):
        txt = """CEDULA DE CIUDADANIA
NUMERO 16.221.480
APELLIDOS RAJONAL
NOMBRES ANTONIO
"""
        res = extractor_service.extraer(txt)
        self.assertEqual(res["nombres"], "ANTONIO")
        self.assertIn("RAJONAL", res["apellidos"])

    def test_4_fecha_nacimiento_vs_expedicion_cronologico(self):
        txt = """FECHA DE EXPEDICION: 2019-10-24
FECHA DE NACIMIENTO: 2001-10-23
"""
        res = extractor_service.extraer(txt)
        self.assertEqual(res["fecha_nacimiento"], "2001-10-23")
        self.assertEqual(res["fecha_expedicion"], "2019-10-24")

    def test_5_campo_faltante_no_inventar(self):
        txt = "CEDULA DE CIUDADANIA 12345678"
        res = extractor_service.extraer(txt)
        self.assertIsNone(res["nombres"])
        self.assertIn(res["detalles_campos"]["nombres"]["status"].upper(), ("MISSING", "MISSING_DATA", "REVIEW_REQUIRED"))
        val_nom = res["detalles_campos"]["nombres"].get("valor", res["detalles_campos"]["nombres"].get("value"))
        self.assertIsNone(val_nom)

    def test_6_genero_faltante(self):
        txt = "CEDULA 1006501709 NOMBRES PEDRO JOSE APELLIDOS JOVEN URAZAN"
        res = extractor_service.extraer(txt)
        self.assertIsNone(res["sexo"])
        val_sex = res["detalles_campos"]["sexo"].get("valor", res["detalles_campos"]["sexo"].get("value"))
        self.assertIsNone(val_sex)

    def test_7_lugar_expedicion_normalizado(self):
        txt = "FECHA Y LUGAR DE EXPEDICION\n24-OCT-2019 SAN VICENTE DEL CAGUAN"
        lugar = extractor_service._extraer_lugar(txt, txt.split("\n"))
        self.assertIsNotNone(lugar)
        self.assertTrue("SAN VICENTE" in lugar or "CAGUAN" in lugar)

    def test_8_layout_espacial_tokens(self):
        p_data = OCRPageData(
            page_number=1, width=1.0, height=1.0, text="CEDULA DE CIUDADANIA",
            lines=[
                OCRLine(text="NOMBRES", confidence=0.99, page_number=1, x=0.1, y=0.2, w=0.2, h=0.05),
                OCRLine(text="PEDRO JOSE", confidence=0.98, page_number=1, x=0.4, y=0.2, w=0.3, h=0.05)
            ]
        )
        mock_layout = StructuredDocumentAIResult(text="CEDULA DE CIUDADANIA NOMBRES PEDRO JOSE", tiempo_ms=10.0, pages=[p_data])
        res = extractor_service.extraer("CEDULA DE CIUDADANIA NOMBRES PEDRO JOSE", layout_data=mock_layout)
        self.assertEqual(res["nombres"], "PEDRO JOSE")

    def test_9_pdf_multiples_paginas_contexto(self):
        txt_p1 = "CEDULA 1117489876 NOMBRES DIEGO ARMANDO"
        txt_p2 = "CEDULA 16221480 NOMBRES ANTONIO"
        res1 = extractor_service.extraer(txt_p1, pagina_num=1)
        res2 = extractor_service.extraer(txt_p2, pagina_num=2)
        self.assertEqual(res1["identificacion"], "1117489876")
        self.assertEqual(res2["identificacion"], "16221480")
        self.assertEqual(res1["detalles_campos"]["identificacion"]["page"], 1)
        self.assertEqual(res2["detalles_campos"]["identificacion"]["page"], 2)

    def test_10_documento_desconocido(self):
        txt = "ACTA DE REUNION DE SOCIOS 2026 DEPARTAMENTO FINANCIERO"
        tipo = extractor_service.detectar_tipo_documento(txt)
        res = extractor_service.extraer(txt)
        self.assertEqual(tipo, "UNKNOWN")
        self.assertIsNone(res["detalles_campos"]["identificacion"]["value"])

    def test_11_validar_fecha_mes_abrev(self):
        d1 = validador.parsear_fecha("05-MAY-1987")
        d2 = validador.parsear_fecha("NOV 07 1987")
        self.assertEqual((d1.year, d1.month, d1.day), (1987, 5, 5))
        self.assertEqual((d2.year, d2.month, d2.day), (1987, 11, 7))

    def test_12_normalizacion_comparacion_excel(self):
        from app.services.comparacion_service import comparacion_service
        s1 = comparacion_service._normalizar_para_comparacion(" PÉREZ ")
        s2 = comparacion_service._normalizar_para_comparacion("PEREZ")
        self.assertEqual(s1, s2)

    def test_13_diferencia_real_comparacion(self):
        from app.services.comparacion_service import comparacion_service
        s1 = comparacion_service._normalizar_para_comparacion("2020-04-15")
        s2 = comparacion_service._normalizar_para_comparacion("2020-04-16")
        self.assertNotEqual(s1, s2)

    def test_14_confianza_baja_revision_requerida(self):
        txt = "CEDULA 123"
        res = extractor_service.extraer(txt)
        self.assertLess(res["confianza_extraccion"], 80.0)
        self.assertIn(res["detalles_campos"]["nombres"]["status"], ("missing", "review_required"))

    def test_15_fallback_tesseract_etiquetado(self):
        from app.services.ocr_service import ocr_service
        mock_db = MagicMock()
        mock_persona_query = MagicMock()
        mock_persona_query.first.return_value = None
        mock_db.query.return_value.filter.return_value = mock_persona_query

        datos = extractor_service.extraer("CEDULA 1006501709 NOMBRES PEDRO JOSE")
        p_dict = ocr_service._guardar_persona(
            datos, "CEDULA 1006501709", "doc-123", mock_db,
            ocr_engine="tesseract_fallback", pagina_num=5
        )
        self.assertEqual(p_dict["estado_registro"], "FALLBACK_TESSERACT")
        self.assertEqual(p_dict["motor_ocr"], "tesseract_fallback")
        self.assertEqual(p_dict["pagina_numero"], 5)


if __name__ == "__main__":
    unittest.main()
