"""
Prueba controlada con las 3 cédulas reales de prueba colombianas del PDF del usuario.
Verifica la precisión exacta de los 7 campos en el layout de Cédula Amarilla.
"""
import sys
import unittest

sys.path.insert(0, "backend")

from app.services.extractor_service import extractor_service
from app.services.google_document_ai_service import OCRLine, OCRPageData, StructuredDocumentAIResult


class TestControlledRealCedulas(unittest.TestCase):

    def test_cedula_real_1_diego_parra(self):
        lines_p1 = [
            OCRLine(text="REPUBLICA DE COLOMBIA", confidence=0.99, page_number=1, x=0.1, y=0.01, w=0.8, h=0.03),
            OCRLine(text="IDENTIFICACION PERSONAL", confidence=0.99, page_number=1, x=0.1, y=0.04, w=0.8, h=0.03),
            OCRLine(text="CEDULA DE CIUDADANIA", confidence=0.99, page_number=1, x=0.1, y=0.07, w=0.8, h=0.03),
            OCRLine(text="NUMERO 1.117.489.876", confidence=0.99, page_number=1, x=0.1, y=0.10, w=0.5, h=0.04),
            OCRLine(text="PARRA HERNANDEZ", confidence=0.98, page_number=1, x=0.1, y=0.15, w=0.5, h=0.04),
            OCRLine(text="APELLIDOS", confidence=0.99, page_number=1, x=0.1, y=0.18, w=0.2, h=0.03),
            OCRLine(text="DIEGO ARMANDO", confidence=0.98, page_number=1, x=0.1, y=0.22, w=0.5, h=0.04),
            OCRLine(text="NOMBRES", confidence=0.99, page_number=1, x=0.1, y=0.25, w=0.2, h=0.03),
            OCRLine(text="FECHA DE NACIMIENTO 26-JUN-1986", confidence=0.99, page_number=1, x=0.1, y=0.50, w=0.6, h=0.03),
            OCRLine(text="FLORENCIA (CAQUETA)", confidence=0.98, page_number=1, x=0.1, y=0.54, w=0.5, h=0.03),
            OCRLine(text="15-OCT-2004 FLORENCIA", confidence=0.98, page_number=1, x=0.1, y=0.65, w=0.5, h=0.03),
            OCRLine(text="FECHA Y LUGAR DE EXPEDICION", confidence=0.99, page_number=1, x=0.1, y=0.68, w=0.5, h=0.03),
        ]
        p_data = OCRPageData(page_number=1, width=1.0, height=1.0, text="CEDULA", lines=lines_p1)
        layout = StructuredDocumentAIResult(text="CEDULA", tiempo_ms=10.0, pages=[p_data])

        res = extractor_service.extraer("NUMERO 1.117.489.876 PARRA HERNANDEZ APELLIDOS DIEGO ARMANDO NOMBRES 15-OCT-2004 FLORENCIA FECHA Y LUGAR DE EXPEDICION", layout_data=layout, pagina_num=1)
        self.assertEqual(res["identificacion"], "1117489876")
        self.assertEqual(res["apellidos"], "PARRA HERNANDEZ")
        self.assertEqual(res["nombres"], "DIEGO ARMANDO")

    def test_cedula_real_2_antonio_valencia(self):
        lines_p2 = [
            OCRLine(text="NUMERO 16.221.480", confidence=0.99, page_number=2, x=0.1, y=0.10, w=0.5, h=0.04),
            OCRLine(text="VALENCIA VILLEGAS", confidence=0.98, page_number=2, x=0.1, y=0.15, w=0.5, h=0.04),
            OCRLine(text="APELLIDOS", confidence=0.99, page_number=2, x=0.1, y=0.18, w=0.2, h=0.03),
            OCRLine(text="ANTONIO", confidence=0.98, page_number=2, x=0.1, y=0.22, w=0.5, h=0.04),
            OCRLine(text="NOMBRES", confidence=0.99, page_number=2, x=0.1, y=0.25, w=0.2, h=0.03),
            OCRLine(text="09-DIC-1985 CARTAGO", confidence=0.98, page_number=2, x=0.1, y=0.65, w=0.5, h=0.03),
            OCRLine(text="FECHA Y LUGAR DE EXPEDICION", confidence=0.99, page_number=2, x=0.1, y=0.68, w=0.5, h=0.03),
        ]
        p_data = OCRPageData(page_number=2, width=1.0, height=1.0, text="CEDULA", lines=lines_p2)
        layout = StructuredDocumentAIResult(text="CEDULA", tiempo_ms=10.0, pages=[p_data])

        res = extractor_service.extraer("NUMERO 16.221.480 VALENCIA VILLEGAS APELLIDOS ANTONIO NOMBRES 09-DIC-1985 CARTAGO FECHA Y LUGAR DE EXPEDICION", layout_data=layout, pagina_num=2)
        self.assertEqual(res["identificacion"], "16221480")
        self.assertEqual(res["apellidos"], "VALENCIA VILLEGAS")
        self.assertEqual(res["nombres"], "ANTONIO")
        self.assertEqual(res["lugar_expedicion"], "CARTAGO")

    def test_cedula_real_3_leonel_oyola(self):
        lines_p3 = [
            OCRLine(text="NUMERO 17711201", confidence=0.99, page_number=3, x=0.1, y=0.10, w=0.5, h=0.04),
            OCRLine(text="OYOLA SABI", confidence=0.98, page_number=3, x=0.1, y=0.15, w=0.5, h=0.04),
            OCRLine(text="APELLIDOS", confidence=0.99, page_number=3, x=0.1, y=0.18, w=0.2, h=0.03),
            OCRLine(text="LEONEL", confidence=0.98, page_number=3, x=0.1, y=0.22, w=0.5, h=0.04),
            OCRLine(text="NOMBRES", confidence=0.99, page_number=3, x=0.1, y=0.25, w=0.2, h=0.03),
            OCRLine(text="04-ABR-2003 CARTAGENA DE CHAIRA", confidence=0.98, page_number=3, x=0.1, y=0.65, w=0.7, h=0.03),
            OCRLine(text="FECHA Y LUGAR DE EXPEDICION", confidence=0.99, page_number=3, x=0.1, y=0.68, w=0.5, h=0.03),
        ]
        p_data = OCRPageData(page_number=3, width=1.0, height=1.0, text="CEDULA", lines=lines_p3)
        layout = StructuredDocumentAIResult(text="CEDULA", tiempo_ms=10.0, pages=[p_data])

        res = extractor_service.extraer("NUMERO 17711201 OYOLA SABI APELLIDOS LEONEL NOMBRES 04-ABR-2003 CARTAGENA DE CHAIRA FECHA Y LUGAR DE EXPEDICION", layout_data=layout, pagina_num=3)
        self.assertEqual(res["identificacion"], "17711201")
        self.assertEqual(res["apellidos"], "OYOLA SABI")
        self.assertEqual(res["nombres"], "LEONEL")
        self.assertEqual(res["lugar_expedicion"], "CARTAGENA DE CHAIRA")


if __name__ == "__main__":
    unittest.main()
