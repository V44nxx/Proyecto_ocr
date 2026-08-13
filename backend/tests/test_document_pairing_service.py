"""
Suite de Pruebas Automatizadas para DocumentSideClassifier, DocumentPairingService y Agrupación de Caras.
Cubre los 17 escenarios exigidos sin romper funcionalidades existentes.
"""
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, "backend")

from app.services.document_side_classifier import document_side_classifier
from app.services.document_pairing_service import document_pairing_service, DocumentGroup
from app.services.extractor_service import extractor_service


class TestDocumentPairingServiceSuite(unittest.TestCase):

    def test_1_front_back_consecutivos(self):
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501709"}
        p2 = {"pagina_numero": 2, "cara": "CEDULA_BACK", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501709"}
        grupos = document_pairing_service.agrupar_paginas([p1, p2])
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0].pages, [1, 2])
        self.assertEqual(grupos[0].pagina_frente, 1)
        self.assertEqual(grupos[0].pagina_reverso, 2)

    def test_2_multiples_personas_front_back(self):
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501701"}
        p2 = {"pagina_numero": 2, "cara": "CEDULA_BACK", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501701"}
        p3 = {"pagina_numero": 3, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501702"}
        p4 = {"pagina_numero": 4, "cara": "CEDULA_BACK", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501702"}

        grupos = document_pairing_service.agrupar_paginas([p1, p2, p3, p4])
        self.assertEqual(len(grupos), 2)
        self.assertEqual(grupos[0].pages, [1, 2])
        self.assertEqual(grupos[1].pages, [3, 4])

    def test_3_front_front_back_back_por_coincidencia_id(self):
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501701"}
        p2 = {"pagina_numero": 2, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501702"}
        p3 = {"pagina_numero": 3, "cara": "CEDULA_BACK", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501701"}
        p4 = {"pagina_numero": 4, "cara": "CEDULA_BACK", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501702"}

        grupos = document_pairing_service.agrupar_paginas([p1, p2, p3, p4])
        self.assertEqual(len(grupos), 2)
        self.assertEqual(grupos[0].pages, [1, 3])
        self.assertEqual(grupos[1].pages, [2, 4])

    def test_4_coincidencia_mrz_nuip_confianza_alta(self):
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1117489876"}
        p2 = {"pagina_numero": 2, "cara": "CEDULA_BACK", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1117489876"}
        score, reasons = document_pairing_service.evaluar_asociacion(p1, p2)
        self.assertGreaterEqual(score, 0.95)
        self.assertTrue(any("Coincidencia exacta" in r for r in reasons))

    def test_5_back_sin_numero_identificacion(self):
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501709"}
        p2 = {"pagina_numero": 2, "cara": "CEDULA_BACK", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.80, "numero_identificacion": None}
        grupos = document_pairing_service.agrupar_paginas([p1, p2])
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0].pages, [1, 2])

    def test_6_pagina_unknown(self):
        p1 = {"pagina_numero": 1, "cara": "UNKNOWN", "tipo_documento": "UNKNOWN", "confianza": 0.30, "numero_identificacion": None}
        grupos = document_pairing_service.agrupar_paginas([p1])
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0].status, "REVIEW_REQUIRED")

    def test_7_documento_incompleto_solo_front(self):
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501709"}
        grupos = document_pairing_service.agrupar_paginas([p1])
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0].pagina_frente, 1)
        self.assertIsNone(grupos[0].pagina_reverso)

    def test_8_mismo_numero_en_dos_grupos_duplicados(self):
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501709"}
        p2 = {"pagina_numero": 3, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501709"}
        grupos = document_pairing_service.agrupar_paginas([p1, p2])
        self.assertEqual(len(grupos), 2)
        self.assertEqual(grupos[1].status, "DUPLICATE_REVIEW_REQUIRED")

    def test_9_paginas_fuera_de_orden(self):
        p2 = {"pagina_numero": 2, "cara": "CEDULA_BACK", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501709"}
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501709"}
        grupos = document_pairing_service.agrupar_paginas([p2, p1])
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0].pages, [1, 2])

    def test_10_mezcla_cedula_y_tarjeta_identidad(self):
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501709"}
        p2 = {"pagina_numero": 2, "cara": "TARJETA_IDENTIDAD_BACK", "tipo_documento": "TARJETA_IDENTIDAD", "confianza": 0.90, "numero_identificacion": None}
        score, _ = document_pairing_service.evaluar_asociacion(p1, p2)
        self.assertLess(score, 0.50)

    def test_11_informacion_contradictoria_front_back(self):
        grp = DocumentGroup("DOC-999")
        grp.front_page = {"pagina_numero": 1, "texto": "NUMERO 1006501709 NOMBRES JUAN CARLOS APELLIDOS PEREZ GOMEZ"}
        grp.back_page = {"pagina_numero": 2, "texto": "FECHA DE EXPEDICION 15-MAY-2018 NUMERO 1006509999 FLORENCIA"}
        res = extractor_service.extraer_grupo(grp)
        self.assertTrue(res["requiere_revision"])
        self.assertEqual(res["detalles_campos"]["identificacion"]["status"], "REVIEW_REQUIRED")

    def test_12_paginas_no_documento(self):
        p1 = {"pagina_numero": 1, "cara": "UNKNOWN", "tipo_documento": "NO_DOCUMENT", "confianza": 0.10}
        grupos = document_pairing_service.agrupar_paginas([p1])
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0].status, "REVIEW_REQUIRED")

    def test_13_pdf_una_sola_cara(self):
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "1006501709"}
        grupos = document_pairing_service.agrupar_paginas([p1])
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0].pages, [1])

    def test_14_pdf_multiples_documentos(self):
        p1 = {"pagina_numero": 1, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "111"}
        p2 = {"pagina_numero": 2, "cara": "CEDULA_BACK", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "111"}
        p3 = {"pagina_numero": 3, "cara": "CEDULA_FRONT", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "222"}
        p4 = {"pagina_numero": 4, "cara": "CEDULA_BACK", "tipo_documento": "CEDULA_CIUDADANIA", "confianza": 0.95, "numero_identificacion": "222"}
        grupos = document_pairing_service.agrupar_paginas([p1, p2, p3, p4])
        self.assertEqual(len(grupos), 2)

    def test_15_preservacion_pagina_numero_frente_reverso(self):
        grp = DocumentGroup("DOC-001")
        grp.front_page = {"pagina_numero": 3, "texto": "NUMERO 1006501709 NOMBRES ANTONIO"}
        grp.back_page = {"pagina_numero": 4, "texto": "FECHA DE EXPEDICION 2019-04-16 FLORENCIA"}
        res = extractor_service.extraer_grupo(grp)
        self.assertEqual(res["pagina_frente"], 3)
        self.assertEqual(res["pagina_reverso"], 4)

    def test_16_preservacion_grupo_documento_id(self):
        grp = DocumentGroup("DOC-888")
        grp.front_page = {"pagina_numero": 1, "texto": "NUMERO 1006501709 NOMBRES ANTONIO"}
        res = extractor_service.extraer_grupo(grp)
        self.assertEqual(res["grupo_documento_id"], "DOC-888")

    def test_17_comparacion_excel_por_documento_agrupado(self):
        from app.services.exportacion_service import exportacion_service
        mock_db = MagicMock()
        mock_dif = MagicMock()
        mock_dif.numero_identificacion = "1006501709"
        mock_dif.campo = "nombres"
        mock_dif.valor_bd = "ANTONIO"
        mock_dif.valor_excel = "ANTONIO JOSE"
        mock_dif.tipo_diferencia = "diferente"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dif]
        mock_db.query.return_value.filter.return_value.first.return_value = None

        ruta = exportacion_service.exportar_reporte_diferencias(mock_db, "comp-999")
        self.assertTrue(ruta.endswith(".xlsx"))


if __name__ == "__main__":
    unittest.main()
