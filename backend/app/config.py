"""
Configuración global del sistema OCR
v2: agrega soporte para Google Cloud Document AI
"""
import hashlib
import secrets
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
    APP_VERSION: str = "2.10.1"
    ENVIRONMENT: str = "development"
    # Con DEBUG, SQLAlchemy escribe cada consulta (con sus datos) en el log: nunca en producción
    DEBUG: bool = False

    # ─────────────────────────────────────
    # Base de Datos
    # ─────────────────────────────────────
    DATABASE_URL: str = "postgresql://ocr_user@localhost:5432/ocr_documentos"  # se define en .env o en Dokploy

    # ─────────────────────────────────────
    # Seguridad JWT
    # ─────────────────────────────────────
    # Obligatoria en producción. Sin ella se usa una aleatoria por proceso (ver get_settings)
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas
    # Cookie de sesión Secure (solo HTTPS). Sin definir: Secure en producción y no en local (http)
    COOKIE_SECURE: Optional[bool] = None

    # ─────────────────────────────────────
    # Administrador inicial
    # ─────────────────────────────────────
    # Si ambos están definidos y el correo no existe, se crea como admin al arrancar.
    # Nunca modifica usuarios existentes ni sus contraseñas.
    ADMIN_EMAIL: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    ADMIN_NOMBRE: str = "Administrador Sistema"

    # ─────────────────────────────────────
    # Correo (recuperación de contraseña)
    # ─────────────────────────────────────
    # Con Gmail: SMTP_HOST=smtp.gmail.com, SMTP_USER=la cuenta y SMTP_PASSWORD=una "contraseña de aplicación".
    # Sin SMTP_HOST la recuperación por correo queda desactivada.
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587                     # 587 con STARTTLS; 465 con SSL directo
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_REMITENTE: Optional[str] = None     # por defecto, SMTP_USER
    SMTP_TLS: bool = True
    # Dirección pública del frontend, para el enlace del correo
    FRONTEND_URL: str = "http://localhost:3000"
    RECUPERACION_MINUTOS: int = 30

    # ─────────────────────────────────────
    # Archivos
    # ─────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    EXPORT_DIR: str = "./exports"
    MAX_FILE_SIZE_MB: int = 50
    MAX_SUBIDA_TOTAL_MB: int = 500           # tope de una petición de subida (varios PDF + planilla)
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
    GOOGLE_DOCUMENT_AI_PROCESSOR_ID: str = "c0b0e9a8458af30c"
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
    # Orígenes del frontend que pueden llamar a la API desde el navegador: la lista exacta más
    # la expresión regular (por defecto, cualquier subdominio https de v44nxx.online).
    CORS_ORIGINS: list = ["http://localhost:3000", "http://127.0.0.1:3000"]
    CORS_ORIGIN_REGEX: Optional[str] = r"https://([a-z0-9-]+\.)*v44nxx\.online"

    # ─────────────────────────────────────
    # Auditoría
    # ─────────────────────────────────────
    AUDITORIA_RETENCION_DIAS: int = 365

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def es_produccion(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

    @property
    def cookie_segura(self) -> bool:
        return self.es_produccion if self.COOKIE_SECURE is None else self.COOKIE_SECURE

    @property
    def nombre_cookie_sesion(self) -> str:
        # El prefijo __Host- hace que el navegador la acepte solo por HTTPS, sin dominio y con Path=/
        return "__Host-kondid_sesion" if self.cookie_segura else "kondid_sesion"

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

    @property
    def max_subida_total_bytes(self) -> int:
        return self.MAX_SUBIDA_TOTAL_MB * 1024 * 1024


# Huellas SHA-256 de las SECRET_KEY de ejemplo que se publicaron en el repositorio (.env.example inicial,
# valor por defecto viejo y documentación). Con una de ellas cualquiera podría firmar sesiones válidas.
HUELLAS_CLAVES_PUBLICAS = frozenset({
    "23a4bf019ab3d632f7aaee05d3ac3f04249cbc60d340dd7e06cfa30876cd78ca",
    "11a3607fd8969ec2d737e66f1f57ae80cd1305cfe60dfabf0f8b4f3bb76efbe0",
    "f6c126ca64241bc54d67ad762256c207e23c286dbc8a4acfff082d91d912605b",
})

# True si se generó una SECRET_KEY temporal (las sesiones se cierran en cada reinicio);
# secret_key_publica dice si fue porque la configurada era una clave de ejemplo publicada
secret_key_temporal = False
secret_key_publica = False


def asegurar_secret_key(configuracion: Settings) -> str:
    """Reemplaza por una temporal la SECRET_KEY vacía ("faltante") o publicada ("publica"); "" si sirve."""
    clave = configuracion.SECRET_KEY.strip()
    if not clave:
        motivo = "faltante"
    elif hashlib.sha256(clave.encode("utf-8")).hexdigest() in HUELLAS_CLAVES_PUBLICAS:
        motivo = "publica"
    else:
        return ""
    configuracion.SECRET_KEY = secrets.token_urlsafe(64)
    return motivo


@lru_cache()
def get_settings() -> Settings:
    global secret_key_temporal, secret_key_publica
    configuracion = Settings()
    motivo = asegurar_secret_key(configuracion)
    secret_key_temporal = bool(motivo)
    secret_key_publica = motivo == "publica"
    return configuracion


settings = get_settings()
