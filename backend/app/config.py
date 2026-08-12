"""
Configuración global del sistema OCR
"""
from pydantic_settings import BaseSettings
from pydantic import AnyUrl
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # ─────────────────────────────────────
    # Aplicación
    # ─────────────────────────────────────
    APP_NAME: str = "Sistema OCR - Documentos Colombianos"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # ─────────────────────────────────────
    # Base de Datos
    # ─────────────────────────────────────
    DATABASE_URL: str = "postgresql://ocr_user:ocr_password_2024@localhost:5432/ocr_documentos"

    # ─────────────────────────────────────
    # Seguridad JWT
    # ─────────────────────────────────────
    SECRET_KEY: str = "supersecretkey_change_in_production_2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas

    # ─────────────────────────────────────
    # Archivos
    # ─────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    EXPORT_DIR: str = "./exports"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_PDF_EXTENSIONS: list = [".pdf"]
    ALLOWED_EXCEL_EXTENSIONS: list = [".xlsx", ".xls"]

    # ─────────────────────────────────────
    # OCR
    # ─────────────────────────────────────
    OCR_LANG: str = "es"
    OCR_USE_ANGLE_CLS: bool = True
    OCR_DET_DB_SCORE_MODE: str = "slow"
    OCR_CONFIDENCE_THRESHOLD: float = 0.70   # Umbral para revisión manual
    IMAGE_DPI: int = 300                      # DPI para conversión PDF→imagen
    IMAGE_MIN_WIDTH: int = 1000              # Ancho mínimo para OCR óptimo

    # ─────────────────────────────────────
    # CORS
    # ─────────────────────────────────────
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def upload_path(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def export_path(self) -> Path:
        path = Path(self.EXPORT_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
