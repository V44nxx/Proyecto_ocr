"""
Sistema de logging configurado con Loguru
"""
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from app.config import settings


def setup_logger():
    """Configurar el logger del sistema"""
    # Eliminar logger por defecto
    logger.remove()

    # Logger en consola con colores. El nivel DEBUG incluye textos leídos por el OCR: solo con DEBUG=true.
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG" if settings.DEBUG else "INFO",
    )

    # Logger en archivo rotativo
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "ocr_sistema_{time:YYYY-MM-DD}.log",
        rotation="00:00",       # Rotar a medianoche
        retention="14 days",    # Mantener 14 días (pueden contener datos de las fichas)
        compression="zip",      # Comprimir logs viejos
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO",
        encoding="utf-8",
    )

    # Logger de errores separado
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        encoding="utf-8",
    )

    logger.info("Sistema de logging inicializado")
    return logger


def enmascarar_documento(numero: Optional[str]) -> str:
    """Número de documento para los logs: solo los últimos 4 dígitos (******0401)."""
    texto = str(numero or "")
    if len(texto) <= 4:
        return "*" * len(texto)
    return "*" * (len(texto) - 4) + texto[-4:]


# Logger global del sistema
app_logger = setup_logger()
