"""
Tests de seguridad de la API:
- /api/auth/register y /api/sistema/migrar-db exigen administrador
- límite de tamaño en las subidas, sin guardar nada si se rechaza un archivo
- administrador inicial por variables de entorno, sin tocar usuarios existentes
- personas de un documento reconstruidas desde el snapshot del historial
"""
import hashlib
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.documento import Documento
from app.models.usuario import Usuario
from app.routers.auth import get_usuario_actual, verificar_password

NUEVO_USUARIO = {"email": "nuevo@example.com", "password": "ClaveSegura123", "nombre": "Nuevo", "rol": "admin"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _usuario(rol):
    return SimpleNamespace(id=uuid.uuid4(), rol=rol, activo=True, email=f"{rol}@example.com")


@pytest.fixture
def client():
    # Las subidas exigen un token firmado antes de leer el cuerpo; la sesión la simulan las pruebas
    from app.routers.auth import crear_token_acceso
    token = crear_token_acceso({"sub": str(uuid.uuid4()), "email": "prueba@example.com", "ver": 0})
    yield TestClient(app, headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()


@pytest.fixture
def db_mock():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    return db


@pytest.fixture
def subidas(monkeypatch, tmp_path):
    """Carpeta de subidas temporal y límite de 1 MB"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 1)
    return tmp_path


GRANDE = b"0" * (1024 * 1024 + 1)


# ── /api/auth/register ──────────────────────────────────────────────

def test_register_sin_token_responde_401(client, db_mock):
    assert client.post("/api/auth/register", json=NUEVO_USUARIO).status_code == 401
    db_mock.add.assert_not_called()


def test_register_usuario_normal_responde_403(client, db_mock):
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario("usuario")
    assert client.post("/api/auth/register", json=NUEVO_USUARIO).status_code == 403
    db_mock.add.assert_not_called()


def test_register_admin_crea_usuario(client, db_mock):
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario("admin")
    db_mock.query.return_value.filter.return_value.first.return_value = None

    def _refresh(obj):
        obj.id = uuid.uuid4()
        obj.activo = True
        obj.fecha_creacion = datetime(2026, 10, 13, 12, 0)

    db_mock.refresh.side_effect = _refresh
    r = client.post("/api/auth/register", json=NUEVO_USUARIO)
    assert r.status_code == 201
    assert r.json()["email"] == "nuevo@example.com"
    creado = db_mock.add.call_args[0][0]
    assert creado.rol == "admin"
    assert verificar_password("ClaveSegura123", creado.password_hash)


# ── /api/sistema/migrar-db ──────────────────────────────────────────

@pytest.fixture
def create_tables_mock(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.main.create_tables", mock)
    return mock


def test_migrar_db_sin_token_responde_401(client, create_tables_mock):
    client.headers.pop("Authorization")
    assert client.get("/api/sistema/migrar-db").status_code == 401
    assert client.post("/api/sistema/migrar-db").status_code == 401
    create_tables_mock.assert_not_called()


def test_migrar_db_usuario_normal_responde_403(client, create_tables_mock):
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario("usuario")
    assert client.post("/api/sistema/migrar-db").status_code == 403
    create_tables_mock.assert_not_called()


def test_migrar_db_admin_ejecuta(client, create_tables_mock):
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario("admin")
    assert client.post("/api/sistema/migrar-db").status_code == 200
    create_tables_mock.assert_called_once()


# ── Límite de tamaño en subidas ─────────────────────────────────────

def test_upload_pdf_grande_responde_413_sin_guardar_nada(client, db_mock, subidas):
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario("usuario")
    r = client.post("/api/documentos/upload", files=[
        ("files", ("ok.pdf", b"%PDF-1.4 ok", "application/pdf")),
        ("files", ("grande.pdf", GRANDE, "application/pdf")),
        ("excel", ("planilla.xlsx", b"PK", XLSX)),
    ])
    assert r.status_code == 413
    assert "grande.pdf" in r.json()["detail"]
    db_mock.add.assert_not_called()
    assert list(subidas.iterdir()) == []


def test_upload_excel_grande_responde_413_sin_guardar_nada(client, db_mock, subidas):
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario("usuario")
    r = client.post("/api/documentos/upload", files=[
        ("files", ("ok.pdf", b"%PDF-1.4 ok", "application/pdf")),
        ("excel", ("planilla.xlsx", GRANDE, XLSX)),
    ])
    assert r.status_code == 413
    db_mock.add.assert_not_called()
    assert list(subidas.iterdir()) == []


def test_upload_extension_invalida_no_guarda_los_anteriores(client, db_mock, subidas):
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario("usuario")
    r = client.post("/api/documentos/upload", files=[
        ("files", ("ok.pdf", b"%PDF-1.4 ok", "application/pdf")),
        ("files", ("foto.png", b"PNG", "image/png")),
    ])
    assert r.status_code == 400
    db_mock.add.assert_not_called()
    assert list(subidas.iterdir()) == []


def test_upload_valido_guarda_pdfs_y_excel(client, db_mock, subidas, monkeypatch):
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario("usuario")
    procesar = MagicMock()
    monkeypatch.setattr("app.routers.documentos._procesar_batch_ocr_y_comparacion", procesar)
    r = client.post("/api/documentos/upload", files=[
        ("files", ("a.pdf", b"%PDF-1.4 a", "application/pdf")),
        ("files", ("b.pdf", b"%PDF-1.4 b", "application/pdf")),
        ("excel", ("planilla.xlsx", b"PK", XLSX)),
    ])
    assert r.status_code == 202
    assert r.json()["total"] == 2
    guardados = sorted(p.read_bytes() for p in subidas.iterdir())
    assert guardados == [b"%PDF-1.4 a", b"%PDF-1.4 b", b"PK"]
    assert db_mock.add.call_count == 3
    procesar.assert_called_once()


def test_upload_comparacion_excel_grande_responde_413(client, db_mock, subidas):
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario("usuario")
    r = client.post("/api/comparacion/upload", files=[("file", ("planilla.xlsx", GRANDE, XLSX))])
    assert r.status_code == 413
    db_mock.add.assert_not_called()
    assert list(subidas.iterdir()) == []


def test_subir_pdf_persona_grande_responde_413(client, db_mock, subidas):
    app.dependency_overrides[get_usuario_actual] = lambda: _usuario("usuario")
    r = client.post(f"/api/personas/{uuid.uuid4()}/subir-pdf", files=[("file", ("cedula.pdf", GRANDE, "application/pdf"))])
    assert r.status_code == 413
    db_mock.add.assert_not_called()
    assert list(subidas.iterdir()) == []


# ── Administrador inicial ───────────────────────────────────────────

def test_admin_inicial_sin_variables_no_crea(monkeypatch):
    from app.database import crear_admin_inicial
    monkeypatch.setattr(settings, "ADMIN_EMAIL", None)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", None)
    db = MagicMock()
    assert crear_admin_inicial(db) is False
    db.add.assert_not_called()


def test_admin_inicial_crea_si_no_existe(monkeypatch):
    from app.database import crear_admin_inicial
    monkeypatch.setattr(settings, "ADMIN_EMAIL", " Admin@Example.com ")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "OtraClave456")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert crear_admin_inicial(db) is True
    creado = db.add.call_args[0][0]
    assert isinstance(creado, Usuario)
    assert (creado.email, creado.rol, creado.activo) == ("admin@example.com", "admin", True)
    assert verificar_password("OtraClave456", creado.password_hash)
    db.commit.assert_called_once()


def test_admin_inicial_no_toca_usuario_existente(monkeypatch):
    from app.database import crear_admin_inicial
    monkeypatch.setattr(settings, "ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "OtraClave456")
    existente = SimpleNamespace(email="admin@example.com", password_hash="hash-original", rol="usuario", activo=False)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existente
    assert crear_admin_inicial(db) is False
    db.add.assert_not_called()
    db.commit.assert_not_called()
    assert (existente.password_hash, existente.rol, existente.activo) == ("hash-original", "usuario", False)


@pytest.mark.parametrize("correo", ["admin@ocr.local", "admin@localhost", "sin-arroba"])
def test_admin_inicial_rechaza_correo_que_no_podria_iniciar_sesion(monkeypatch, correo):
    from app.database import crear_admin_inicial
    monkeypatch.setattr(settings, "ADMIN_EMAIL", correo)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "OtraClave456")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert crear_admin_inicial(db) is False
    db.add.assert_not_called()


# Huellas SHA-256 de las contraseñas que estuvieron fijas en versiones viejas: se buscan sin escribirlas
HUELLAS_CONTRASENAS_FILTRADAS = {
    # Valores por defecto que se quitaron en la 2.6.2 (contraseña de la base, de pgAdmin y SECRET_KEY)
    "8c00f9a3bb117335c7a60b89dacee8f2027ed5ffac2600f4af3ccc8a085e393c",
    "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",
    "11a3607fd8969ec2d737e66f1f57ae80cd1305cfe60dfabf0f8b4f3bb76efbe0",
    "72e2ca83f0b90703fc2ed629ee1facbc975a8289d328c192d2579f660e1e63de",
    "3b612c75a7b5048a435fb6ec81e52ff92d6d795a8b5a9c17070f6a63c97a53b2",
}


def test_sin_contrasenas_fijas_en_el_codigo():
    raiz = Path(__file__).resolve().parents[2]
    ignorar = {"node_modules", ".next", ".venv", "__pycache__", ".git"}
    extensiones = {".py", ".sql", ".md", ".yml", ".yaml", ".ts", ".tsx", ".js", ".mjs", ".json", ".example", ""}
    revisados = 0
    for carpeta, subcarpetas, archivos in os.walk(raiz):
        subcarpetas[:] = [s for s in subcarpetas if s not in ignorar]
        for nombre in archivos:
            ruta = Path(carpeta) / nombre
            if nombre.startswith(".env") and nombre != ".env.example":
                continue  # archivos locales, fuera de git
            if ruta.suffix.lower() not in extensiones or ruta.stat().st_size > 2_000_000:
                continue
            contenido = ruta.read_text(encoding="utf-8", errors="ignore")
            palabras = set(re.findall(r"[A-Za-z0-9]{6,}", contenido)) | set(re.findall(r"[A-Za-z0-9_]{6,}", contenido))
            assert not {hashlib.sha256(p.encode()).hexdigest() for p in palabras} & HUELLAS_CONTRASENAS_FILTRADAS, ruta
            revisados += 1
    assert revisados > 50
    for ruta in (raiz / "backend" / "app" / "database.py", raiz / "database" / "init.sql"):
        assert "$2b$12$" not in ruta.read_text(encoding="utf-8"), ruta


# ── Personas desde el snapshot del historial ────────────────────────

def test_personas_de_documento_desde_snapshot(client, db_mock, monkeypatch):
    usuario = _usuario("usuario")
    app.dependency_overrides[get_usuario_actual] = lambda: usuario
    doc_id, persona_id = uuid.uuid4(), uuid.uuid4()
    documento = SimpleNamespace(
        id=doc_id,
        usuario_id=usuario.id,
        fecha_carga=datetime(2026, 10, 1, 12, 0),
        metadatos={"personas_extraidas_datos": [{
            "id": str(persona_id), "documento_id": str(doc_id), "nombre_documento": "lote.pdf",
            "numero_identificacion": "12345678", "nombre_completo": "PERSONA DE PRUEBA",
            "nombres": "PERSONA", "apellidos": "DE PRUEBA", "fecha_nacimiento": "1990-01-01", "edad": 36,
            "fecha_expedicion": "2008-01-01", "lugar_expedicion": "FLORENCIA", "sexo": "F",
            "tipo_documento": "CEDULA_CIUDADANIA", "estado_registro": "VALID", "confianza_extraccion": 95.0,
            "requiere_revision": False, "pagina_frente": 1, "pagina_reverso": 2, "pagina_numero": 1,
            "motor_ocr": "google_document_ai", "detalles_campos": {},
        }]},
    )

    def _query(modelo):
        q = MagicMock()
        if modelo is Documento:
            q.filter.return_value.first.return_value = documento
        else:
            q.filter.return_value.all.return_value = []
        return q

    db_mock.query.side_effect = _query
    monkeypatch.setattr("app.routers.personas._obtener_ids_en_excel", lambda db, uid: ({"12345678"}, True))
    r = client.get(f"/api/documentos/{doc_id}/personas")
    assert r.status_code == 200
    (persona,) = r.json()
    assert persona["id"] == str(persona_id)
    assert persona["en_excel"] is True and persona["en_pdf"] is True


def test_sin_secret_key_usa_una_clave_temporal(monkeypatch):
    from app import config

    monkeypatch.setenv("SECRET_KEY", "")
    monkeypatch.setattr(config, "secret_key_temporal", False)
    una = config.get_settings.__wrapped__()
    otra = config.get_settings.__wrapped__()
    assert config.secret_key_temporal is True
    assert len(una.SECRET_KEY) > 40 and una.SECRET_KEY != otra.SECRET_KEY
