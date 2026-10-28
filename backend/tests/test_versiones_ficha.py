"""
Subir otra vez una ficha que ya existe (mismo número en el nombre del archivo):
- la API avisa que la ficha existe, para que el usuario elija
- reemplazar: una sola ficha en la lista; quien no está en el PDF nuevo no se borra, queda para revisión
- agregar como otra parte: las personas nuevas quedan en la ficha existente
En ningún caso se duplican personas.
"""
import json
import uuid

import pytest

from app.models.documento import Documento
from app.models.persona import Persona
from tests.test_documentos_soporte import CARTA, CEDULA_AMARILLA, CEDULA_DIGITAL, CERTIFICADO_OTRA_PERSONA
from tests.utilidades_pg import cabecera, crear_usuario, pdf_de_prueba, requiere_postgres

DIANA, LINA, CAROLINA = "1003218765", "1117004512", "1098765432"
CEDULA_CAROLINA = (CEDULA_AMARILLA.replace("1.003.218.765", "1.098.765.432")
                   .replace("SUAREZ MEDINA", "RAMIREZ LOPEZ").replace("DIANA MARCELA", "CAROLINA ANDREA"))


@pytest.fixture
def ocr_simulado(monkeypatch):
    """Solo se simula la lectura de imagen; clasificación, agrupación, extracción y guardado son los reales"""
    from app.services.ocr_service import ocr_service
    paginas = {}
    monkeypatch.setattr(ocr_service, "_necesita_ocr_imagen", lambda *a, **k: True)
    monkeypatch.setattr(ocr_service, "_ocr_imagen",
                        lambda img_np=None, pagina_num=0, **k: (paginas[pagina_num], "google_document_ai", None))
    return paginas


def _subir(api, usuario, tmp_path, ocr_simulado, nombre, textos, acciones=None):
    ocr_simulado.clear()
    ocr_simulado.update({i + 1: t for i, t in enumerate(textos)})
    pdf = pdf_de_prueba(tmp_path / f"{uuid.uuid4()}.pdf", paginas=len(textos))
    datos = {"acciones": json.dumps(acciones)} if acciones else None
    with open(pdf, "rb") as f:
        r = api.post("/api/documentos/upload", headers=usuario, data=datos,
                     files=[("files", (nombre, f.read(), "application/pdf"))])
    assert r.status_code == 202, r.text
    return r.json()["documentos"][0]


def _personas(bd):
    db = bd.SessionLocal()
    personas = {p.numero_identificacion: (p.documento_id, p.documento_pdf_id, p.requiere_revision,
                                          (p.detalles_campos or {}).get("motivos_revision") or [])
                for p in db.query(Persona).all()}
    total = db.query(Persona).count()
    db.close()
    return personas, total


def _fichas_en_lista(api, usuario):
    r = api.get("/api/documentos", headers=usuario, params={"solo_subida": True})
    return [d["id"] for d in r.json()]


@requiere_postgres
def test_avisa_que_la_ficha_ya_existe(bd, api, tmp_path, ocr_simulado):
    db = bd.SessionLocal()
    ana = cabecera(crear_usuario(db, "ana@example.com"))
    db.close()
    primera = _subir(api, ana, tmp_path, ocr_simulado, "3100001.pdf", [CEDULA_AMARILLA, CEDULA_DIGITAL])

    r = api.post("/api/documentos/fichas-existentes", headers=ana,
                 json={"nombres": ["DOCUMENTOS FICHA 3100001.pdf", "3100002.pdf", "cedulas.pdf"]})

    assert r.status_code == 200
    existente, otra, sin_numero = r.json()
    assert existente["numero_ficha"] == "3100001"
    assert existente["existente"]["id"] == primera["id"]
    assert existente["existente"]["total_personas"] == 2
    assert otra["existente"] is None
    assert sin_numero["numero_ficha"] is None and sin_numero["existente"] is None


@requiere_postgres
def test_reemplazar_deja_una_ficha_sin_duplicar_ni_borrar_personas(bd, api, tmp_path, ocr_simulado):
    db = bd.SessionLocal()
    ana = cabecera(crear_usuario(db, "ana@example.com"))
    db.close()
    vieja = _subir(api, ana, tmp_path, ocr_simulado, "3100001.pdf",
                   [CARTA, CEDULA_AMARILLA, CEDULA_DIGITAL, CEDULA_CAROLINA, CERTIFICADO_OTRA_PERSONA])
    # Versión corregida: Carolina ya no está
    nueva = _subir(api, ana, tmp_path, ocr_simulado, "3100001 corregida.pdf", [CEDULA_AMARILLA, CEDULA_DIGITAL],
                   acciones=[{"archivo": "3100001 corregida.pdf", "accion": "reemplazar", "documento_id": vieja["id"]}])

    personas, total = _personas(bd)
    id_vieja, id_nueva = uuid.UUID(vieja["id"]), uuid.UUID(nueva["id"])

    assert total == 3                                                   # ni la carta ni el certificado
    assert all(p[0] == id_nueva for p in personas.values())             # todas en la ficha nueva
    assert personas[DIANA][1] is None and personas[LINA][1] is None   # se ven en el PDF nuevo
    documento_id, documento_pdf_id, revision, motivos = personas[CAROLINA]   # no se borra: a revisión
    assert documento_pdf_id == id_vieja and revision is True
    assert "No se encontró en la nueva versión" in motivos[0]
    assert _fichas_en_lista(api, ana) == [nueva["id"]]


