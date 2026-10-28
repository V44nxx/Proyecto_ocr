"""
Reverso de cédula amarilla mal leído por RapidOCR (sin internet): se reconoce como reverso por sus datos
(estatura, grupo sanguíneo, sexo, fechas) y no se toma un número del código de barras como otra persona.
"""
from app.services.document_pairing_service import document_pairing_service
from app.services.document_side_classifier import document_side_classifier

# Texto real de RapidOCR para el reverso de una cédula (números cambiados)
REVERSO_RAPID = """FCHA#C# 21UN-1968
NEIVA
(HUILA)
LUKAR DE
NACNIENIO
1.75
0+
M
ESTARUTIA
a3R
06-OCT-19BeFLOAENCIA
FEQAYLUEAADE EXPEDICION
44100024180124301020100
002235306341
34170000"""

FRENTE = """REPUBLICA DE COLOMBIA
IDENTIFICACION PERSONAL
CEDULA DE CIUDADANIA
17.300.020
GARCIA TORRES
LUIS FERNANDO"""


def test_reverso_mal_leido_se_reconoce():
    r = document_side_classifier.clasificar_cara(REVERSO_RAPID)
    assert r["cara"] == "CEDULA_BACK"


def test_texto_sin_datos_de_reverso_sigue_desconocido():
    for texto in ("HOJA EN BLANCO\n1\n", "Lista de asistencia\nM\n12-OCT-2026", "PAGINA 3 DE 26"):
        assert document_side_classifier.clasificar_cara(texto)["cara"] == "UNKNOWN"


def test_un_frente_no_se_confunde_con_reverso():
    assert document_side_classifier.clasificar_cara(FRENTE)["cara"] == "CEDULA_FRONT"


def test_el_reverso_se_une_a_su_frente():
    paginas = []
    for n, texto in ((1, FRENTE), (2, REVERSO_RAPID)):
        c = document_side_classifier.clasificar_cara(texto)
        paginas.append({"pagina_numero": n, "texto": texto, "layout": None, "motor": "rapid_ocr",
                        "cara": c["cara"], "tipo_documento": c["tipo_documento"], "confianza": c["confianza"],
                        "numero_identificacion": "17300020" if n == 1 else None})
    grupos = document_pairing_service.agrupar_paginas(paginas)
    assert len(grupos) == 1
    assert sorted(grupos[0].pages) == [1, 2]
