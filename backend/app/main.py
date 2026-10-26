"""
Sistema OCR - Plataforma de Extracción de Documentos Colombianos
FastAPI Application Entry Point
"""
import os
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_DISABLE_PIR"] = "1"

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.exc import DataError
import logging
import time

from app.config import Settings, settings
from app.database import check_db_connection, create_tables
from app.utils.logger import FiltroRutasEnmascaradas, app_logger as logger, enmascarar_ruta
from app.routers import auth, documentos, personas, exportacion, comparacion, seguimiento
from app.routers.auth import get_admin_actual
from app.utils.errores import mensaje_error_interno, nueva_referencia
from app.utils.limite_peticiones import LimitePeticionesMiddleware
from app.utils.seguridad_http import CabecerasSeguridadMiddleware, cabeceras_cors, cabeceras_seguridad


def rutas_documentacion(configuracion: Settings) -> dict:
    """La documentación interactiva describe toda la API: solo se publica fuera de producción."""
    if configuracion.es_produccion:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


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
    from app import config as config_mod
    if config_mod.secret_key_publica:
        logger.error(
            "SECRET_KEY es una clave de ejemplo publicada en el repositorio: con ella cualquiera podría firmar "
            "sesiones. Se generó una temporal (las sesiones se cierran en cada reinicio y la verificación en dos "
            "pasos de los administradores deja de servir); define una propia."
        )
    elif config_mod.secret_key_temporal:
        logger.warning(
            "SECRET_KEY no está definida: se generó una temporal, las sesiones se cerrarán en cada reinicio y la "
            "verificación en dos pasos de los administradores dejará de servir. Defínela en las variables de entorno."
        )
    elif len(settings.SECRET_KEY.encode("utf-8")) < 32:
        logger.warning("SECRET_KEY tiene menos de 32 bytes: usa una más larga (por ejemplo, la de secrets.token_urlsafe(64)).")

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
    if app.docs_url:
        logger.info(f"Documentación API: http://localhost:8000{app.docs_url}")

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
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    **rutas_documentacion(settings),
)

# ──────────────────────────────────────────
# Middlewares (el último que se agrega queda por fuera)
# ──────────────────────────────────────────
# Revisa token y tamaño antes de leer el cuerpo. Va antes que CORS para quedar por dentro:
# así sus respuestas 401/413 también llevan las cabeceras CORS.
app.add_middleware(LimitePeticionesMiddleware)

# Solo el frontend configurado, con credenciales: el navegador envía la cookie de sesión.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)

# Por fuera de CORS para que también las respuestas de CORS y del límite de peticiones las lleven
app.add_middleware(CabecerasSeguridadMiddleware)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# El registro de acceso de uvicorn también escribe la dirección (con la cédula en /buscar/cedula/...)
logging.getLogger("uvicorn.access").addFilter(FiltroRutasEnmascaradas())


# Middleware de logging de requests
@app.middleware("http")
async def log_requests(request, call_next):
    inicio = time.time()
    response = await call_next(request)
    duracion = time.time() - inicio

    if not request.url.path.startswith("/docs") and not request.url.path.startswith("/openapi"):
        logger.info(
            f"{request.method} {enmascarar_ruta(request.url.path)} "
            f"-> {response.status_code} "
            f"({duracion * 1000:.1f}ms)"
        )
    return response


@app.exception_handler(DataError)
async def datos_invalidos_handler(request: Request, exc: DataError):
    """Un id u otro dato con formato inválido que llega hasta la base: es un error del cliente, no del servidor."""
    logger.warning(f"Dato con formato inválido en {request.method} {enmascarar_ruta(request.url.path)}: {type(exc.orig).__name__}")
    return JSONResponse(status_code=400, content={"detail": "Uno de los datos enviados no tiene el formato esperado."})


@app.exception_handler(ValueError)
async def caracter_nulo_handler(request: Request, exc: ValueError):
    """
    PostgreSQL no acepta el carácter nulo (0x00) en un texto y el controlador lo rechaza con un ValueError
    antes de consultar: llegue en la dirección o en el cuerpo, es un dato inválido del cliente.
    Cualquier otro ValueError sigue al manejador de errores internos.
    """
    if "NUL (0x00)" not in str(exc):
        raise exc
    logger.warning(f"Carácter nulo en un dato enviado a {request.method} {enmascarar_ruta(request.url.path)}")
    return JSONResponse(status_code=400, content={"detail": "Uno de los datos enviados contiene caracteres no válidos."})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Errores no controlados: el detalle queda en el log con una referencia y el usuario solo ve la referencia.
    Esta respuesta no pasa por los middlewares, así que lleva a mano las cabeceras de CORS y de seguridad.
    """
    referencia = nueva_referencia()
    logger.opt(exception=exc).error(f"{referencia} Excepción no controlada en {request.method} {enmascarar_ruta(request.url.path)}")
    return JSONResponse(
        status_code=500,
        content={"detail": mensaje_error_interno(referencia), "referencia": referencia},
        headers={**cabeceras_seguridad(request.url.path), **cabeceras_cors(request.headers.get("origin"))},
    )


# ──────────────────────────────────────────
# Routers
# ──────────────────────────────────────────
app.include_router(auth.router)
app.include_router(documentos.router)
app.include_router(personas.router)
app.include_router(exportacion.router)
app.include_router(comparacion.router)
app.include_router(seguimiento.router)


# ──────────────────────────────────────────
# Endpoints base
# ──────────────────────────────────────────
@app.get("/", tags=["Sistema"])
def root():
    respuesta = {
        "sistema": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operativo",
    }
    if app.docs_url:
        respuesta["docs"] = app.docs_url
    return respuesta


@app.get("/health", tags=["Sistema"])
def health_check():
    """Verificación de salud del sistema y diagnóstico de motores OCR"""
    db_ok = check_db_connection()
    from app.services.google_document_ai_service import google_document_ai_service
    from app.services.rapid_ocr_service import rapid_ocr_service
    import os

    docai_info = {
        "disponible": google_document_ai_service.disponible,
        "processor_id_configurado": bool(settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID),
        "creds_path_existe": bool(settings.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS)),
        "creds_env_configurado": bool(settings.GOOGLE_CREDENTIALS_JSON or settings.GOOGLE_CREDENTIALS_BASE64),
    }

    return {
        "status": "ok" if db_ok else "degradado",
        "database": "conectada" if db_ok else "sin conexión",
        "version": settings.APP_VERSION,
        "motores": {
            "google_docai": docai_info,
            "rapid_ocr": rapid_ocr_service.disponible,
            "tesseract": True,
        },
        "cpu_count": os.cpu_count(),
    }


# GET se mantiene por compatibilidad, fuera del esquema para que cada operación tenga un id único
@app.post("/api/sistema/migrar-db", tags=["Sistema"], dependencies=[Depends(get_admin_actual)])
@app.get("/api/sistema/migrar-db", tags=["Sistema"], dependencies=[Depends(get_admin_actual)], include_in_schema=False)
def migrar_base_datos():
    """Ejecuta migraciones de esquema idempotentes en PostgreSQL (solo admin)"""
    try:
        create_tables()
        return {"status": "ok", "message": "Migración de esquema ejecutada exitosamente."}
    except Exception as e:
        referencia = nueva_referencia()
        logger.opt(exception=e).error(f"{referencia} Error en /api/sistema/migrar-db")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": mensaje_error_interno(referencia), "referencia": referencia},
        )
