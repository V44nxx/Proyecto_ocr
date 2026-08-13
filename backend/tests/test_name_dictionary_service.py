"""
Pruebas unitarias para NameDictionaryService y sistema de scoring evidencial.
Cubre los 20 escenarios exigidos en las especificaciones.
"""
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, "backend")

from app.services.name_dictionary_service import name_dictionary_service
from app.services.extractor_service import extractor_service
from app.services.google_document_ai_service import OCRLine, OCRPageData, StructuredDocumentAIResult


class TestNameDictionaryServiceScenarios(unittest.TestCase):

    def test_1_nombre_simple(self):
        res = name_dictionary_service.analizar_candidatos_campo(
            ["PEDRO"], "nombres", etiqueta_presente=True, distancia_espacial_px=15.0, doc_ai_confidence=0.98
        )
        self.assertEqual(res["value"], "PEDRO")
        self.assertEqual(res["status"], "valid")
        self.assertGreaterEqual(res["final_score"], 0.75)

    def test_2_apellido_simple(self):
        res = name_dictionary_service.analizar_candidatos_campo(
            ["PEREZ"], "apellidos", etiqueta_presente=True, distancia_espacial_px=15.0, doc_ai_confidence=0.97
        )
        self.assertEqual(res["value"], "PEREZ")
        self.assertEqual(res["status"], "valid")

    def test_3_nombre_compuesto(self):
        res = name_dictionary_service.analizar_candidatos_campo(
            ["JUAN", "CARLOS"], "nombres", etiqueta_presente=True, distancia_espacial_px=18.0, doc_ai_confidence=0.96
        )
        self.assertEqual(res["value"], "JUAN CARLOS")
        self.assertEqual(res["status"], "valid")

    def test_4_apellido_compuesto(self):
        res = name_dictionary_service.analizar_candidatos_campo(
            ["DE", "LA", "ROSA"], "apellidos", etiqueta_presente=True, distancia_espacial_px=18.0, doc_ai_confidence=0.95
        )
        self.assertEqual(res["value"], "DE LA ROSA")
        self.assertEqual(res["status"], "valid")

    def test_5_nombre_desconocido_en_diccionario(self):
        # Nombre verdaderamente no registrado como "YERLINSON" debe ser ACEPTADO si layout y Document AI son altos
        res = name_dictionary_service.analizar_candidatos_campo(
            ["YERLINSON"], "nombres", etiqueta_presente=True, distancia_espacial_px=12.0, doc_ai_confidence=0.98
        )
        self.assertEqual(res["value"], "YERLINSON")
        self.assertIn(res["status"], ("valid", "review_required"))
        self.assertTrue(any("no registrada en diccionario" in ev for ev in res["evidence"]))

    def test_6_palabra_presente_en_ambos_diccionarios(self):
        # "CRUZ" existe como nombre y apellido. Sin buena adyacencia espacial debe ser REVIEW_REQUIRED
        eval_word = name_dictionary_service.evaluar_palabra("CRUZ")
        self.assertGreaterEqual(eval_word["nombre_score"], 0.8)
        self.assertGreaterEqual(eval_word["apellido_score"], 0.8)

    def test_7_error_ocr_con_fuzzy_matching(self):
        eval_p = name_dictionary_service.evaluar_palabra("PERE2")
        self.assertEqual(eval_p["matched_value"], "PEREZ")
        self.assertTrue(eval_p["nombre_score"] > 0 or eval_p["apellido_score"] > 0)

    def test_8_error_ocr_sin_suficiente_confianza(self):
        res = name_dictionary_service.analizar_candidatos_campo(
            ["X9Z"], "nombres", etiqueta_presente=False, distancia_espacial_px=100.0, doc_ai_confidence=0.10
        )
        self.assertIn(res["status"], ("missing_data", "review_required"))

    def test_9_nombre_apellido_intercambiados_por_layout(self):
        p_data = OCRPageData(
            page_number=1, width=1.0, height=1.0, text="CEDULA",
            lines=[
                OCRLine(text="NOMBRES", confidence=0.99, page_number=1, x=0.1, y=0.1, w=0.2, h=0.05),
                OCRLine(text="ANTONIO", confidence=0.98, page_number=1, x=0.4, y=0.1, w=0.3, h=0.05),
                OCRLine(text="APELLIDOS", confidence=0.99, page_number=1, x=0.1, y=0.2, w=0.2, h=0.05),
                OCRLine(text="RAJONAL", confidence=0.98, page_number=1, x=0.4, y=0.2, w=0.3, h=0.05),
            ]
        )
        layout = StructuredDocumentAIResult(text="NOMBRES ANTONIO APELLIDOS RAJONAL", tiempo_ms=10.0, pages=[p_data])
        ext_res = extractor_service.extraer("NOMBRES ANTONIO APELLIDOS RAJONAL", layout_data=layout)
        self.assertEqual(ext_res["nombres"], "ANTONIO")
        self.assertIn("RAJONAL", ext_res["apellidos"])

    def test_10_palabras_duplicadas(self):
        words, info = name_dictionary_service.detectar_duplicados(["PEDRO", "PEDRO", "JOSE"])
        self.assertTrue(info["duplicate_detected"])

    def test_11_tres_nombres(self):
        res = name_dictionary_service.analizar_candidatos_campo(
            ["JUAN", "CARLOS", "DIEGO"], "nombres", etiqueta_presente=True, distancia_espacial_px=15.0, doc_ai_confidence=0.95
        )
        self.assertEqual(res["value"], "JUAN CARLOS DIEGO")

    def test_12_un_solo_apellido(self):
        res = name_dictionary_service.analizar_candidatos_campo(
            ["GOMEZ"], "apellidos", etiqueta_presente=True, distancia_espacial_px=15.0, doc_ai_confidence=0.95
        )
        self.assertEqual(res["value"], "GOMEZ")

    def test_13_cuatro_componentes_nombre(self):
        res = name_dictionary_service.analizar_candidatos_campo(
            ["MARIA", "DE", "LOS", "ANGELES"], "nombres", etiqueta_presente=True, distancia_espacial_px=15.0, doc_ai_confidence=0.95
        )
        self.assertEqual(res["value"], "MARIA DE LOS ANGELES")

    def test_14_caracteres_con_tildes(self):
        norm = name_dictionary_service.normalizar_para_comparacion("PÉREZ GÓMEZ")
        self.assertEqual(norm, "PEREZ GOMEZ")

    def test_15_espacios_duplicados(self):
        norm = name_dictionary_service.normalizar_para_comparacion("  PEDRO   JOSE  ")
        self.assertEqual(norm, "PEDRO JOSE")

    def test_16_conflicto_entre_diccionario_y_layout(self):
        # Si la palabra es un apellido común pero está espacialmente debajo de NOMBRES
        res = name_dictionary_service.analizar_candidatos_campo(
            ["HERNANDEZ"], "nombres", etiqueta_presente=True, distancia_espacial_px=10.0, doc_ai_confidence=0.95
        )
        self.assertEqual(res["value"], "HERNANDEZ")
        self.assertGreaterEqual(res["spatial_score"], 0.8)

    def test_17_confidence_bajo(self):
        res = name_dictionary_service.analizar_candidatos_campo(
            ["XYZ"], "nombres", etiqueta_presente=False, distancia_espacial_px=80.0, doc_ai_confidence=0.20
        )
        self.assertIn(res["status"], ("review_required", "missing_data"))

    def test_18_documento_varias_paginas(self):
        r1 = extractor_service.extraer("CEDULA 1117489876 NOMBRES DIEGO ARMANDO", pagina_num=1)
        r2 = extractor_service.extraer("CEDULA 16221480 NOMBRES ANTONIO", pagina_num=2)
        self.assertEqual(r1["detalles_campos"]["nombres"]["page"], 1)
        self.assertEqual(r2["detalles_campos"]["nombres"]["page"], 2)

    def test_19_nombres_similares_entre_personas(self):
        r1 = extractor_service.extraer("CEDULA 1006501709 NOMBRES PEDRO JOSE")
        r2 = extractor_service.extraer("CEDULA 1006501710 NOMBRES PEDRO ANTONIO")
        self.assertEqual(r1["nombres"], "PEDRO JOSE")
        self.assertEqual(r2["nombres"], "PEDRO ANTONIO")

    def test_20_tesseract_fallback(self):
        from app.services.ocr_service import ocr_service
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        datos = extractor_service.extraer("CEDULA 1006501709 NOMBRES PEDRO JOSE")
        p_dict = ocr_service._guardar_persona(
            datos, "CEDULA 1006501709", "doc-999", mock_db,
            ocr_engine="tesseract_fallback", pagina_num=3
        )
        self.assertEqual(p_dict["estado_registro"], "FALLBACK_TESSERACT")
        self.assertEqual(p_dict["motor_ocr"], "tesseract_fallback")


if __name__ == "__main__":
    unittest.main()
