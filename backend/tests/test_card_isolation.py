"""
Pruebas de aislamiento estricto del documento físico (Cédula de Ciudadanía Colombiana).
Garantiza:
1. Veto a textos externos a la cédula (notas en fotocopia, teléfonos celulares, membretes).
2. Rechazo de números de teléfono celular (10 dígitos con prefijo 3xx) como cédula.
3. Extracción correcta de Fecha de Nacimiento en Cédula Amarilla Holográfica (donde el rótulo no existe en el plástico).
"""
import pytest
from app.services.spatial_field_extractor import spatial_field_extractor
from app.services.extractor_service import extractor_service
from app.utils.validators import validador


class PseudoLine:
    def __init__(self, text: str, y: float, x: float = 0.2, w: float = 0.5, h: float = 0.03):
        self.text = text
        self.y = y
        self.x = x
        self.w = w
        self.h = h
        self.confidence = 0.95


def test_rechazo_telefonos_celulares_colombianos():
    """Valida que números celulares de 10 dígitos (prefijo 3xx) no sean aceptados como cédula."""
    telefonos = [
        "3105701005",
        "3201234567",
        "3009876543",
        "3158765432",
        "3501234567",
        "3012345678"
    ]
    for tel in telefonos:
        valido, msg = validador.validar_cedula(tel)
        assert not valido, f"El teléfono {tel} no debe ser aceptado como cédula"
        assert "teléfono celular" in msg.lower() or "celular" in msg.lower()

    # Cédulas legítimas colombianas sí deben ser aceptadas
    cedulas_validas = [
        "30507543",     # 8 dígitos
        "1006506310",   # 10 dígitos NUIP (inicia con 1)
        "1117489876",   # 10 dígitos NUIP (inicia con 1)
        "16221480"      # 8 dígitos
    ]
    for ced in cedulas_validas:
        valido, num = validador.validar_cedula(ced)
        assert valido, f"La cédula legítima {ced} debe ser válida: {num}"


def test_aislamiento_cedula_con_encabezado_fotocopia_y_telefono():
    """
    Simula el documento del screenshot del usuario:
    Parte superior (margen):
      - CC. 30507543 MARITZA GUTIERREZ MORENO
      - 3105701005 (Teléfono)
    Cédula Frente (físico):
      - REPUBLICA DE COLOMBIA
      - IDENTIFICACION PERSONAL
      - CEDULA DE CIUDADANIA
      - NUMERO 30.507.543
      - GUTIERREZ MORENO / APELLIDOS
      - MARITZA / NOMBRES
    Cédula Reverso (físico):
      - 12-OCT-1981
      - BOGOTA D.C. (CUNDINAMARCA)
      - LUGAR DE NACIMIENTO
      - 1.55 O+ F
      - ESTATURA G.S. RH SEXO
      - 30-MAR-2000 FLORENCIA
      - FECHA Y LUGAR DE EXPEDICION
      - Código de barras PDF417
    """
    lines = [
        PseudoLine("CC. 30507543 MARITZA GUTIERREZ MORENO", y=0.05),
        PseudoLine("3105701005", y=0.12),
        PseudoLine("REPUBLICA DE COLOMBIA", y=0.25),
        PseudoLine("IDENTIFICACION PERSONAL", y=0.28),
        PseudoLine("CEDULA DE CIUDADANIA", y=0.31),
        PseudoLine("NUMERO 30.507.543", y=0.34),
        PseudoLine("GUTIERREZ MORENO", y=0.37),
        PseudoLine("APELLIDOS", y=0.40),
        PseudoLine("MARITZA", y=0.43),
        PseudoLine("NOMBRES", y=0.46),
        PseudoLine("12-OCT-1981", y=0.60, x=0.4),
        PseudoLine("BOGOTA D.C.", y=0.63, x=0.4),
        PseudoLine("(CUNDINAMARCA)", y=0.65, x=0.4),
        PseudoLine("LUGAR DE NACIMIENTO", y=0.68, x=0.4),
        PseudoLine("1.55 O+ F", y=0.71, x=0.4),
        PseudoLine("ESTATURA G.S. RH SEXO", y=0.74, x=0.4),
        PseudoLine("30-MAR-2000 FLORENCIA", y=0.77, x=0.4),
        PseudoLine("FECHA Y LUGAR DE EXPEDICION", y=0.80, x=0.4),
        PseudoLine("A - 1900100-50158434-F-0030507543-20070528 00507 071488 02 210595690", y=0.85),
    ]

    res = spatial_field_extractor.extraer_cedula_universal(lines, page_num=1)

    # 1. Identificación debe ser el número del documento, NUNCA el teléfono celular
    assert res["identificacion"]["value"] == "30507543"
    assert res["identificacion"]["status"] == "VALID"

    # 2. Nombres y apellidos extraídos de la cédula física
    assert res["apellidos"]["value"] == "GUTIERREZ MORENO"
    assert res["nombres"]["value"] == "MARITZA"

    # 3. Fecha de nacimiento extraída del reverso aunque no tenga rótulo "FECHA DE NACIMIENTO"
    assert res["fecha_nacimiento"]["value"] == "1981-10-12"
    assert res["fecha_nacimiento"]["status"] == "VALID"

    # 4. Fecha de expedición
    assert res["fecha_expedicion"]["value"] == "2000-03-30"
    assert res["fecha_expedicion"]["status"] == "VALID"

    # 5. Lugar de expedición
    assert res["lugar_expedicion"]["value"] == "FLORENCIA"

    # 6. Sexo
    assert res["sexo"]["value"] == "F"

    # 7. Evaluación completa: debe ser 100% válida sin requerir revisión por asistente
    es_valido, motivos = validador.evaluar_persona_completa(
        numero_identificacion=res["identificacion"]["value"],
        nombres=res["nombres"]["value"],
        apellidos=res["apellidos"]["value"],
        nombre_completo=f"{res['nombres']['value']} {res['apellidos']['value']}",
        fecha_nacimiento=res["fecha_nacimiento"]["value"],
        fecha_expedicion=res["fecha_expedicion"]["value"],
        lugar_expedicion=res["lugar_expedicion"]["value"],
        sexo=res["sexo"]["value"],
        confianza=95.0
    )
    assert es_valido, f"La persona debe quedar marcada como válida sin motivos de revisión: {motivos}"
    assert len(motivos) == 0


def test_fecha_nacimiento_variantes_ocr():
    """Valida que variantes OCR frecuentes como '12-0CT-1981' o '12.OCT.1981' se reconozcan."""
    lines_variante = [
        PseudoLine("REPUBLICA DE COLOMBIA", y=0.25),
        PseudoLine("NUMERO 30.507.543", y=0.34),
        PseudoLine("GUTIERREZ MORENO", y=0.37),
        PseudoLine("APELLIDOS", y=0.40),
        PseudoLine("MARITZA", y=0.43),
        PseudoLine("NOMBRES", y=0.46),
        PseudoLine("12-0CT-1981", y=0.60, x=0.4),  # 0CT con cero
        PseudoLine("BOGOTA D.C.", y=0.63, x=0.4),
        PseudoLine("LUGAR DE NACIMIENTO", y=0.68, x=0.4),
        PseudoLine("30-MAR-2000 FLORENCIA", y=0.77, x=0.4),
        PseudoLine("FECHA Y LUGAR DE EXPEDICION", y=0.80, x=0.4),
    ]

    res = spatial_field_extractor.extraer_cedula_universal(lines_variante, page_num=1)
    assert res["fecha_nacimiento"]["value"] == "1981-10-12"
    assert res["fecha_expedicion"]["value"] == "2000-03-30"
