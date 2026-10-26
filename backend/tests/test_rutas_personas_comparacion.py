"""
Rutas de Personas y Comparación: lo que hace cada una para el usuario y que nunca toque datos de otra cuenta.
Necesitan TEST_DATABASE_URL (PostgreSQL real). Solo datos inventados.
"""
import io
import uuid
from datetime import date

import openpyxl
import pytest

from app.models.comparacion import Comparacion
from app.models.diferencia import Diferencia
from app.models.documento import Documento
from app.models.persona import Persona
from tests.utilidades_pg import cabecera, crear_ficha, crear_persona, crear_usuario, pdf_de_prueba, requiere_postgres

pytestmark = requiere_postgres


@pytest.fixture
def cuentas(bd):
    """ana con una ficha de dos personas y beto con una persona propia."""
    db = bd.SessionLocal()
    ana = crear_usuario(db, "ana@example.com")
    beto = crear_usuario(db, "beto@example.com")
    ficha = crear_ficha(db, ana)
    otra_ficha = crear_ficha(db, ana, nombre="3000002.pdf")
    p1 = crear_persona(db, ana, ficha, "1000000501", "ANGELA", "MORA", fecha_nacimiento=date(1990, 5, 1),
                       tipo_documento="CEDULA_CIUDADANIA")
    p2 = crear_persona(db, ana, ficha, "1000000502", "BRUNO", "DIAZ")
    p2.requiere_revision, p2.estado_registro = True, "REVIEW_REQUIRED"
    p3 = crear_persona(db, ana, otra_ficha, "1000000503", "CARLA", "RUIZ")
    pb = crear_persona(db, beto, crear_ficha(db, beto), "1000000599", "OTRA", "CUENTA")
    db.commit()
    datos = {
        "ana": cabecera(ana), "beto": cabecera(beto), "ana_id": ana.id, "ficha": str(ficha.id),
        "otra_ficha": str(otra_ficha.id), "p1": str(p1.id), "p2": str(p2.id), "p3": str(p3.id), "pb": str(pb.id),
    }
    db.close()
    return datos


def _persona(bd, persona_id):
    db = bd.SessionLocal()
    p = db.get(Persona, uuid.UUID(persona_id))
    if p is not None:
        db.expunge(p)
    db.close()
    return p


# ── Personas: listar y buscar ───────────────────────────────────────

def test_listar_filtra_por_ficha_por_revision_y_por_busqueda(api, cuentas):
    def cedulas(**params):
        r = api.get("/api/personas", params=params, headers=cuentas["ana"])
        assert r.status_code == 200
        return sorted(p["numero_identificacion"] for p in r.json())

    assert cedulas() == ["1000000501", "1000000502", "1000000503"]
    assert cedulas(documento_id=cuentas["ficha"]) == ["1000000501", "1000000502"]
    assert cedulas(requiere_revision="true") == ["1000000502"]
    assert cedulas(requiere_revision="false") == ["1000000501", "1000000503"]
    assert cedulas(buscar="0503") == ["1000000503"]
    assert cedulas(buscar="mora") == ["1000000501"]


def test_listar_y_buscar_no_muestran_personas_de_otra_cuenta(api, cuentas):
    lista = api.get("/api/personas", headers=cuentas["beto"]).json()
    assert [p["numero_identificacion"] for p in lista] == ["1000000599"]
    assert api.get("/api/personas/buscar/cedula/1000000501", headers=cuentas["beto"]).status_code == 404
    propia = api.get("/api/personas/buscar/cedula/1000000501", headers=cuentas["ana"])
    assert propia.status_code == 200 and propia.json()["nombres"] == "ANGELA"
    assert api.get(f"/api/personas/{cuentas['p1']}", headers=cuentas["beto"]).status_code == 404


# ── Personas: corregir a mano ───────────────────────────────────────

def test_corregir_datos_guarda_en_mayusculas_y_anota_lo_revisado(bd, api, cuentas, auditoria_registrada):
    r = api.put(f"/api/personas/{cuentas['p3']}", headers=cuentas["ana"],
                json={"nombres": "carla maria", "lugar_expedicion": "bogota", "sexo": "f"})
    p = _persona(bd, cuentas["p3"])
    assert r.status_code == 200
    assert (p.nombres, p.lugar_expedicion, p.sexo) == ("CARLA MARIA", "BOGOTA", "F")
    assert "nombres" in p.campos_revisados


