"""
Configuración de base de datos con SQLAlchemy
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import settings
import logging

# Motor de hashing: passlib (mismo que auth.py) con fallback a bcrypt directo
try:
    from passlib.context import CryptContext
    _pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _PASSLIB_OK = True
except ImportError:
    _pwd_ctx = None
    _PASSLIB_OK = False

try:
    import bcrypt as _bcrypt_raw
    _BCRYPT_OK = True
except ImportError:
    _bcrypt_raw = None
    _BCRYPT_OK = False

logger = logging.getLogger(__name__)

# Motor de base de datos
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"options": "-c client_encoding=utf8"}
)

# Sesión de base de datos
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency para obtener sesión de DB en endpoints FastAPI"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Error en sesión de DB: {e}")
        raise
    finally:
        db.close()


def _hash_password(password: str) -> str:
    """Hash bcrypt usando bcrypt directo con fallback a passlib"""
    pwd_bytes = password.encode("utf-8")[:72]
    if _BCRYPT_OK:
        return _bcrypt_raw.hashpw(pwd_bytes, _bcrypt_raw.gensalt(rounds=12)).decode("utf-8")
    if _PASSLIB_OK:
        return _pwd_ctx.hash(password)
    raise RuntimeError("No hay motor de hashing disponible")


def create_tables():
    """Crear todas las tablas del modelo e inicializar usuario admin si no existe"""
    from app.models import usuario, documento, persona, comparacion, diferencia
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas de base de datos creadas/verificadas")

    # ── Migraciones automáticas de esquema (idempotentes) ───────────
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            queries = [
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS grupo_documento_id VARCHAR(100);",
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS pagina_frente INTEGER;",
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS pagina_reverso INTEGER;",
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS pagina_numero INTEGER;",
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS tipo_documento VARCHAR(50) DEFAULT 'CEDULA_CIUDADANIA';",
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS estado_registro VARCHAR(30) DEFAULT 'VALID';",
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS motor_ocr VARCHAR(50) DEFAULT 'google_document_ai';",
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS detalles_campos JSONB;",
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS nombre_completo VARCHAR(400);",
                "CREATE INDEX IF NOT EXISTS ix_personas_nombre_completo ON personas (nombre_completo);",
                "UPDATE personas SET nombre_completo = TRIM(CONCAT(COALESCE(nombres, ''), ' ', COALESCE(apellidos, ''))) WHERE (nombre_completo IS NULL OR nombre_completo = '') AND (nombres IS NOT NULL OR apellidos IS NOT NULL);"
            ]
            for q in queries:
                try:
                    conn.execute(text(q))
                except Exception as q_err:
                    logger.warning(f"Aviso en migración de esquema '{q[:40]}...': {q_err}")
            conn.commit()
            logger.info("Migraciones automáticas de esquema completadas con éxito.")
    except Exception as mig_err:
        logger.error(f"Error ejecutando migraciones automáticas: {mig_err}")

    # ── Saneamiento de nombres y reevaluación de estado de revisión ──
    try:
        from app.models.persona import Persona
        from app.utils.name_cleaner import resolver_nombre_completo
        db_s = SessionLocal()
        try:
            personas = db_s.query(Persona).all()
            modificados = 0
            for p in personas:
                nom_limpio = resolver_nombre_completo(p.nombres, p.apellidos, p.nombre_completo)
                if nom_limpio and nom_limpio != p.nombre_completo:
                    p.nombre_completo = nom_limpio
                    modificados += 1

                # Reevaluar si es un registro completo y válido
                tiene_datos = bool(
                    p.numero_identificacion
                    and not str(p.numero_identificacion).startswith("SIN_ID")
                    and (p.nombre_completo and p.nombre_completo != "POR REVISAR")
                    and (p.fecha_expedicion or p.fecha_nacimiento)
                    and float(p.confianza_extraccion or 0) >= 70.0
                )
                nuevo_req = not tiene_datos
                nuevo_est = "VALID" if tiene_datos else "REVIEW_REQUIRED"
                if p.requiere_revision != nuevo_req or p.estado_registro != nuevo_est:
                    p.requiere_revision = nuevo_req
                    p.estado_registro = nuevo_est
                    modificados += 1

            if modificados > 0:
                db_s.commit()
                logger.info(f"Saneamiento y reevaluación completada: {modificados} cambios en personas.")
        finally:
            db_s.close()
    except Exception as san_err:
        logger.warning(f"Aviso saneando y reevaluando personas en BD: {san_err}")

    try:
        from app.models.usuario import Usuario
        db = SessionLocal()
        try:
            admin_user = db.query(Usuario).filter(Usuario.email == "admin@ocr.com").first()
            nuevo_hash = _hash_password("Admin123!")
            if not admin_user:
                nuevo_admin = Usuario(
                    email="admin@ocr.com",
                    nombre="Administrador Sistema",
                    password_hash=nuevo_hash,
                    rol="admin",
                    activo=True
                )
                db.add(nuevo_admin)
                db.commit()
                logger.info("Usuario administrador inicial creado: admin@ocr.com")
            else:
                admin_user.password_hash = nuevo_hash
                admin_user.activo = True
                db.commit()
                logger.info("Usuario admin actualizado: admin@ocr.com -> Admin123!")
        finally:
            db.close()
    except Exception as err:
        logger.warning(f"No se pudo verificar/crear usuario admin inicial: {err}")


def check_db_connection():
    """Verificar que la conexión a DB está disponible"""
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        logger.info("Conexión a PostgreSQL: OK")
        return True
    except Exception as e:
        msg = str(e)
        if isinstance(e, UnicodeDecodeError) or "codec can't decode" in msg:
            try:
                # Decodificar el mensaje crudo con la página de códigos de Windows
                raw_bytes = bytes(e.args[1]) if hasattr(e, 'args') and len(e.args) > 1 and isinstance(e.args[1], (bytes, bytearray)) else None
                if raw_bytes:
                    msg = raw_bytes.decode('cp1252', errors='replace')
            except Exception:
                msg = f"Error de autenticación/conexión a PostgreSQL (Verifica usuario 'postgres' y clave '123456' en tu servidor local)."
        logger.error(f"Error conectando a PostgreSQL: {msg}")
        return False
