import pytest

from app.utils.limitador import vaciar_todos


@pytest.fixture(autouse=True)
def _limites_vacios():
    """Los límites de intentos viven en memoria: cada prueba empieza sin intentos previos."""
    vaciar_todos()
    yield
    vaciar_todos()
