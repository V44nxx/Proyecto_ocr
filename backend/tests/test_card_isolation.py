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


def test_aislamiento_cedula_angi_botache():
    """
    Simula exactamente el documento del pantallazo del usuario (pág 5 ficha 3631718):
    Parte superior (margen de hoja fotocopia):
      - ANGI CAROLINA BOTACHE VALERO
      - angiecarolina001@gmail.com
      - 3102894860
    Cédula Frente (físico):
      - NUBLIC DE COLOMBIA (deformación OCR de REPUBLICA DE COLOMBIA)
      - IDENTIFICACION PERSONAL
      - NUMERO 1.117.547.992
      - APELLIDOS
      - BOTACHE VALERO
      - NOMBRES
      - ANGI CAROLINA
      - CAPE (artefacto OCR de firma cursiva inferior)
    Cédula Reverso (físico):
      - FECHA DE NACIMIENTO 25-ABR-1997
      - MILAN
      - (CAQUETA)
      - LUGAR DE NACIMIENTO
      - 1.52 O+ F
      - ESTATURA G.S. RH SEXO
      - 01-DIC-2015 FLORENCIA
      - FECHA Y LUGAR DE EXPEDICION
      - Código de barras PDF417
    """
    from app.utils.name_cleaner import resolver_nombre_completo

    lines = [
        # Encabezado externo tipeado por la aprendiz en la hoja
        PseudoLine("ANGI CAROLINA BOTACHE VALERO", y=0.08),
        PseudoLine("angiecarolina001@gmail.com", y=0.11),
        PseudoLine("3102894860", y=0.14),
        # Frente de la cédula física
        PseudoLine("NUBLIC DE COLOMBIA", y=0.30),
        PseudoLine("IDENTIFICACION PERSONAL", y=0.33),
        PseudoLine("NUMERO 1.117.547.992", y=0.36),
        PseudoLine("APELLIDOS", y=0.39),
        PseudoLine("BOTACHE VALERO", y=0.42),
        PseudoLine("NOMBRES", y=0.45),
        PseudoLine("ANGI CAROLINA", y=0.48),
        PseudoLine("CAPE", y=0.52),  # Ruido de firma
        # Reverso de la cédula física
        PseudoLine("FECHA DE NACIMIENTO 25-ABR-1997", y=0.62, x=0.4),
        PseudoLine("MILAN", y=0.65, x=0.4),
        PseudoLine("(CAQUETA)", y=0.67, x=0.4),
        PseudoLine("LUGAR DE NACIMIENTO", y=0.70, x=0.4),
        PseudoLine("1.52 O+ F", y=0.73, x=0.4),
        PseudoLine("ESTATURA G.S. RH SEXO", y=0.76, x=0.4),
        PseudoLine("01-DIC-2015 FLORENCIA", y=0.79, x=0.4),
        PseudoLine("FECHA Y LUGAR DE EXPEDICION", y=0.82, x=0.4),
    ]

    res = spatial_field_extractor.extraer_cedula_universal(lines, page_num=5)

    # 1. Identificación debe ser el número real de cédula sin incluir celular
    assert res["identificacion"]["value"] == "1117547992"
    assert res["identificacion"]["status"] == "VALID"

    # 2. Apellidos y Nombres exactos de la cédula física sin ruido NUBLIC ni CAPE
    assert res["apellidos"]["value"] == "BOTACHE VALERO"
    assert res["nombres"]["value"] == "ANGI CAROLINA"

    # 3. Resolución de nombre completo sin ruido
    nom_completo = resolver_nombre_completo(
        nombres=res["nombres"]["value"],
        apellidos=res["apellidos"]["value"]
    )
    assert nom_completo == "ANGI CAROLINA BOTACHE VALERO"
    assert "NUBLIC" not in nom_completo
    assert "CAPE" not in nom_completo

    # 4. Fecha de nacimiento
    assert res["fecha_nacimiento"]["value"] == "1997-04-25"
    assert res["fecha_nacimiento"]["status"] == "VALID"


def test_separar_nombres_pegados():
    """Valida la separación de nombres o apellidos fusionados por el OCR."""
    from app.utils.name_cleaner import separar_nombres_pegados

    assert separar_nombres_pegados("BOTACHEVALERO") == "BOTACHE VALERO"
    assert separar_nombres_pegados("ANGICAROLINA") == "ANGI CAROLINA"
    assert separar_nombres_pegados("MURCIACORREDOR") == "MURCIA CORREDOR"
    assert separar_nombres_pegados("SALASNARANJO") == "SALAS NARANJO"
    assert separar_nombres_pegados("APELLIDOSBOTACHE") == "APELLIDOS BOTACHE"
    assert separar_nombres_pegados("NOMBRESANGI") == "NOMBRES ANGI"
    assert separar_nombres_pegados("BotacheValero") == "Botache Valero"