def test_aprobar_a_mano_deja_la_persona_valida(bd, api, cuentas):
    r = api.put(f"/api/personas/{cuentas['p2']}", headers=cuentas["ana"], json={"requiere_revision": False})
    p = _persona(bd, cuentas["p2"])
    assert r.status_code == 200
    assert (p.requiere_revision, p.estado_registro) == (False, "VALID")
    assert p.detalles_campos.get("aprobado_manual") is True


def test_marcar_para_revision_y_validar_por_estado(bd, api, cuentas):
    api.put(f"/api/personas/{cuentas['p1']}", headers=cuentas["ana"], json={"requiere_revision": True})
    revisar = _persona(bd, cuentas["p1"])
    api.put(f"/api/personas/{cuentas['p1']}", headers=cuentas["ana"], json={"estado_registro": "VALID"})
    valida = _persona(bd, cuentas["p1"])
    assert (revisar.requiere_revision, revisar.estado_registro) == (True, "REVIEW_REQUIRED")
    assert (valida.requiere_revision, valida.estado_registro) == (False, "VALID")
    assert valida.detalles_campos.get("validado_manual") is True


def test_no_se_cambia_a_tarjeta_de_identidad_a_un_mayor_de_edad(bd, api, cuentas):
    r = api.put(f"/api/personas/{cuentas['p1']}", headers=cuentas["ana"], json={"tipo_documento": "TARJETA_IDENTIDAD"})
    assert r.status_code == 400 and "menores de 18" in r.json()["detail"]
    assert _persona(bd, cuentas["p1"]).tipo_documento == "CEDULA_CIUDADANIA"


def test_no_se_edita_ni_se_borra_una_persona_ajena(bd, api, cuentas):
    assert api.put(f"/api/personas/{cuentas['p1']}", headers=cuentas["beto"],
                   json={"nombres": "X"}).status_code == 404
    assert api.delete(f"/api/personas/{cuentas['p1']}", headers=cuentas["beto"]).status_code == 404
    assert _persona(bd, cuentas["p1"]).nombres == "ANGELA"


# ── Personas: borrar ────────────────────────────────────────────────

def test_borrar_una_persona_propia(bd, api, cuentas):
    assert api.delete(f"/api/personas/{cuentas['p1']}", headers=cuentas["ana"]).status_code == 204
    assert _persona(bd, cuentas["p1"]) is None


def test_borrado_en_lote_solo_borra_las_propias(bd, api, cuentas):
    vacio = api.post("/api/personas/batch-delete", headers=cuentas["ana"], json={"ids": []})
    r = api.post("/api/personas/batch-delete", headers=cuentas["ana"],
                 json={"ids": [cuentas["p1"], cuentas["p2"], cuentas["pb"]]})
    ajenas = api.post("/api/personas/batch-delete", headers=cuentas["beto"], json={"ids": [cuentas["p3"]]})
    assert vacio.json() == {"eliminadas": 0}
    assert r.json() == {"eliminadas": 2}
    assert ajenas.json() == {"eliminadas": 0}
    assert _persona(bd, cuentas["pb"]) is not None and _persona(bd, cuentas["p3"]) is not None


def test_vaciar_por_ficha_y_luego_todas(bd, api, cuentas):
    por_ficha = api.delete("/api/personas/vaciar/todas", headers=cuentas["ana"],
                           params={"documento_id": cuentas["ficha"]}).json()
    todas = api.delete("/api/personas/vaciar/todas", headers=cuentas["ana"], params={"documento_id": "todos"}).json()
    otra_vez = api.delete("/api/personas/vaciar/todas", headers=cuentas["ana"]).json()
    assert por_ficha["eliminadas"] == 2 and todas["eliminadas"] == 1 and otra_vez["eliminadas"] == 0
    assert _persona(bd, cuentas["pb"]) is not None


# ── Personas: subir el PDF de una persona ───────────────────────────

def test_subir_pdf_de_persona_solo_acepta_pdf_y_solo_propias(api, cuentas, tmp_path):
    pdf = pdf_de_prueba(tmp_path / "c.pdf").read_bytes()
    no_pdf = api.post(f"/api/personas/{cuentas['p1']}/subir-pdf", headers=cuentas["ana"],
                      files={"file": ("c.png", b"\x89PNG", "image/png")})
    ajena = api.post(f"/api/personas/{cuentas['p1']}/subir-pdf", headers=cuentas["beto"],
                     files={"file": ("c.pdf", pdf, "application/pdf")})
    assert no_pdf.status_code == 400 and ajena.status_code == 404


