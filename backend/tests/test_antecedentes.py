"""
Pruebas unitarias para el flujo completo de Certificados de Antecedentes (CERTIFICADO_ANTECEDENTES)
- Clasificación de páginas (Página 1 con titular, Página 2+ con firma de funcionario)
- Agrupación determinista en grupos de documentos sin duplicación de personas
- Extracción de Nombre Completo y Cédula (excluyendo fechas y campos no aplicables)
- Validación de completitud sin exigir fecha de nacimiento
"""
import pytest
from app.services.document_side_classifier import document_side_classifier
from app.services.document_pairing_service import document_pairing_service
from app.services.extractor_service import extractor_service
from app.services.exportacion_service import exportacion_service
from app.utils.validators import ValidadorColombia


def test_clasificacion_antecedentes_hoja_1():
    texto_p1 = (
        "REPÚBLICA DE COLOMBIA\n"
        "PROCURADURÍA GENERAL DE LA NACIÓN\n"
        "CERTIFICADO DE ANTECEDENTES\n"
        "CERTIFICADO ORDINARIO\n"
        "No. 263152504\n"
        "Hoja 1 de 2\n"
        "EL SUSCRITO JEFE DE LA DIVISIÓN DEL CENTRO DE ATENCIÓN AL CIUDADANO\n"
        "CERTIFICA:\n"
        "Que una vez consultado el Sistema de Información de Registro de Sanciones e Inhabilidades (SIRI),\n"
        "el(la) señor(a) EMERSON MURCIA CORREDOR identificado(a) con Cédula de ciudadanía número 1082987654:\n"
        "NO REGISTRA SANCIONES NI INHABILIDADES VIGENTES"
    )
    res = document_side_classifier.clasificar_cara(texto_p1)
    assert res["tipo_documento"] == "CERTIFICADO_ANTECEDENTES"
    assert res["cara"] == "ANTECEDENTES_FRONT"
    assert res["certificado_numero"] == "263152504"
    assert res["hoja_actual"] == 1
    assert res["hoja_total"] == 2
    assert res["tiene_titular"] is True


def test_clasificacion_antecedentes_hoja_2_firma():
    texto_p2 = (
        "REPÚBLICA DE COLOMBIA\n"
        "PROCURADURÍA GENERAL DE LA NACIÓN\n"
        "CERTIFICADO DE ANTECEDENTES\n"
        "CERTIFICADO ORDINARIO\n"
        "No. 263152504\n"
        "Hoja 2 de 2\n"
        "ADVERTENCIA\n"
        "La información suministrada por el SIRI se presume veraz.\n"
        "Firma mecánica autorizada:\n"
        "Mario Enrique Castro González\n"
        "Jefe División de Relacionamiento Con El Ciudadano"
    )
    res = document_side_classifier.clasificar_cara(texto_p2)
    assert res["tipo_documento"] == "CERTIFICADO_ANTECEDENTES"
    assert res["cara"] == "ANTECEDENTES_BACK"
    assert res["certificado_numero"] == "263152504"
    assert res["hoja_actual"] == 2
    assert res["hoja_total"] == 2
    assert res["tiene_titular"] is False


def test_agrupacion_antecedentes_multipage_sin_duplicados():
    # Simulamos un lote con 2 certificados: uno de 2 páginas y uno de 1 página
    paginas = [
        # Certificado 1 (2 páginas)
        {
            "pagina_numero": 1,
            "tipo_documento": "CERTIFICADO_ANTECEDENTES",
            "cara": "FRENTE",
            "certificado_numero": "10001",
            "hoja_actual": 1,
            "hoja_total": 2,
            "tiene_titular": True,
            "confianza": 0.98,
        },
        {
            "pagina_numero": 2,
            "tipo_documento": "CERTIFICADO_ANTECEDENTES",
            "cara": "REVERSO",
            "certificado_numero": "10001",
            "hoja_actual": 2,
            "hoja_total": 2,
            "tiene_titular": False,
            "confianza": 0.95,
        },
        # Certificado 2 (1 página)
        {
            "pagina_numero": 3,
            "tipo_documento": "CERTIFICADO_ANTECEDENTES",
            "cara": "FRENTE",
            "certificado_numero": "10002",
            "hoja_actual": 1,
            "hoja_total": 1,
            "tiene_titular": True,
            "confianza": 0.98,
        },
    ]

    grupos = document_pairing_service.agrupar_paginas(paginas)
    # Debe haber exactamente 2 grupos, NO 3
    assert len(grupos) == 2

    # Grupo 1: Páginas 1 y 2
    g1 = grupos[0]
    assert g1.tipo_documento == "CERTIFICADO_ANTECEDENTES"
    assert g1.pages == [1, 2]

    # Grupo 2: Página 3
    g2 = grupos[1]
    assert g2.tipo_documento == "CERTIFICADO_ANTECEDENTES"
    assert g2.pages == [3]


