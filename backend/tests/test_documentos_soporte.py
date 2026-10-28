"""
Cartas y certificados que no son de identidad ni de antecedentes (bancarios, solicitudes...) dentro de una ficha:
se reconocen para no confundirlos con una cédula, pero no se toma ningún dato de ellos.
Antes, una carta de solicitud se tomaba como frente de una cédula: el destinatario ("Señor: ...")
quedaba como nombre y el número de quien firma como cédula.
"""
from app.services.document_pairing_service import document_pairing_service
from app.services.document_side_classifier import document_side_classifier

CARTA = """N° 18-1-2026-000123
29/9/2026 09:31:44
El Doncello, 28 de septiembre del 2026
Señor:
LUIS ÁNGEL MESA ROA
Director Regional (e) Con Funciones de Subdirector del Centro Tecnológico de la Amazonia
SENA Regional Caquetá
Asunto: Solicitud de formación complementaria en Tecnovigilancia para el Técnico en SF
Ficha 3100001 del Municipio de El Doncello
Cordial Saludo,
Comedidamente me permito solicitar el siguiente programa de formación complementaria
para los aprendices del Técnico en Servicios Farmacéuticos con ficha n° 3100001
Lo anterior con el propósito que los aprendices obtengamos conocimientos adicionales.
Agradezco su oportuna colaboración.
Atentamente,
SANDRA PATRICIA LEON MORA
CC – 1077300214
Vocera Ficha 3100001. Técnico en Servicios Farmacéuticos
Teléfono: 3001234567
Anexo: 17 folios. Copia documento de identidad de los aprendices"""

CERTIFICADO_BANCARIO = """BANCOLOMBIA S.A.
NIT 890.903.938-8
CERTIFICACIÓN BANCARIA
Florencia, 15 de octubre de 2026
A QUIEN INTERESE
Bancolombia certifica que el(la) señor(a) LINA PAOLA CARDONA ROJAS identificado(a) con
cédula de ciudadanía número 1117004512 tiene con nuestra entidad una cuenta de ahorros
número 123-456789-01 abierta desde el 03 de marzo de 2025, la cual se encuentra activa.
La presente certificación se expide a solicitud del interesado.
Cordialmente,
CARLOS EDUARDO RAMIREZ PEÑA
Director de Oficina
CC 79123456"""

CEDULA_AMARILLA = """REPUBLICA DE COLOMBIA
IDENTIFICACION PERSONAL
CEDULA DE CIUDADANIA
NUMERO 1.003.218.765
SUAREZ MEDINA
APELLIDOS
DIANA MARCELA
NOMBRES
FECHA DE NACIMIENTO 14-MAR-2001
EL DONCELLO (CAQUETA)
LUGAR DE NACIMIENTO
1.63 O+ F
ESTATURA G.S. RH SEXO
20-MAR-2019 EL DONCELLO
FECHA Y LUGAR DE EXPEDICION
REGISTRADOR NACIONAL
INDICE DERECHO"""

CEDULA_DIGITAL = """CÉDULA DE CIUDADANÍA REPÚBLICA DE COLOMBIA
NUIP 1.117.004.512
Apellidos CARDONA ROJAS
Nombres LINA PAOLA
Nacionalidad COL Estatura 1.63 Sexo F
Fecha de nacimiento 12 MAR 2006 G.S. O+
Lugar de nacimiento FLORENCIA (CAQUETA)
Fecha y lugar de expedición 15 MAR 2024 FLORENCIA
Fecha de expiración 15 MAR 2034
ICCOL0512345678900001<<<<<<<<<<
0603129F3403151COL1117004512<4
CARDONA<ROJAS<<LINA<PAOLA<<<"""


def test_carta_de_solicitud_es_documento_de_soporte():
    r = document_side_classifier.clasificar_cara(CARTA)
    assert r["tipo_documento"] == "DOCUMENTO_SOPORTE"
    assert r["subtipo"] == "CARTA_O_CERTIFICADO"


def test_certificado_bancario_es_documento_de_soporte():
    r = document_side_classifier.clasificar_cara(CERTIFICADO_BANCARIO)
    assert r["tipo_documento"] == "DOCUMENTO_SOPORTE"
    assert r["subtipo"] == "CERTIFICADO_BANCARIO"


def test_las_cedulas_no_se_confunden_con_documentos_de_soporte():
    for texto in (CEDULA_AMARILLA, CEDULA_DIGITAL):
        r = document_side_classifier.clasificar_cara(texto)
        assert r["tipo_documento"] != "DOCUMENTO_SOPORTE", r


