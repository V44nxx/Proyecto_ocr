import pytest
from app.services.excel_lookup_service import excel_lookup_service

def test_verificacion_exacta_ambos_lados():
    lookup = {
        "1117489876": {
            "nombre_completo": "DIEGO ARMANDO PARRA HERNANDEZ",
            "nombres": "DIEGO ARMANDO",
            "apellidos": "PARRA HERNANDEZ"
        },
        "16221480": {
            "nombre_completo": "ANTONIO VALENCIA VILLEGAS",
            "nombres": "ANTONIO",
            "apellidos": "VALENCIA VILLEGAS"
        }
    }
    # Caso 1: OCR leyó 1117489876 y DIEGO ARMANDO PARRA HERNANDEZ
    res = excel_lookup_service.verificar_exhaustiva_ocr_excel(
        id_ocr="1117489876",
        nombre_ocr="DIEGO ARMANDO PARRA HERNANDEZ",
        lookup=lookup
    )
    assert res["id_final"] == "1117489876"
    assert res["nombre_final"] == "DIEGO ARMANDO PARRA HERNANDEZ"
    assert res["encontrado_en_excel"] is True
    assert res["discrepancia_excel"] is None
    assert res["estado_registro"] == "VALID"
    assert res["requiere_revision"] is False

def test_verificacion_discrepancia_id_pertenece_a_otro():
    lookup = {
        "16221480": {
            "nombre_completo": "ANTONIO VALENCIA VILLEGAS",
            "nombres": "ANTONIO",
            "apellidos": "VALENCIA VILLEGAS"
        },
        "50123456": {
            "nombre_completo": "MARIA LOPEZ PEREZ",
            "nombres": "MARIA",
            "apellidos": "LOPEZ PEREZ"
        }
    }
    # Caso 2: Documento es de CARLOS GOMEZ, pero OCR extrajo por error 16221480
    res = excel_lookup_service.verificar_exhaustiva_ocr_excel(
        id_ocr="16221480",
        nombre_ocr="CARLOS ALBERTO GOMEZ",
        lookup=lookup
    )
    # NUNCA debe cambiar el nombre a ANTONIO VALENCIA VILLEGAS
    assert res["nombre_final"] == "CARLOS ALBERTO GOMEZ"
    assert res["id_final"] == "16221480"
    assert res["requiere_revision"] is True
    assert res["estado_registro"] == "REVIEW_REQUIRED"
    assert res["discrepancia_excel"] is not None
    assert "ANTONIO VALENCIA VILLEGAS" in res["discrepancia_excel"]["motivo"]

def test_verificacion_autocorreccion_por_nombre_con_id_en_texto():
    lookup = {
        "1117489876": {
            "nombre_completo": "DIEGO ARMANDO PARRA HERNANDEZ",
            "nombres": "DIEGO ARMANDO",
            "apellidos": "PARRA HERNANDEZ"
        }
    }
    # Caso 3: OCR leyó 1117489878 (error de 1 dígito) para DIEGO ARMANDO PARRA
    res = excel_lookup_service.verificar_exhaustiva_ocr_excel(
        id_ocr="1117489878",
        nombre_ocr="DIEGO ARMANDO PARRA HERNANDEZ",
        lookup=lookup,
        texto_ocr="NUMERO 1.117.489.876 DIEGO ARMANDO PARRA HERNANDEZ"
    )
    assert res["id_final"] == "1117489876"
    assert res["id_original_ocr"] == "1117489878"
    assert res["nombre_final"] == "DIEGO ARMANDO PARRA HERNANDEZ"
    assert res["encontrado_en_excel"] is True
    assert res["estado_registro"] == "VALID"

def test_verificacion_no_sobrescribe_homonimo():
    lookup = {
        "99999999": {
            "nombre_completo": "JOSE PEREZ",
            "nombres": "JOSE",
            "apellidos": "PEREZ"
        }
    }
    # Caso 4: Documento tiene JOSE PEREZ con cédula 10203040, que es completamente diferente a 99999999
    res = excel_lookup_service.verificar_exhaustiva_ocr_excel(
        id_ocr="10203040",
        nombre_ocr="JOSE PEREZ",
        lookup=lookup,
        texto_ocr="C.C. 10203040 JOSE PEREZ"
    )
    # NO debe sobrescribir 10203040 con 99999999
    assert res["id_final"] == "10203040"
    assert res["nombre_final"] == "JOSE PEREZ"
    assert res["requiere_revision"] is True
    assert res["discrepancia_excel"] is not None
