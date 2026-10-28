"""
RapidOCR a veces junta palabras que en la cédula van separadas: «NUMERO1.008.773.710», «SANTIAGOMANUEL».
Con fichas inventadas (números y nombres al azar, de nadie).
"""
import cv2
import numpy as np
import pytest

from app.services.ocr_service import ocr_service


@pytest.mark.parametrize("linea, esperado", [
    ("NUMERO1.008.773.710", "1008773710"),
    ("NUMERO1.033.948.892", "1033948892"),
    ("NÚMERO1008773710", "1008773710"),
    ("NUMERO 1.097.943.834", "1097943834"),
])
def test_numero_pegado_a_la_palabra_numero(linea, esperado):
    texto = f"REPUBLICA DE COLOMBIA\nIDENTIFICACION PERSONAL\nCEDULA DE CIUDADANIA\n{linea}\nRAMIREZMARTINEZ\nAPELLIDOS"
    assert ocr_service.parser._extraer_identificacion(texto, texto.split("\n")) == esperado


def test_el_codigo_del_reverso_sigue_leyendose_con_letras_pegadas():
    texto = "INDICE DERECHO\n9512243F3501232C0L1117266865<1"
    assert ocr_service.parser._extraer_identificacion(texto, texto.split("\n")) == "1117266865"


@pytest.mark.parametrize("pegado, separado", [
    ("SOFIAFERNANDA", "SOFIA FERNANDA"),
    ("MATEOANDRES", "MATEO ANDRES"),
    ("JULIANAMARCELA", "JULIANA MARCELA"),
    ("GOMEZVARGAS", "GOMEZ VARGAS"),
    ("RAMIREZMARTINEZ", "RAMIREZ MARTINEZ"),
])
def test_nombres_frecuentes_pegados_se_separan(pegado, separado):
    from app.utils.name_cleaner import separar_nombres_pegados
    assert separar_nombres_pegados(pegado) == separado


@pytest.mark.parametrize("nombre", ["CAROLINA", "FLORALBA", "ROSALBA", "MARIANA", "JULIANA", "SARAH", "JOHANN", "ALBAN", "MARCOS"])
def test_un_nombre_que_contiene_otros_no_se_parte_ni_se_recorta(nombre):
    from app.utils.name_cleaner import separar_nombres_pegados
    assert separar_nombres_pegados(nombre) == nombre


def test_fernanda_es_un_nombre_del_diccionario_y_no_un_parecido_a_fernando():
    from app.services.name_dictionary_service import NameDictionaryService
    evaluacion = NameDictionaryService().evaluar_palabra("FERNANDA")
    assert "dictionary_exact_name" in evaluacion["evidence"] and evaluacion["nombre_score"] >= 0.95
    assert not any("FERNANDO" in e for e in evaluacion["evidence"])
