"""
Pasos compartidos de los escenarios BDD (Gherkin en español, pytest-bdd).

Los escenarios recorren la API completa con una base PostgreSQL real, así que necesitan TEST_DATABASE_URL;
sin ella se omiten como el resto de pruebas de integración.
"""
import pytest
from pytest_bdd import parsers, then


@pytest.fixture(autouse=True)
def _base_de_pruebas(bd):
    """Cada escenario arranca con la base recién creada (y la auditoría se escribe en ella)."""
    return bd


@pytest.fixture
def contexto():
    """Lo que un paso deja para los siguientes del mismo escenario."""
    return {}


@then("el sistema responde que no existe")
def responde_que_no_existe(contexto):
    assert contexto["respuesta"].status_code == 404, contexto["respuesta"].text


@then(parsers.parse('la acción "{accion}" queda en la auditoría'))
def accion_en_la_auditoria(bd, accion):
    from app.models.auditoria import RegistroAuditoria
    db = bd.SessionLocal()
    try:
        assert db.query(RegistroAuditoria).filter(RegistroAuditoria.accion == accion).count() >= 1
    finally:
        db.close()
