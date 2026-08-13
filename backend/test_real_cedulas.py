"""
Prueba controlada con 3 cédulas reales de prueba colombianas.
Verifica la precisión de extracción de los 7 campos antes de procesar el lote completo de 42 páginas.
"""
import sys
import unittest

sys.path.insert(0, "backend")

from app.services.extractor_service import extractor_service
from app.services.google_document_ai_service import OCRLine, OCRPageData, StructuredDocumentAIResult


class TestControlledRealCedulas(unittest.TestCase):

    def test_cedula_real_1_diego_biabos(self):
        txt = """REPUBLICA DE COLOMBIA
IDENTIFICACION PERSONAL
CEDULA DE CIUDADANIA
NUMERO 1.117.489.876
APELLIDOS BIABOS
NOMBRES DIEGO ARMANDO
FECHA Y LUGAR DE EXPEDICION 26-JUN-2007 FLORENCIA
FECHA DE NACIMIENTO 05-MAY-1987 SEXO M
"""
        res = extractor_service.extraer(txt, pagina_num=1)
        self.assertEqual(res["identificacion"], "1117489876")
        self.assertEqual(res["nombres"], "DIEGO ARMANDO")
        self.assertEqual(res["apellidos"], "BIABOS")
        self.assertEqual(res["fecha_nacimiento"], "1987-05-05")
        self.assertEqual(res["fecha_expedicion"], "2007-06-26")
        self.assertEqual(res["lugar_expedicion"], "FLORENCIA")
        self.assertEqual(res["sexo"], "M")
        self.assertEqual(res["detalles_campos"]["nombres"]["status"].upper(), "VALID")

    def test_cedula_real_2_pedro_joven(self):
        lines_p = [
            OCRLine(text="NUMERO 1.006.501.709", confidence=0.99, page_number=2, x=0.1, y=0.05, w=0.4, h=0.04),
            OCRLine(text="APELLIDOS", confidence=0.99, page_number=2, x=0.1, y=0.12, w=0.2, h=0.04),
            OCRLine(text="JOVEN URAZAN", confidence=0.98, page_number=2, x=0.1, y=0.17, w=0.4, h=0.04),
            OCRLine(text="NOMBRES", confidence=0.99, page_number=2, x=0.1, y=0.24, w=0.2, h=0.04),
            OCRLine(text="PEDRO JOSE", confidence=0.98, page_number=2, x=0.1, y=0.29, w=0.4, h=0.04),
            OCRLine(text="FECHA DE EXPEDICION 16-APR-2019 FLORENCIA", confidence=0.97, page_number=2, x=0.1, y=0.36, w=0.6, h=0.04),
        ]
        p_data = OCRPageData(page_number=2, width=1.0, height=1.0, text="CEDULA", lines=lines_p)
        layout = StructuredDocumentAIResult(text="CEDULA", tiempo_ms=12.0, pages=[p_data])

        res = extractor_service.extraer("CEDULA 1006501709 APELLIDOS JOVEN URAZAN NOMBRES PEDRO JOSE", layout_data=layout, pagina_num=2)
        self.assertEqual(res["identificacion"], "1006501709")
        self.assertEqual(res["nombres"], "PEDRO JOSE")
        self.assertEqual(res["apellidos"], "JOVEN URAZAN")

    def test_cedula_real_3_antonio_rajonal(self):
        txt = """REPUBLICA DE COLOMBIA
CEDULA DE CIUDADANIA 16.221.480
APELLIDOS RAJONAL
NOMBRES ANTONIO
FECHA DE NACIMIENTO 1983-03-12
SEXO M
"""
        res = extractor_service.extraer(txt, pagina_num=3)
        self.assertEqual(res["identificacion"], "16221480")
        self.assertEqual(res["nombres"], "ANTONIO")
        self.assertIn("RAJONAL", res["apellidos"])
        self.assertEqual(res["sexo"], "M")


if __name__ == "__main__":
    unittest.main()
