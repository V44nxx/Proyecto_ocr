"""Errores sin detalles internos: el usuario ve una referencia y el detalle queda solo en el log."""
import uuid


def nueva_referencia() -> str:
    return f"ERR-{uuid.uuid4().hex[:8].upper()}"


def mensaje_error_interno(referencia: str) -> str:
    return (f"Ocurrió un error interno. Si se repite, informa al administrador la referencia {referencia}.")
