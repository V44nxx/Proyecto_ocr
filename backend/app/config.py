"""
Configuración global del sistema OCR
v2: agrega soporte para Google Cloud Document AI
"""
from typing import Optional
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
    # Google Cloud Document AI
    # ─────────────────────────────────────
    # ID del proyecto en Google Cloud
    GOOGLE_CLOUD_PROJECT: str = "ocr-sena"
    # Región del procesador (us, eu, etc.)
    GOOGLE_DOCUMENT_AI_LOCATION: str = "us"
    # ID del procesador — OBLIGATORIO, configurar en .env
    # Ejemplo: "abc123def456789a"
    GOOGLE_DOCUMENT_AI_PROCESSOR_ID: str = ""
    # Ruta al JSON de credenciales (Service Account)
    # En Docker: /app/credentials/google-document-ai.json
    # En local:  ./credentials/google-document-ai.json
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    # Contenido raw o Base64 del JSON de credenciales (para producción/Dokploy sin montar archivos)
    GOOGLE_CREDENTIALS_JSON: Optional[str] = None
    GOOGLE_CREDENTIALS_BASE64: Optional[str] = None
    # Switch para habilitar/deshabilitar Google Document AI
    GOOGLE_DOCUMENT_AI_ENABLED: bool = True

    # ─────────────────────────────────────
    # RapidOCR (ONNX Runtime Local)
    # ─────────────────────────────────────
    RAPID_OCR_ENABLED: bool = True

    # ─────────────────────────────────────
    # CORS
    # ─────────────────────────────────────
    CORS_ORIGINS: list = ["*"]

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