def test_subir_pdf_completa_la_persona_con_lo_que_lee_el_ocr(bd, api, cuentas, tmp_path, monkeypatch):
    from app.services.ocr_service import ocr_service

    def ocr_falso(ruta, documento_id, db_externa):
        # El OCR leyó mal un dígito y creó un registro aparte; la ruta debe unirlo a la persona y borrarlo
        db_externa.add(Persona(usuario_id=cuentas["ana_id"], documento_id=documento_id, numero_identificacion="1000000581",
                               nombres="ANGELA", apellidos="MORA", nombre_completo="ANGELA MORA", sexo="F",
                               fecha_expedicion=date(2008, 6, 1), lugar_expedicion="BOGOTA D.C.", pagina_frente=1,
                               pagina_reverso=2, confianza_extraccion=97, motor_ocr="google_document_ai",
                               detalles_campos={"sexo": {"valor": "F"}}))
        db_externa.flush()
    monkeypatch.setattr(ocr_service, "procesar_pdf", ocr_falso)

    pdf = pdf_de_prueba(tmp_path / "c.pdf").read_bytes()
    r = api.post(f"/api/personas/{cuentas['p1']}/subir-pdf", headers=cuentas["ana"],
                 files={"file": ("cedula angela.pdf", pdf, "application/pdf")})
    p = _persona(bd, cuentas["p1"])
    db = bd.SessionLocal()
    duplicadas = db.query(Persona).filter(Persona.numero_identificacion == "1000000581").count()
    doc = db.get(Documento, p.documento_pdf_id)
    db.close()

    assert r.status_code == 200
    assert (p.sexo, p.lugar_expedicion, p.fecha_expedicion) == ("F", "BOGOTA D.C.", date(2008, 6, 1))
    assert duplicadas == 0                                    # el registro temporal del OCR se borró
    assert str(p.documento_id) == cuentas["ficha"]           # sigue en su ficha; el PDF va aparte
    assert doc.estado == "completado" and doc.visible_en_subida is False
    assert p.detalles_campos["en_pdf"] is True


def test_si_el_ocr_falla_responde_con_referencia_y_marca_el_pdf_con_error(bd, api, cuentas, tmp_path, monkeypatch):
    from app.services.ocr_service import ocr_service

    def ocr_roto(*args, **kwargs):
        raise RuntimeError("falla de prueba del OCR")
    monkeypatch.setattr(ocr_service, "procesar_pdf", ocr_roto)

    pdf = pdf_de_prueba(tmp_path / "c.pdf").read_bytes()
    r = api.post(f"/api/personas/{cuentas['p1']}/subir-pdf", headers=cuentas["ana"],
                 files={"file": ("c.pdf", pdf, "application/pdf")})
    db = bd.SessionLocal()
    doc = db.query(Documento).filter(Documento.nombre_archivo.like("cedula_%")).one()
    estado, mensaje = doc.estado, doc.mensaje_error
    db.close()
    assert r.status_code == 500 and "ERR-" in r.json()["detail"] and "falla de prueba" not in r.text
    assert estado == "error" and "referencia ERR-" in mensaje


# ── Comparación ─────────────────────────────────────────────────────

def _planilla():
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(["IDENTIFICACION", "NOMBRE COMPLETO"])
    hoja.append(["1000000501", "ANGELA MORA"])
    hoja.append(["1000000777", "PERSONA NUEVA PLANILLA"])
    datos = io.BytesIO()
    libro.save(datos)
    return datos.getvalue()


@pytest.fixture
def comparacion(bd, cuentas):
    db = bd.SessionLocal()
    comp = Comparacion(usuario_id=cuentas["ana_id"], nombre_archivo="p.xlsx", nombre_original="p.xlsx",
                       estado="completado", total_registros_excel=3, total_faltantes_bd=1, total_diferentes=1)
    db.add(comp)
    db.commit()
    db.add_all([
        Diferencia(comparacion_id=comp.id, numero_identificacion="1000000501", campo="nombre_completo",
                   valor_bd="ANGELA MORA", valor_excel="ANGELA MARIA MORA", tipo_diferencia="diferente"),
        Diferencia(comparacion_id=comp.id, numero_identificacion="1000000777", campo="registro",
                   valor_bd=None, valor_excel="PERSONA NUEVA", tipo_diferencia="faltante_bd"),
    ])
    db.commit()
    comp_id = str(comp.id)
    db.close()
    return comp_id