def test_header_rescue_gloria_botache_sin_etiquetas_visibles():
    """
    Caso Screenshot 1 (Pág. 10 - Cédula 1006484792):
    Documento oscuro/fotocopia donde el OCR de la cédula no pudo extraer etiquetas APELLIDOS/NOMBRES,
    pero la cabecera digital de la página contiene:
      GLORIA AYDE BOTACHE DAZA
      1006484792
    El sistema debe rescatar el nombre completo y apellidos desde la cabecera,
    evitando quedar en 'POR REVISAR' aun cuando no figure en el Excel.
    """
    from app.utils.name_cleaner import resolver_nombre_completo

    lines = [
        # Cabecera digital tipeada en la hoja escaneada
        PseudoLine("GLORIA AYDE BOTACHE DAZA", y=0.07),
        PseudoLine("1006484792", y=0.10),
        # Frente de cédula física con baja visibilidad / sin etiquetas legibles
        PseudoLine("REPUBLICA DE COLOMBIA", y=0.35),
        PseudoLine("IDENTIFICACION PERSONAL", y=0.38),
        PseudoLine("1.006.484.792", y=0.42),
        # Texto borroso del frente sin rótulos APELLIDOS ni NOMBRES
        # Reverso de cédula
        PseudoLine("FECHA DE NACIMIENTO 03-MAY-2000", y=0.65, x=0.4),
        PseudoLine("MILAN (CAQUETA)", y=0.68, x=0.4),
        PseudoLine("1.52 O+ F", y=0.72, x=0.4),
        PseudoLine("FECHA Y LUGAR DE EXPEDICION", y=0.78, x=0.4),
    ]

    res = spatial_field_extractor.extraer_cedula_universal(lines, page_num=10)

    # Identificación extraída
    assert res["identificacion"]["value"] == "1006484792"
    assert res["identificacion"]["status"] == "VALID"

    # Nombres y apellidos rescatados del encabezado digital
    assert res["nombres"]["value"] == "GLORIA AYDE"
    assert res["apellidos"]["value"] == "BOTACHE DAZA"
    assert res["nombres"]["status"] == "VALID"
    assert res["apellidos"]["status"] == "VALID"

    nom_completo = resolver_nombre_completo(
        nombres=res["nombres"]["value"],
        apellidos=res["apellidos"]["value"]
    )
    assert nom_completo == "GLORIA AYDE BOTACHE DAZA"
    assert nom_completo != "POR REVISAR"


def test_deduplicacion_nombres_repetidos_ocr():
    """
    Caso Screenshot 2:
    Evita que variaciones OCR o repeticiones de firmas se concatenen:
    'ANGUIE CAROLINA BOTACHE' + 'ANGI CAROLINA' -> 'ANGUIE CAROLINA BOTACHE'
    (sin repetir 'CAROLINA' ni concatenar 'ANGI CAROLINA').
    """
    from app.utils.name_cleaner import resolver_nombre_completo

    # 1. Nombres contiene apellidos y apellidos repite nombres
    res1 = resolver_nombre_completo("ANGUIE CAROLINA BOTACHE", "ANGI CAROLINA")
    assert res1 == "ANGUIE CAROLINA BOTACHE"
    assert res1.count("CAROLINA") == 1
    assert "ANGI" not in res1.split() or "ANGUIE" not in res1.split()

    # 2. Inverso
    res2 = resolver_nombre_completo("ANGI CAROLINA", "ANGUIE CAROLINA BOTACHE")
    assert res2 == "ANGUIE CAROLINA BOTACHE"

    # 3. Registro corrupto previo en actual
    res3 = resolver_nombre_completo("", "", actual="ANGUIE CAROLINA BOTACHE ANGI CAROLINA")
    assert res3 == "ANGUIE CAROLINA BOTACHE"
    assert res3.count("CAROLINA") == 1

    # 4. Apellido repetido legítimo en Colombia (paterno y materno) se preserva
    res4 = resolver_nombre_completo("JUAN CARLOS", "RODRIGUEZ RODRIGUEZ")
    assert res4 == "JUAN CARLOS RODRIGUEZ RODRIGUEZ"

    # 5. Apellido que se coló en nombres
    res5 = resolver_nombre_completo("ANGI CAROLINA BOTACHE", "BOTACHE VALERO")
    assert res5 == "ANGI CAROLINA BOTACHE VALERO"
    assert res5.count("BOTACHE") == 1


def test_casos_reales_screenshot_desegmentacion_y_alucinacion():
    """
    Casos reales reportados por el usuario en la captura de pantalla:
    1. 'GLORIAAAYDE BOTACHEDAZA' -> 'GLORIA AYDE BOTACHE DAZA'
    2. 'ANGIUECUVOLINA BO TACHE ANGI CAROLINA' -> 'BOTACHE ANGI CAROLINA'
    """
    from app.utils.name_cleaner import resolver_nombre_completo, separar_nombres_pegados, limpiar_tokens_ruido

    # Caso 1: Palabras pegadas con vocales de frontera y apellido DAZA
    t1 = "GLORIAAAYDE BOTACHEDAZA"
    assert separar_nombres_pegados(t1) == "GLORIA AYDE BOTACHE DAZA"
    assert resolver_nombre_completo("", "", actual=t1) == "GLORIA AYDE BOTACHE DAZA"

    # Caso 2: Alucinación OCR + token dividido 'BO TACHE'
    t2 = "ANGIUECUVOLINA BO TACHE ANGI CAROLINA"
    res2 = resolver_nombre_completo("", "", actual=t2)
    assert "ANGIUECUVOLINA" not in res2
    assert "BOTACHE" in res2
    assert "ANGI" in res2
    assert "CAROLINA" in res2
    assert res2 == "BOTACHE ANGI CAROLINA"


