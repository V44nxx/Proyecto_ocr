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
