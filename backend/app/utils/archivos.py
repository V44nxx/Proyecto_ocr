"""Validaciones de archivos subidos"""
from fastapi import HTTPException

from app.config import settings


def verificar_tamano_archivo(contenido: bytes, nombre: str) -> None:
    """Rechaza con 413 los archivos que superan MAX_FILE_SIZE_MB"""
    if len(contenido) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"El archivo '{nombre}' pesa {len(contenido) / (1024 * 1024):.1f} MB "
                f"y el máximo permitido es {settings.MAX_FILE_SIZE_MB} MB"
            ),
        )
