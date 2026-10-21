"""Errores sin detalles internos: el usuario ve una referencia y el detalle queda solo en el log."""
import re
import uuid
from typing import Optional

# Lo que hoy se guarda en mensaje_error de fichas y comparaciones: una frase y la referencia del log
_MENSAJE_GUARDADO_GENERICO = re.compile(r"No se pudo [^()]{1,80} \(referencia ERR-[0-9A-F]{8}\)\.")


def nueva_referencia() -> str:
    return f"ERR-{uuid.uuid4().hex[:8].upper()}"


def mensaje_error_interno(referencia: str) -> str:
    return (f"Ocurrió un error interno. Si se repite, informa al administrador la referencia {referencia}.")


def mensaje_error_visible(guardado: Optional[str], generico: str) -> Optional[str]:
    """
    Mensaje de error de una ficha o comparación para mostrar. Los registros de antes de la 2.7.0 guardaron el
    texto de la excepción (módulos, SQL): se cambia por uno genérico. Los de ahora ya son genéricos y se dejan.
    """
    if not guardado or _MENSAJE_GUARDADO_GENERICO.fullmatch(guardado):
        return guardado
    return generico
