"""
Cartas y certificados (bancarios, solicitudes) dentro de una ficha:
no son documentos de identidad, pero sí traen al titular. Se toma solo su nombre y su número
(no el destinatario "Señor: ..." ni quien firma) y la persona queda para revisión.
Antes, una carta se tomaba como frente de una cédula: el destinatario quedaba como nombre.
"""
from app.services.document_pairing_service import document_pairing_service
from app.services.document_side_classifier import document_side_classifier

CARTA = """N° 18-1-2026-004974
29/9/2026 09:31:44
El Doncello, 28 de septiembre del 2026
Señor:
LUIS ÁNGEL LOZADA OLAYA
Director Regional (e) Con Funciones de Subdirector del Centro Tecnológico de la Amazonia
SENA Regional Caquetá
Asunto: Solicitud de formación complementaria en Tecnovigilancia para el Técnico en SF
Ficha 3492408 del Municipio de El Doncello
Cordial Saludo,
Comedidamente me permito solicitar el siguiente programa de formación complementaria
para los aprendices del Técnico en Servicios Farmacéuticos con ficha n° 3492408
Lo anterior con el propósito que los aprendices obtengamos conocimientos adicionales.
Agradezco su oportuna colaboración.
Atentamente,
MAYRA YERITZA TOQUICA CASALLAS
CC – 1077847851
Vocera Ficha 3492408. Técnico en Servicios Farmacéuticos
Teléfono: 3143724882
Anexo: 17 folios. Copia documento de identidad de los aprendices"""

CERTIFICADO_BANCARIO = """BANCOLOMBIA S.A.
NIT 890.903.938-8
CERTIFICACIÓN BANCARIA
Florencia, 15 de octubre de 2026
A QUIEN INTERESE
Bancolombia certifica que el(la) señor(a) ANYI YULIANA BALANTA URIBE identificado(a) con
cédula de ciudadanía número 1117501209 tiene con nuestra entidad una cuenta de ahorros
número 123-456789-01 abierta desde el 03 de marzo de 2025, la cual se encuentra activa.
La presente certificación se expide a solicitud del interesado.
Cordialmente,
CARLOS EDUARDO RAMIREZ PEÑA
Director de Oficina
CC 79123456"""

CEDULA_AMARILLA = """REPUBLICA DE COLOMBIA
IDENTIFICACION PERSONAL
CEDULA DE CIUDADANIA
NUMERO 1.006.459.309
ZAPATA CUELLAR
APELLIDOS
ADRIANA ALEJANDRA
NOMBRES
FECHA DE NACIMIENTO 22-FEB-2001
EL DONCELLO (CAQUETA)
LUGAR DE NACIMIENTO
1.63 O+ F
ESTATURA G.S. RH SEXO
08-ABR-2019 EL DONCELLO
FECHA Y LUGAR DE EXPEDICION
REGISTRADOR NACIONAL
INDICE DERECHO"""

CEDULA_DIGITAL = """CÉDULA DE CIUDADANÍA REPÚBLICA DE COLOMBIA
NUIP 1.117.501.209
Apellidos BALANTA URIBE
Nombres ANYI YULIANA
Nacionalidad COL Estatura 1.63 Sexo F
Fecha de nacimiento 26 JUL 2006 G.S. O+
Lugar de nacimiento FLORENCIA (CAQUETA)
Fecha y lugar de expedición 30 JUL 2024 FLORENCIA
Fecha de expiración 30 JUL 2034
ICCOL0516582636440001<<<<<<<<<<
0607269F3407301COL1117501209<4
BALANTA<URIBE<<ANYI<YULIANA<<<"""


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


def test_de_la_carta_se_toma_a_quien_firma_con_su_cedula_y_no_al_destinatario():
    from app.services.extractor_service import extractor_service
    t = extractor_service.extraer_titular_soporte(CARTA)
    assert t["identificacion"] == "1077847851"
    assert t["nombre_completo"] == "MAYRA YERITZA TOQUICA CASALLAS"


def test_del_certificado_bancario_se_toma_al_titular_y_no_al_funcionario():
    from app.services.extractor_service import extractor_service
    t = extractor_service.extraer_titular_soporte(CERTIFICADO_BANCARIO)
    assert t["identificacion"] == "1117501209"
    assert t["nombre_completo"] == "ANYI YULIANA BALANTA URIBE"


def test_titular_con_particulas_y_sin_cedula():
    from app.services.extractor_service import extractor_service
    t = extractor_service.extraer_titular_soporte(
        "El Banco Agrario certifica que MARIA DE LOS ANGELES RUIZ, identificada con cédula de ciudadanía "
        "No. 1.117.000.111, es titular de una cuenta de ahorros")
    assert (t["identificacion"], t["nombre_completo"]) == ("1117000111", "MARIA DE LOS ANGELES RUIZ")
    sin_cc = extractor_service.extraer_titular_soporte(
        "Señor:\nLUIS ANGEL LOZADA\nAsunto: solicitud\nAtentamente,\nla coordinación")
    assert sin_cc["identificacion"] is None


