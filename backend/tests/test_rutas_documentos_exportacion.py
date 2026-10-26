"""
Rutas de Documentos (estado, retirar y eliminar fichas) y de Exportación a Excel.
Necesitan TEST_DATABASE_URL (PostgreSQL real). Solo datos inventados.
"""
import io
import uuid

import openpyxl
import pytest

from app.config import settings
from app.models.documento import Documento
from app.models.persona import Persona
from tests.utilidades_pg import cabecera, crear_ficha, crear_persona, crear_usuario, requiere_postgres

pytestmark = requiere_postgres


@pytest.fixture
def cuentas(bd):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    beto = crear_usuario(db, "beto@example.com")
    ficha = crear_ficha(db, ana, estado="procesando", metadatos={"paso": "Leyendo página 2", "progreso": 40})
    crear_persona(db, ana, ficha, "1000000601", "ANGELA", "MORA")
    crear_persona(db, ana, ficha, "1000000602", "BRUNO", "DIAZ")
    crear_persona(db, beto, crear_ficha(db, beto), "1000000699", "OTRA", "CUENTA")
    datos = {"ana": cabecera(ana), "beto": cabecera(beto), "ficha": str(ficha.id)}
    db.close()
    return datos


def _ficha(bd, ficha_id):
    db = bd.SessionLocal()
    d = db.get(Documento, uuid.UUID(ficha_id))
    if d is not None:
        db.expunge(d)
    db.close()
    return d


def _textos_del_excel(contenido):
    hoja = openpyxl.load_workbook(io.BytesIO(contenido)).active
    return {str(c.value) for fila in hoja.iter_rows() for c in fila if c.value is not None}


# ── Estado de una ficha ─────────────────────────────────────────────

def test_estado_de_una_ficha_en_proceso_muestra_su_paso(api, cuentas):
    r = api.get(f"/api/documentos/{cuentas['ficha']}/estado", headers=cuentas["ana"])
    datos = r.json()
    assert r.status_code == 200
    assert (datos["estado"], datos["progreso"], datos["paso"], datos["personas_count"]) == \
        ("procesando", 40, "Leyendo página 2", 2)
    assert api.get(f"/api/documentos/{cuentas['ficha']}/estado", headers=cuentas["beto"]).status_code == 404


@pytest.mark.parametrize("estado, progreso, paso", [
    ("completado", 100, "Procesamiento completado"),
    ("procesando", 25, "Procesando documento con OCR..."),
    ("error", 100, "Error durante el procesamiento"),
    ("pendiente", 0, "Pendiente en cola"),
])
def test_estado_sin_detalle_usa_valores_por_defecto(bd, api, estado, progreso, paso):
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    ficha = crear_ficha(db, ana, estado=estado, mensaje_error="Traceback: detalle interno")
    ficha_id, cab = str(ficha.id), cabecera(ana)
    db.close()
    datos = api.get(f"/api/documentos/{ficha_id}/estado", headers=cab).json()
    assert (datos["progreso"], datos["paso"]) == (progreso, paso)
    assert "Traceback" not in str(datos["mensaje_error"])     # nunca se muestra el error interno


# ── Retirar y eliminar fichas ───────────────────────────────────────

def test_retirar_una_ficha_la_oculta_pero_conserva_sus_personas(bd, api, cuentas):
    r = api.delete(f"/api/documentos/{cuentas['ficha']}", headers=cuentas["ana"])
    ficha = _ficha(bd, cuentas["ficha"])
    personas = api.get("/api/personas", headers=cuentas["ana"]).json()
    assert r.status_code == 200 and r.json()["ok"] is True
    assert ficha.visible_en_subida is False and ficha.metadatos["oculto_en_subida"] is True
    assert len(personas) == 2


def test_eliminar_una_ficha_borra_sus_personas_y_sus_archivos(bd, api, cuentas, auditoria_registrada):
    subidas = settings.upload_path
    pdf = subidas / "ficha_prueba.pdf"
    pdf.write_bytes(b"%PDF-1.4 datos inventados")
    cache = subidas / "cache_previews"
    cache.mkdir(parents=True, exist_ok=True)
    vista = cache / f"{cuentas['ficha']}_p1.jpg"
    vista.write_bytes(b"jpg")
    db = bd.SessionLocal()
    db.get(Documento, uuid.UUID(cuentas["ficha"])).ruta_archivo = str(pdf)
    db.commit()
    db.close()

    ajeno = api.delete(f"/api/documentos/{cuentas['ficha']}", headers=cuentas["beto"], params={"permanente": "true"})
    r = api.delete(f"/api/documentos/{cuentas['ficha']}", headers=cuentas["ana"], params={"permanente": "true"})
    db = bd.SessionLocal()
    quedan = db.query(Persona).filter(Persona.numero_identificacion.in_(["1000000601", "1000000602"])).count()
    de_beto = db.query(Persona).filter(Persona.numero_identificacion == "1000000699").count()
    db.close()

    assert ajeno.status_code == 404
    assert r.status_code == 200 and _ficha(bd, cuentas["ficha"]) is None
    assert quedan == 0 and de_beto == 1
    assert not pdf.exists() and not vista.exists()


# ── Exportación a Excel ─────────────────────────────────────────────

def test_exportar_todas_las_personas_propias(api, cuentas):
    r = api.get("/api/exportacion/xlsx", headers=cuentas["ana"], params={"documento_id": cuentas["ficha"]})
    textos = _textos_del_excel(r.content)
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    assert {"1000000601", "1000000602"} <= textos and "1000000699" not in textos


def test_exportar_solo_la_seleccion_y_nunca_personas_ajenas(bd, api, cuentas):
    db = bd.SessionLocal()
    ids = {p.numero_identificacion: str(p.id) for p in db.query(Persona).all()}
    db.close()
    r = api.post("/api/exportacion/xlsx", headers=cuentas["ana"],
                 json={"persona_ids": [ids["1000000601"], ids["1000000699"]], "requiere_revision": False})
    textos = _textos_del_excel(r.content)
    assert r.status_code == 200
    assert "1000000601" in textos and "1000000602" not in textos and "1000000699" not in textos


def test_el_excel_exportado_no_queda_en_el_servidor(api, cuentas):
    api.get("/api/exportacion/xlsx", headers=cuentas["ana"], params={"solo_menores": "false"})
    assert not list(settings.export_path.glob("*.xlsx"))
