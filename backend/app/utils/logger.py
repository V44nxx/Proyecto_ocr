"""
Sistema de logging configurado con Loguru
"""
import logging
import re
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from app.config import settings


def setup_logger():
    """Configurar el logger del sistema"""
    # Eliminar logger por defecto
    logger.remove()

    # diagnose=False en todos: las trazas de error muestran archivo y línea, pero no el valor de las
    # variables (tokens de sesión, contraseñas o cédulas que estuvieran en memoria al fallar)

    # Logger en consola con colores. El nivel DEBUG incluye textos leídos por el OCR: solo con DEBUG=true.
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG" if settings.DEBUG else "INFO",
        diagnose=False,
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
        diagnose=False,
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
        diagnose=False,
    )

    logger.info("Sistema de logging inicializado")
    return logger


def enmascarar_documento(numero: Optional[str]) -> str:
    """Número de documento para los logs: solo los últimos 4 dígitos (******0401)."""
    texto = str(numero or "")
    if len(texto) <= 4:
        return "*" * len(texto)
    return "*" * (len(texto) - 4) + texto[-4:]


def enmascarar_nombre(nombre: Optional[str]) -> str:
    """Nombre de una persona para los logs: solo las iniciales (A. M. M. R.)."""
    return " ".join(f"{palabra[0].upper()}." for palabra in str(nombre or "").split())


# Un tramo de la dirección hecho solo de dígitos es una cédula (/buscar/cedula/1000000401); los ids son UUID
_CEDULA_EN_RUTA = re.compile(r"(?<=/)\d{6,}(?=[/?#]|$)")


def enmascarar_ruta(ruta: Optional[str]) -> str:
    """Dirección de una petición para los logs, con las cédulas enmascaradas."""
    return _CEDULA_EN_RUTA.sub(lambda m: enmascarar_documento(m.group()), str(ruta or ""))


class FiltroRutasEnmascaradas(logging.Filter):
    """Enmascara la cédula de la dirección en el registro de acceso de uvicorn (cliente, método, ruta, ...)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            record.args = record.args[:2] + (enmascarar_ruta(record.args[2]),) + record.args[3:]
        return True


# Logger global del sistema
app_logger = setup_logger()
