"""
Pruebas Unitarias para RapidOCRService (ONNX Runtime)
Verifica inicialización, extracción de texto y generación de layout estructurado 2D.
"""
import sys
import unittest
import numpy as np
import cv2

sys.path.insert(0, "backend")

from app.services.rapid_ocr_service import rapid_ocr_service
from app.services.ocr_service import ocr_service


class TestRapidOCRService(unittest.TestCase):

    def test_1_rapid_ocr_inicializado_y_disponible(self):
        """Verifica que el servicio RapidOCR esté disponible."""
        self.assertTrue(rapid_ocr_service.disponible, "RapidOCR debe estar disponible e inicializado")

    def test_2_extraccion_texto_y_coordenadas_sinteticas(self):
        """Crea una imagen sintética con texto y verifica que RapidOCR lo lea correctamente."""
        # Crear imagen blanca de 400x1200
        img = np.ones((400, 1200, 3), dtype=np.uint8) * 255
        # Escribir texto nítido
        cv2.putText(img, "CEDULA DE CIUDADANIA", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
        cv2.putText(img, "NUMERO 1006501709", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
        cv2.putText(img, "DIEGO ARMANDO MARADONA", (50, 300), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)

        texto, conf, struct_res = rapid_ocr_service.procesar_imagen(img, pagina_num=1)

        self.assertIn("1006501709", texto)
        self.assertGreater(conf, 50.0)
        self.assertIsNotNone(struct_res)
        self.assertGreater(len(struct_res.pages), 0)
        self.assertGreater(len(struct_res.pages[0].tokens), 0)
        
        # Verificar que las coordenadas estén normalizadas entre 0.0 y 1.0
        primer_token = struct_res.pages[0].tokens[0]
        self.assertGreaterEqual(primer_token.x, 0.0)
        self.assertLessEqual(primer_token.x, 1.0)
        self.assertGreaterEqual(primer_token.y, 0.0)
        self.assertLessEqual(primer_token.y, 1.0)

    def test_3_cascada_ocr_imagen_fallback(self):
        """Verifica que _ocr_imagen funcione correctamente con RapidOCR."""
        img = np.ones((300, 800, 3), dtype=np.uint8) * 255
        cv2.putText(img, "REPUBLICA DE COLOMBIA", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

        texto, motor, struct_res = ocr_service._ocr_imagen(img, pagina_num=1)
        self.assertIn("COLOMBIA", texto.upper())
        self.assertIn(motor, ["google_document_ai", "rapid_ocr", "tesseract_fallback", "google_document_ai+rapid_ocr"])


if __name__ == "__main__":
    unittest.main()
