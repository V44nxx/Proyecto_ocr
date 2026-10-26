import pytest

from app.utils.limitador import usar_base_de_datos, vaciar_todos
from tests.utilidades_pg import TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def _limites_vacios():
    """Cada prueba empieza sin intentos previos. Sin PostgreSQL, los límites se llevan en memoria."""
    usar_base_de_datos(False)
    vaciar_todos()
    yield
    usar_base_de_datos(False)
    vaciar_todos()


@pytest.fixture(autouse=True)
def auditoria_registrada(request, monkeypatch):
    """
    Sin PostgreSQL, los registros de auditoría se guardan en esta lista en vez de la base.
    Con el fixture `bd`, se escriben de verdad en la base de pruebas.
    """
    registros = []
    if "bd" not in request.fixturenames:
        monkeypatch.setattr("app.services.auditoria._guardar", registros.append)
    return registros


@pytest.fixture
def bd(monkeypatch, tmp_path):
    """Base de pruebas real (TEST_DATABASE_URL) con el esquema recreado desde cero."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    import app.database as database
    from app.config import settings

    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        # Cerrar sesiones que un test fallido haya dejado abiertas, para que el DROP no se bloquee
        conn.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid()"
        ))
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(autocommit=False, autoflush=False, bind=engine))
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setattr(settings, "ADMIN_EMAIL", None)
    database.create_tables()
    usar_base_de_datos(True)             # como en producción: los intentos se cuentan en la base
    yield database
    usar_base_de_datos(False)
    engine.dispose()


@pytest.fixture
def api(bd):
    """Cliente HTTP de la app contra la base de pruebas real; los errores 500 llegan como respuesta."""
    from fastapi.testclient import TestClient
    from app.main import app
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