def test_extraccion_antecedentes():
    texto = (
        "REPÚBLICA DE COLOMBIA\n"
        "PROCURADURÍA GENERAL DE LA NACIÓN\n"
        "CERTIFICADO DE ANTECEDENTES\n"
        "CERTIFICADO ORDINARIO\n"
        "No. 263152504\n"
        "Hoja 1 de 2\n"
        "Que una vez consultado el Sistema SIRI,\n"
        "el(la) señor(a) JUAN CARLOS PEREZ GOMEZ identificado(a) con Cédula de ciudadanía número 79.845.123:\n"
        "NO REGISTRA SANCIONES NI INHABILIDADES VIGENTES"
    )

    resultado = extractor_service._extraer_antecedentes(texto)

    assert resultado["identificacion"] == "79845123"
    assert resultado["nombre_completo"] == "JUAN CARLOS PEREZ GOMEZ"
    assert resultado["nombres"] == "JUAN CARLOS"
    assert resultado["apellidos"] == "PEREZ GOMEZ"
    assert resultado["tipo_documento"] == "CERTIFICADO_ANTECEDENTES"
    assert resultado["detalles_campos"]["fecha_nacimiento"]["status"] == "NOT_APPLICABLE"


def test_validacion_completitud_antecedentes():
    # Para antecedentes, NO se debe requerir fecha de nacimiento
    valido, motivos = ValidadorColombia.evaluar_persona_completa(
        numero_identificacion="79845123",
        nombre_completo="JUAN CARLOS PEREZ GOMEZ",
        fecha_nacimiento=None,
        nombres="JUAN CARLOS",
        apellidos="PEREZ GOMEZ",
        tipo_documento="CERTIFICADO_ANTECEDENTES"
    )

    assert valido is True
    assert not any("Fecha de nacimiento" in m for m in motivos)


def test_exportacion_tipo_documento_antecedentes():
    tipo_resuelto = exportacion_service._resolver_tipo_documento("CERTIFICADO_ANTECEDENTES")
    assert tipo_resuelto == "Certificado de Antecedentes"


def test_agrupacion_antecedentes_3_paginas_y_extraccion():
    # Certificado de 3 páginas:
    # Pág 1: titular y consulta
    # Pág 2: detalle/anotaciones
    # Pág 3: firma de funcionario
    p1 = {
        "pagina_numero": 1,
        "tipo_documento": "CERTIFICADO_ANTECEDENTES",
        "cara": "ANTECEDENTES_FRONT",
        "certificado_numero": "304290303",
        "hoja_actual": 1,
        "hoja_total": 3,
        "tiene_titular": True,
        "numero_identificacion": "1030580731",
        "texto": (
            "PROCURADURÍA GENERAL DE LA NACIÓN\n"
            "CERTIFICADO DE ANTECEDENTES\n"
            "CERTIFICADO ORDINARIO No. 304290303\n"
            "Hoja 1 de 03\n"
            "el(la) señor(a) ANDRES CAMILO PEREZ BELLO identificado(a) con Cédula de ciudadanía número 1030580731:\n"
            "NO REGISTRA SANCIONES NI INHABILIDADES VIGENTES"
        )
    }
    p2 = {
        "pagina_numero": 2,
        "tipo_documento": "CERTIFICADO_ANTECEDENTES",
        "cara": "ANTECEDENTES_BACK",
        "certificado_numero": "304290303",
        "hoja_actual": 2,
        "hoja_total": 3,
        "tiene_titular": False,
        "numero_identificacion": None,
        "texto": (
            "PROCURADURÍA GENERAL DE LA NACIÓN\n"
            "CERTIFICADO DE ANTECEDENTES\n"
            "CERTIFICADO ORDINARIO No. 304290303\n"
            "Hoja 2 de 03\n"
            "REGISTRO DE INHABILIDADES Y SANCIONES - ANEXO CONTINUACIÓN"
        )
    }
    p3 = {
        "pagina_numero": 3,
        "tipo_documento": "CERTIFICADO_ANTECEDENTES",
        "cara": "ANTECEDENTES_BACK",
        "certificado_numero": "304290303",
        "hoja_actual": 3,
        "hoja_total": 3,
        "tiene_titular": False,
        "numero_identificacion": None,
        "texto": (
            "PROCURADURÍA GENERAL DE LA NACIÓN\n"
            "CERTIFICADO DE ANTECEDENTES\n"
            "CERTIFICADO ORDINARIO No. 304290303\n"
            "Hoja 3 de 03\n"
            "Mario Enrique Castro González\n"
            "Jefe División de Relacionamiento Con El Ciudadano"
        )
    }

    grupos = document_pairing_service.agrupar_paginas([p1, p2, p3])
    # Debe haber exactamente 1 solo grupo que abarque las 3 páginas
    assert len(grupos) == 1
    g = grupos[0]
    assert g.tipo_documento == "CERTIFICADO_ANTECEDENTES"
    assert g.pages == [1, 2, 3]

    # Extracción consolidada del grupo
    datos = extractor_service.extraer_grupo(g)
    assert datos["identificacion"] == "1030580731"
    assert datos["nombre_completo"] == "ANDRES CAMILO PEREZ BELLO"
    assert datos["estado_registro"] == "VALID"
    assert datos["requiere_revision"] is False


