"""
Sistema OCR - Plataforma de Extracción de Documentos Colombianos
FastAPI Application Entry Point
"""
import os
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_DISABLE_PIR"] = "1"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import time
import logging

from app.config import settings
from app.database import check_db_connection, create_tables
from app.utils.logger import app_logger as logger
from app.routers import auth, documentos, personas, exportacion, comparacion


# ──────────────────────────────────────────
# Lifecycle: startup y shutdown
# ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Acciones al inicio y cierre de la aplicación"""
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"  Entorno: {settings.ENVIRONMENT}")
    logger.info("=" * 60)

    # Verificar conexión a base de datos
    if not check_db_connection():
        logger.error("No se pudo conectar a PostgreSQL. Verificar configuración.")
    else:
        # Crear tablas y garantizar usuario admin inicial si no existe
        create_tables()

    # Crear directorios necesarios
    settings.upload_path
    settings.export_path

    logger.info("Backend OCR iniciado correctamente")
    logger.info(f"Documentación API: http://localhost:8000/docs")

    yield  # La aplicación corre aquí

    logger.info("Sistema OCR detenido")


# ──────────────────────────────────────────
# Aplicación FastAPI
# ──────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description="""
## Sistema OCR para Documentos de Identificación Colombianos

Plataforma profesional para extracción automática de información personal
desde documentos PDF mediante OCR con PaddleOCR.

### Características principales:
- 📄 **Procesamiento OCR**: PaddleOCR + OpenCV con preprocesamiento avanzado
- 🗄️ **Base de datos**: PostgreSQL con modelo relacional completo
- 📊 **Exportación Excel**: XLSX formateado con Pandas + OpenPyXL  
- 🔍 **Comparación**: Análisis de diferencias entre BD y archivos Excel externos
- 🔐 **Autenticación**: JWT con bcrypt
- 📝 **Logs**: Sistema completo con Loguru

### Flujo de procesamiento:
1. Subir PDF → 2. OCR automático → 3. Extracción de campos → 4. Validación → 5. Almacenamiento

### Credenciales por defecto:
- **Email**: admin@ocr.com
- **Password**: Admin123!
    """,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ──────────────────────────────────────────
# Middlewares
# ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# Middleware de logging de requests
@app.middleware("http")
async def log_requests(request, call_next):
    inicio = time.time()
    response = await call_next(request)
    duracion = time.time() - inicio

    if not request.url.path.startswith("/docs") and not request.url.path.startswith("/openapi"):
        logger.info(
            f"{request.method} {request.url.path} "
            f"-> {response.status_code} "
            f"({duracion * 1000:.1f}ms)"
        )
    return response


# ──────────────────────────────────────────
# Routers
# ──────────────────────────────────────────
app.include_router(auth.router)
app.include_router(documentos.router)
app.include_router(personas.router)
app.include_router(exportacion.router)
app.include_router(comparacion.router)


# ──────────────────────────────────────────
# Endpoints base
# ──────────────────────────────────────────
@app.get("/", tags=["Sistema"])
def root():
    return {
        "sistema": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "entorno": settings.ENVIRONMENT,
        "docs": "/docs",
        "status": "operativo",
    }


@app.get("/health", tags=["Sistema"])
def health_check():
    """Verificación de salud del sistema"""
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degradado",
        "database": "conectada" if db_ok else "sin conexión",
        "version": settings.APP_VERSION,
    }