@requiere_postgres
def test_agregar_como_otra_parte_suma_las_personas_a_la_ficha_existente(bd, api, tmp_path, ocr_simulado):
    db = bd.SessionLocal()
    ana = cabecera(crear_usuario(db, "ana@example.com"))
    db.close()
    parte1 = _subir(api, ana, tmp_path, ocr_simulado, "3100001 parte 1.pdf", [CEDULA_AMARILLA, CEDULA_DIGITAL])
    parte2 = _subir(api, ana, tmp_path, ocr_simulado, "3100001 parte 2.pdf",
                    [CARTA, CERTIFICADO_OTRA_PERSONA, CEDULA_DIGITAL, CEDULA_CAROLINA],
                    acciones=[{"archivo": "3100001 parte 2.pdf", "accion": "agregar", "documento_id": parte1["id"]}])

    personas, total = _personas(bd)
    id_ficha, id_parte2 = uuid.UUID(parte1["id"]), uuid.UUID(parte2["id"])

    assert parte2["ficha_id"] == parte1["id"]
    assert total == 3                                                   # Lina venía en las dos partes
    assert all(p[0] == id_ficha for p in personas.values())             # una sola ficha
    assert personas[DIANA][1] is None                                 # solo estaba en la parte 1
    assert personas[CAROLINA][1] == id_parte2
    assert personas[LINA][1] == id_parte2                               # su lectura más reciente
    assert _fichas_en_lista(api, ana) == [parte1["id"]]


@requiere_postgres
def test_si_el_ocr_de_la_nueva_version_falla_la_ficha_anterior_no_cambia(bd, api, tmp_path, ocr_simulado, monkeypatch):
    from app.services.ocr_service import ocr_service

    db = bd.SessionLocal()
    ana = cabecera(crear_usuario(db, "ana@example.com"))
    db.close()
    vieja = _subir(api, ana, tmp_path, ocr_simulado, "3100001.pdf", [CEDULA_AMARILLA, CEDULA_DIGITAL])

    def _falla(*a, **k):
        raise RuntimeError("OCR caído")
    monkeypatch.setattr(ocr_service, "_ocr_imagen", _falla)
    _subir(api, ana, tmp_path, ocr_simulado, "3100001 v2.pdf", [CEDULA_AMARILLA],
           acciones=[{"archivo": "3100001 v2.pdf", "accion": "reemplazar", "documento_id": vieja["id"]}])

    personas, _ = _personas(bd)
    assert all(p[0] == uuid.UUID(vieja["id"]) for p in personas.values())
    assert vieja["id"] in _fichas_en_lista(api, ana)


@requiere_postgres
def test_no_se_puede_reemplazar_la_ficha_de_otro_usuario(bd, api, tmp_path, ocr_simulado):
    db = bd.SessionLocal()
    ana = cabecera(crear_usuario(db, "ana@example.com"))
    luis = cabecera(crear_usuario(db, "luis@example.com"))
    db.close()
    de_ana = _subir(api, ana, tmp_path, ocr_simulado, "3100001.pdf", [CEDULA_AMARILLA])
    pdf = pdf_de_prueba(tmp_path / "x.pdf", paginas=1)

    with open(pdf, "rb") as f:
        contenido = f.read()
    ajena = api.post("/api/documentos/upload", headers=luis, files=[("files", ("3100001.pdf", contenido, "application/pdf"))],
                     data={"acciones": json.dumps([{"archivo": "3100001.pdf", "accion": "reemplazar", "documento_id": de_ana["id"]}])})
    invalida = api.post("/api/documentos/upload", headers=ana, files=[("files", ("3100001.pdf", contenido, "application/pdf"))],
                        data={"acciones": json.dumps([{"archivo": "3100001.pdf", "accion": "borrar", "documento_id": de_ana["id"]}])})

    assert ajena.status_code == 404
    assert invalida.status_code == 400
    db = bd.SessionLocal()
    assert db.query(Documento).count() == 1                             # no se guardó nada
    db.close()