def test_caso_real_captura_usuario_dos_paginas_sin_duplicado():
    # Simula el caso exacto de la captura donde la hoja 2 causaba 'Sin doc. POR REVISAR'
    texto_p1 = (
        "PROCURADURÍA GENERAL DE LA NACIÓN\n"
        "CERTIFICADO DE ANTECEDENTES\n"
        "CERTIFICADO ORDINARIO No. 304290303\n"
        "Hoja 1 de 02\n"
        "el(la) señor(a) ANDRES CAMILO PEREZ BELLO identificado(a) con Cédula de ciudadanía número 1030580731:\n"
        "NO REGISTRA SANCIONES NI INHABILIDADES VIGENTES"
    )
    texto_p2 = (
        "PROCURADURÍA GENERAL DE LA NACIÓN\n"
        "CERTIFICADO DE ANTECEDENTES\n"
        "CERTIFICADO ORDINARIO No. 304290303\n"
        "Hoja 2 de 02\n"
        "Mario Enrique Castro González\n"
        "Jefe División de Relacionamiento Con El Ciudadano"
    )

    c1 = document_side_classifier.clasificar_cara(texto_p1)
    c2 = document_side_classifier.clasificar_cara(texto_p2)

    assert c1["tiene_titular"] is True
    assert c2["tiene_titular"] is False
    assert c2["hoja_actual"] == 2

    # Simulamos el flujo de páginas procesadas
    p1 = {
        "pagina_numero": 1,
        "tipo_documento": c1["tipo_documento"],
        "cara": c1["cara"],
        "certificado_numero": c1["certificado_numero"],
        "hoja_actual": c1["hoja_actual"],
        "hoja_total": c1["hoja_total"],
        "tiene_titular": c1["tiene_titular"],
        "numero_identificacion": "1030580731",
        "texto": texto_p1,
    }
    p2 = {
        "pagina_numero": 2,
        "tipo_documento": c2["tipo_documento"],
        "cara": c2["cara"],
        "certificado_numero": c2["certificado_numero"],
        "hoja_actual": c2["hoja_actual"],
        "hoja_total": c2["hoja_total"],
        "tiene_titular": c2["tiene_titular"],
        "numero_identificacion": None,
        "texto": texto_p2,
    }

    grupos = document_pairing_service.agrupar_paginas([p1, p2])
    # Exactamente 1 grupo, CERO duplicados, CERO personas "Sin doc."
    assert len(grupos) == 1
    g = grupos[0]
    assert g.pages == [1, 2]

    res = extractor_service.extraer_grupo(g)
    assert res["identificacion"] == "1030580731"
    assert res["nombre_completo"] == "ANDRES CAMILO PEREZ BELLO"
    assert res["estado_registro"] == "VALID"