def _pagina(num, tipo, cara, cedula=None, texto="", subtipo=None):
    return {"pagina_numero": num, "texto": texto, "layout": None, "motor": "google_document_ai",
            "cara": cara, "tipo_documento": tipo, "confianza": 0.95, "numero_identificacion": cedula,
            "subtipo": subtipo}


def test_los_antecedentes_se_siguen_tomando():
    texto = ("PROCURADURIA GENERAL DE LA NACION\nCERTIFICADO ORDINARIO No. 123456789\n"
             "La Procuraduría General de la Nación certifica que el(la) señor(a) LINA PAOLA CARDONA ROJAS "
             "identificado(a) con Cédula de ciudadanía número 1117004512 NO REGISTRA SANCIONES NI INHABILIDADES VIGENTES")
    assert document_side_classifier.clasificar_cara(texto)["tipo_documento"] == "CERTIFICADO_ANTECEDENTES"


def test_la_carta_no_se_usa_como_frente_ni_se_agrega_a_la_cedula():
    paginas = [
        _pagina(1, "DOCUMENTO_SOPORTE", "DOCUMENTO_SOPORTE", None, CARTA, "CARTA_O_CERTIFICADO"),
        _pagina(2, "CEDULA_CIUDADANIA", "CEDULA_FRONT", "1077300214"),
        _pagina(3, "CEDULA_CIUDADANIA", "CEDULA_BACK"),
    ]
    grupos = document_pairing_service.agrupar_paginas(paginas)

    assert len(grupos) == 1
    assert grupos[0].pagina_frente == 2
    assert sorted(grupos[0].pages) == [2, 3]


def test_un_certificado_bancario_no_forma_persona():
    paginas = [
        _pagina(1, "CEDULA_CIUDADANIA", "CEDULA_AMBOS_LADOS", "1003218765"),
        _pagina(2, "DOCUMENTO_SOPORTE", "DOCUMENTO_SOPORTE", None, CERTIFICADO_BANCARIO, "CERTIFICADO_BANCARIO"),
    ]
    grupos = document_pairing_service.agrupar_paginas(paginas)

    assert [g.numero_identificacion for g in grupos] == ["1003218765"]
    assert document_pairing_service.agrupar_paginas([paginas[1]]) == []


# ── Flujo completo: la misma ficha subida dos veces ─────────────────

from tests.utilidades_pg import crear_ficha, crear_usuario, pdf_de_prueba, requiere_postgres  # noqa: E402

CERTIFICADO_OTRA_PERSONA = CERTIFICADO_BANCARIO.replace("LINA PAOLA CARDONA ROJAS", "PEDRO PABLO ARIAS GOMEZ")                                                .replace("1117004512", "79555111")
PAGINAS_FICHA = {1: CARTA, 2: CEDULA_AMARILLA, 3: CEDULA_DIGITAL, 4: CERTIFICADO_OTRA_PERSONA}


@requiere_postgres
def test_ficha_con_carta_y_certificado_solo_toma_los_documentos_de_identidad(bd, tmp_path, monkeypatch):
    from app.models.persona import Persona
    from app.services.ocr_service import ocr_service

    # Solo se simula el OCR de imagen; clasificación, agrupación, extracción y guardado son los reales
    monkeypatch.setattr(ocr_service, "_necesita_ocr_imagen", lambda *a, **k: True)
    monkeypatch.setattr(ocr_service, "_ocr_imagen", lambda img_np=None, pagina_num=0, **k: (PAGINAS_FICHA[pagina_num], "google_document_ai", None))

    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    pdf = str(pdf_de_prueba(tmp_path / "3100001.pdf", paginas=4))

    resultados = []
    for nombre in ("3100001.pdf", "3100001 (otra vez).pdf"):
        ficha = crear_ficha(db, ana, nombre, paginas=4, estado="procesando")
        ocr_service.procesar_pdf(pdf, str(ficha.id), db_externa=db)
        db.expire_all()
        personas = {p.numero_identificacion: p for p in db.query(Persona).all()}
        resultados.append((ficha.id, personas))
    db.close()

    (_, primera), (id_segunda, segunda) = resultados
    assert set(primera) == {"1003218765", "1117004512"}                # ni la carta ni el certificado
    assert set(segunda) == {"1003218765", "1117004512"}                # sin duplicados al volver a subir
    assert all(p.documento_id == id_segunda for p in segunda.values())
    assert segunda["1003218765"].pagina_frente == 2
    assert segunda["1117004512"].pagina_frente == 3
    assert not any("LUIS" in (p.nombre_completo or "") or "SANDRA" in (p.nombre_completo or "") for p in segunda.values())