def test_subir_planilla_valida_la_extension_y_queda_pendiente_sin_ejecutar(bd, api, cuentas):
    mala = api.post("/api/comparacion/upload", headers=cuentas["ana"], files={"file": ("p.csv", b"a,b", "text/csv")})
    r = api.post("/api/comparacion/upload", headers=cuentas["ana"], params={"ejecutar": "false"},
                 files={"file": ("planilla.xlsx", _planilla(), "application/octet-stream")})
    assert mala.status_code == 400
    assert r.status_code == 202 and r.json()["estado"] == "pendiente"


def test_subir_planilla_y_ejecutar_inicia_la_comparacion_en_segundo_plano(bd, api, cuentas, monkeypatch):
    from app.routers import comparacion as router_comparacion
    hilos = []

    class HiloFalso:
        def __init__(self, target, args, daemon):
            hilos.append((target, args))

        def start(self):
            pass
    monkeypatch.setattr(router_comparacion.threading, "Thread", HiloFalso)
    r = api.post("/api/comparacion/upload", headers=cuentas["ana"],
                 files={"file": ("planilla.xlsx", _planilla(), "application/octet-stream")})
    assert r.status_code == 202 and r.json()["estado"] == "procesando"
    assert hilos and hilos[0][1][0] == r.json()["id"]


def test_la_comparacion_en_segundo_plano_usa_la_planilla_guardada(bd, cuentas, comparacion, monkeypatch):
    from app.routers import comparacion as router_comparacion
    llamadas = []
    monkeypatch.setattr(router_comparacion.comparacion_service, "ejecutar_comparacion",
                        lambda cid, ruta, db: llamadas.append((cid, ruta)))
    router_comparacion._ejecutar_comparacion_background(comparacion, "ruta-vieja.xlsx")
    assert llamadas and llamadas[0][0] == comparacion


def test_una_falla_en_segundo_plano_no_tumba_el_servidor(bd, cuentas, comparacion, monkeypatch):
    from app.routers import comparacion as router_comparacion

    def falla(*args):
        raise RuntimeError("falla de prueba")
    monkeypatch.setattr(router_comparacion.comparacion_service, "ejecutar_comparacion", falla)
    router_comparacion._ejecutar_comparacion_background(comparacion, "x.xlsx")   # no debe lanzar


def test_listar_y_ver_comparaciones_solo_las_propias(api, cuentas, comparacion):
    assert [c["id"] for c in api.get("/api/comparacion", headers=cuentas["ana"]).json()] == [comparacion]
    assert api.get("/api/comparacion", headers=cuentas["beto"]).json() == []
    assert api.get(f"/api/comparacion/{comparacion}", headers=cuentas["ana"]).status_code == 200
    assert api.get(f"/api/comparacion/{comparacion}", headers=cuentas["beto"]).status_code == 404
    assert api.post(f"/api/comparacion/{comparacion}/ejecutar", headers=cuentas["beto"]).status_code == 404


def test_las_diferencias_se_filtran_por_tipo_y_son_solo_del_dueno(api, cuentas, comparacion):
    url = f"/api/comparacion/{comparacion}/diferencias"
    faltantes = api.get(url, params={"tipo": "faltante_bd"}, headers=cuentas["ana"]).json()
    assert [d["numero_identificacion"] for d in faltantes] == ["1000000777"]
    assert api.get(url, headers=cuentas["beto"]).status_code == 404


def test_no_se_vuelve_a_ejecutar_una_comparacion_en_proceso(bd, api, cuentas, comparacion):
    db = bd.SessionLocal()
    db.get(Comparacion, uuid.UUID(comparacion)).estado = "procesando"
    db.commit()
    db.close()
    assert api.post(f"/api/comparacion/{comparacion}/ejecutar", headers=cuentas["ana"]).status_code == 409