def test_la_carta_del_titular_queda_como_pagina_extra_de_su_cedula():
    paginas = [
        _pagina(1, "DOCUMENTO_SOPORTE", "DOCUMENTO_SOPORTE", "1077847851", CARTA, "CARTA_O_CERTIFICADO"),
        _pagina(2, "CEDULA_CIUDADANIA", "CEDULA_FRONT", "1077847851"),
        _pagina(3, "CEDULA_CIUDADANIA", "CEDULA_BACK"),
    ]
    grupos = document_pairing_service.agrupar_paginas(paginas)

    assert len(grupos) == 1
    assert grupos[0].pagina_frente == 2
    assert grupos[0].tipo_documento == "CEDULA_CIUDADANIA"
    assert sorted(grupos[0].pages) == [1, 2, 3]


def test_certificado_sin_cedula_en_el_pdf_forma_su_propia_persona():
    from app.services.extractor_service import extractor_service
    paginas = [
        _pagina(1, "CEDULA_CIUDADANIA", "CEDULA_AMBOS_LADOS", "1006459309"),
        _pagina(2, "DOCUMENTO_SOPORTE", "DOCUMENTO_SOPORTE", "1117501209", CERTIFICADO_BANCARIO, "CERTIFICADO_BANCARIO"),
    ]
    grupos = document_pairing_service.agrupar_paginas(paginas)
    soporte = [g for g in grupos if g.tipo_documento == "DOCUMENTO_SOPORTE"]

    assert len(grupos) == 2 and len(soporte) == 1
    datos = extractor_service.extraer_grupo(soporte[0])
    assert datos["identificacion"] == "1117501209"
    assert datos["nombre_completo"] == "ANYI YULIANA BALANTA URIBE"
    assert datos["tipo_documento"] == "CERTIFICADO_BANCARIO"
    assert datos["pagina_frente"] == 2


def test_carta_sin_numero_de_titular_no_forma_persona():
    assert document_pairing_service.agrupar_paginas([_pagina(1, "DOCUMENTO_SOPORTE", "DOCUMENTO_SOPORTE")]) == []


# ── Flujo completo: la misma ficha subida dos veces ─────────────────

from tests.utilidades_pg import crear_ficha, crear_usuario, pdf_de_prueba, requiere_postgres  # noqa: E402

CERTIFICADO_OTRA_PERSONA = CERTIFICADO_BANCARIO.replace("ANYI YULIANA BALANTA URIBE", "PEDRO PABLO ARIAS GOMEZ") \
                                               .replace("1117501209", "79555111")
PAGINAS_FICHA = {1: CARTA, 2: CEDULA_AMARILLA, 3: CEDULA_DIGITAL, 4: CERTIFICADO_OTRA_PERSONA}


@requiere_postgres
def test_ficha_con_carta_y_certificado_subida_dos_veces(bd, tmp_path, monkeypatch):
    from app.models.persona import Persona
    from app.services.ocr_service import ocr_service

    # Solo se simula el OCR de imagen; clasificación, agrupación, extracción y guardado son los reales
    monkeypatch.setattr(ocr_service, "_necesita_ocr_imagen", lambda *a, **k: True)
    monkeypatch.setattr(ocr_service, "_ocr_imagen", lambda img_np=None, pagina_num=0, **k: (PAGINAS_FICHA[pagina_num], "google_document_ai", None))

    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    pdf = str(pdf_de_prueba(tmp_path / "3492408.pdf", paginas=4))

    resultados = []
    for nombre in ("3492408.pdf", "3492408 (otra vez).pdf"):
        ficha = crear_ficha(db, ana, nombre, paginas=4, estado="procesando")
        ocr_service.procesar_pdf(pdf, str(ficha.id), db_externa=db)
        db.expire_all()
        personas = {p.numero_identificacion: p for p in db.query(Persona).all()}
        resultados.append((ficha.id, personas))
    db.close()

    (_, primera), (id_segunda, segunda) = resultados
    esperadas = {"1077847851", "1006459309", "1117501209", "79555111"}
    assert set(primera) == esperadas
    assert set(segunda) == esperadas                                   # sin duplicados al volver a subir
    assert all(p.documento_id == id_segunda for p in segunda.values())

    mayra, pedro = segunda["1077847851"], segunda["79555111"]
    assert "MAYRA" in mayra.nombre_completo and "LUIS" not in mayra.nombre_completo
    assert (mayra.tipo_documento, mayra.requiere_revision, mayra.pagina_frente) == ("DOCUMENTO_SOPORTE", True, 1)
    assert "PEDRO PABLO ARIAS GOMEZ" == pedro.nombre_completo
    assert (pedro.tipo_documento, pedro.requiere_revision, pedro.pagina_frente) == ("CERTIFICADO_BANCARIO", True, 4)
    assert segunda["1006459309"].pagina_frente == 2
    assert segunda["1117501209"].pagina_frente == 3
    assert segunda["1006459309"].tipo_documento == "CEDULA_CIUDADANIA"
