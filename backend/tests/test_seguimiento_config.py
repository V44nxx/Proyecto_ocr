"""
Tests del Seguimiento de fichas:
- cada usuario guarda y lee solo su propia configuración
- solo se aceptan enlaces de Apps Script (panel) y Google Sheets (hoja)
"""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.seguimiento_config import SeguimientoConfig
from app.routers.auth import get_usuario_actual
from tests.utilidades_pg import cabecera, requiere_postgres

PANEL = "https://script.google.com/macros/s/AKfycbx123/exec"
PANEL_ORG = "https://script.google.com/a/macros/sena.edu.co/s/AKfycbx123/exec"
HOJA = "https://docs.google.com/spreadsheets/d/1AbC/edit"


@pytest.fixture
def usuario():
    u = SimpleNamespace(id=uuid.uuid4(), rol="usuario", activo=True, email="instructor@example.com")
    app.dependency_overrides[get_usuario_actual] = lambda: u
    return u


@pytest.fixture
def db_mock():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: db
    return db


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_sin_token_responde_401(client, db_mock):
    assert client.get("/api/seguimiento/config").status_code == 401


def test_sin_configuracion_devuelve_null(client, usuario, db_mock):
    r = client.get("/api/seguimiento/config")
    assert r.status_code == 200
    assert r.json() is None


@pytest.mark.parametrize("panel", [PANEL, PANEL_ORG])
def test_guardar_crea_configuracion_del_usuario(client, usuario, db_mock, panel):
    r = client.put("/api/seguimiento/config", json={
        "url_panel": f"  {panel} ", "correo_google": "yo@gmail.com", "url_hoja": HOJA,
    })
    assert r.status_code == 200, r.text
    guardada = db_mock.add.call_args[0][0]
    assert isinstance(guardada, SeguimientoConfig)
    assert guardada.usuario_id == usuario.id
    assert guardada.url_panel == panel
    assert guardada.correo_google == "yo@gmail.com"
    assert guardada.url_hoja == HOJA
    db_mock.commit.assert_called_once()


def test_guardar_actualiza_configuracion_existente(client, usuario, db_mock):
    existente = SeguimientoConfig(usuario_id=usuario.id, url_panel=PANEL, correo_google="viejo@gmail.com")
    db_mock.query.return_value.filter.return_value.first.return_value = existente
    r = client.put("/api/seguimiento/config", json={"url_panel": PANEL_ORG, "correo_google": "", "url_hoja": ""})
    assert r.status_code == 200, r.text
    db_mock.add.assert_not_called()
    assert existente.url_panel == PANEL_ORG
    assert existente.correo_google is None
    assert existente.url_hoja is None


@pytest.mark.parametrize("datos", [
    {"url_panel": "https://evil.example.com/macros/s/x/exec"},
    {"url_panel": "http://script.google.com/macros/s/x/exec"},
    {"url_panel": "javascript:alert(1)"},
    {"url_panel": "https://script.google.com.evil.com/macros/s/x/exec"},
    {"url_panel": PANEL, "url_hoja": "https://drive.google.com/file/d/1"},
    {"url_panel": PANEL, "correo_google": "no-es-correo"},
])
def test_rechaza_enlaces_o_correos_invalidos(client, usuario, db_mock, datos):
    assert client.put("/api/seguimiento/config", json=datos).status_code == 422
    db_mock.add.assert_not_called()
    db_mock.commit.assert_not_called()


def test_eliminar_sin_configuracion_responde_404(client, usuario, db_mock):
    assert client.delete("/api/seguimiento/config").status_code == 404


# ── Peticiones simultáneas (las encontró el escaneo de OWASP ZAP) ──────────────────
# Otra petición del mismo usuario cambia la fila justo después de que esta la leyó: no debe haber un 500.

def _con_interferencia(monkeypatch, bd, accion):
    """La primera lectura de la configuración devuelve lo que había y enseguida otra sesión aplica `accion`."""
    from app.routers import seguimiento
    original = seguimiento._config_de
    estado = {"hecho": False}

    def leer(db, usuario):
        resultado = original(db, usuario)
        if not estado["hecho"]:
            estado["hecho"] = True
            otra = bd.SessionLocal()
            accion(otra, usuario)
            otra.commit()
            otra.close()
        return resultado
    monkeypatch.setattr(seguimiento, "_config_de", leer)


def _borrar(sesion, usuario):
    sesion.query(SeguimientoConfig).filter(SeguimientoConfig.usuario_id == usuario.id).delete()


def _crear(sesion, usuario):
    sesion.add(SeguimientoConfig(usuario_id=usuario.id, url_panel=PANEL))


@pytest.fixture
def ana_pg(bd):
    from tests.utilidades_pg import crear_usuario
    db = bd.SessionLocal()
    yield crear_usuario(db, "ana@example.com")
    db.close()


def _filas(bd, usuario):
    db = bd.SessionLocal()
    filas = db.query(SeguimientoConfig).filter(SeguimientoConfig.usuario_id == usuario.id).all()
    datos = [f.url_panel for f in filas]
    db.close()
    return datos


@requiere_postgres
def test_guardar_mientras_otra_peticion_la_borra(bd, api, ana_pg, monkeypatch):
    db = bd.SessionLocal(); _crear(db, ana_pg); db.commit(); db.close()
    _con_interferencia(monkeypatch, bd, _borrar)
    r = api.put("/api/seguimiento/config", headers=cabecera(ana_pg), json={"url_panel": PANEL_ORG})
    assert r.status_code == 200, r.text
    assert _filas(bd, ana_pg) == [PANEL_ORG]


@requiere_postgres
def test_guardar_mientras_otra_peticion_la_crea(bd, api, ana_pg, monkeypatch):
    _con_interferencia(monkeypatch, bd, _crear)
    r = api.put("/api/seguimiento/config", headers=cabecera(ana_pg), json={"url_panel": PANEL_ORG})
    assert r.status_code == 200, r.text
    assert _filas(bd, ana_pg) == [PANEL_ORG]


@requiere_postgres
def test_eliminar_mientras_otra_peticion_la_borra(bd, api, ana_pg, monkeypatch):
    db = bd.SessionLocal(); _crear(db, ana_pg); db.commit(); db.close()
    _con_interferencia(monkeypatch, bd, _borrar)
    r = api.delete("/api/seguimiento/config", headers=cabecera(ana_pg))
    assert r.status_code == 200, r.text
    assert _filas(bd, ana_pg) == []