def test_el_reporte_solo_sale_de_una_comparacion_terminada(bd, api, cuentas, comparacion):
    listo = api.get(f"/api/comparacion/{comparacion}/reporte", headers=cuentas["ana"])
    db = bd.SessionLocal()
    db.get(Comparacion, uuid.UUID(comparacion)).estado = "pendiente"
    db.commit()
    db.close()
    pendiente = api.get(f"/api/comparacion/{comparacion}/reporte", headers=cuentas["ana"])
    ajeno = api.get(f"/api/comparacion/{comparacion}/reporte", headers=cuentas["beto"])
    assert listo.status_code == 200 and listo.content[:2] == b"PK"
    assert pendiente.status_code == 409 and ajeno.status_code == 404


def test_corregir_un_campo_desde_la_comparacion(bd, api, cuentas, comparacion):
    url = f"/api/comparacion/{comparacion}/corregir-campo"
    campo_malo = api.post(url, headers=cuentas["ana"],
                          json={"numero_identificacion": "1000000501", "campo": "rh", "nuevo_valor": "O+"})
    fecha_mala = api.post(url, headers=cuentas["ana"],
                          json={"numero_identificacion": "1000000501", "campo": "fecha_nacimiento", "nuevo_valor": "31/31/1990"})
    sin_persona = api.post(url, headers=cuentas["ana"],
                           json={"numero_identificacion": "1000000000", "campo": "nombres", "nuevo_valor": "X"})
    ajena = api.post(url, headers=cuentas["beto"],
                     json={"numero_identificacion": "1000000501", "campo": "nombres", "nuevo_valor": "X"})
    r = api.post(url, headers=cuentas["ana"], json={"numero_identificacion": "1000000501", "campo": "nombre_completo",
                                                    "nuevo_valor": "ANGELA MARIA MORA"})
    db = bd.SessionLocal()
    diferentes_tras_corregir = db.get(Comparacion, uuid.UUID(comparacion)).total_diferentes
    db.close()
    fecha = api.post(url, headers=cuentas["ana"], json={"numero_identificacion": "1000000501",
                                                        "campo": "fecha_expedicion", "nuevo_valor": "01/06/2008"})
    p = _persona(bd, cuentas["p1"])
    db = bd.SessionLocal()
    dif = db.query(Diferencia).filter(Diferencia.campo == "nombre_completo").one()
    comp = db.get(Comparacion, uuid.UUID(comparacion))
    db.close()

    assert campo_malo.status_code == 400 and fecha_mala.status_code == 400
    assert sin_persona.status_code == 404 and ajena.status_code == 404
    assert r.status_code == 200 and fecha.status_code == 200
    assert (p.nombre_completo, p.nombres, p.apellidos) == ("ANGELA MARIA MORA", "ANGELA MARIA MORA", None)
    assert p.fecha_expedicion == date(2008, 6, 1)
    # El contador se actualiza con la misma corrección (antes contaba la diferencia como si siguiera pendiente)
    assert dif.tipo_diferencia == "igual" and diferentes_tras_corregir == 0 and comp.total_diferentes == 0


def test_agregar_desde_la_comparacion_a_quien_falta_en_la_base(bd, api, cuentas, comparacion):
    url = f"/api/comparacion/{comparacion}/agregar-persona-bd"
    vacio = api.post(url, headers=cuentas["ana"], json={"numero_identificacion": "  "})
    ajena = api.post(url, headers=cuentas["beto"], json={"numero_identificacion": "1000000777"})
    r = api.post(url, headers=cuentas["ana"], json={"numero_identificacion": "1000000777",
                                                    "nombre_completo": "PERSONA NUEVA PLANILLA"})
    db = bd.SessionLocal()
    nueva = db.query(Persona).filter(Persona.numero_identificacion == "1000000777").one()
    comp = db.get(Comparacion, uuid.UUID(comparacion))
    faltantes = db.query(Diferencia).filter(Diferencia.tipo_diferencia == "faltante_bd").count()
    datos = (nueva.usuario_id, nueva.estado_registro, nueva.requiere_revision, nueva.detalles_campos["comparacion_id"])
    db.close()

    assert vacio.status_code == 400 and ajena.status_code == 404
    assert r.status_code == 200 and r.json()["nombre_completo"] == "PERSONA NUEVA PLANILLA"
    assert datos == (cuentas["ana_id"], "REVIEW_REQUIRED", True, comparacion)
    assert faltantes == 0 and comp.total_faltantes_bd == 0
