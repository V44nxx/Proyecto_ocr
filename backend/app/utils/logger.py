"""
Sistema de logging configurado con Loguru
"""
import sys
from pathlib import Path
from loguru import logger


def setup_logger():
    """Configurar el logger del sistema"""
    # Eliminar logger por defecto
    logger.remove()

    # Logger en consola con colores
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG",
    )

    # Logger en archivo rotativo
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "ocr_sistema_{time:YYYY-MM-DD}.log",
        rotation="00:00",       # Rotar a medianoche
        retention="30 days",    # Mantener 30 días
        compression="zip",      # Comprimir logs viejos
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO",
        encoding="utf-8",
    )

    # Logger de errores separado
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="90 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        encoding="utf-8",
    )

    logger.info("Sistema de logging inicializado")
    return logger


# Logger global del sistema
app_logger = setup_logger()
