"""
Configuración de base de datos con SQLAlchemy
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import settings
import logging

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


def create_tables():
    """Crear todas las tablas del modelo e inicializar usuario admin si no existe"""
    from app.models import usuario, documento, persona, comparacion, diferencia
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas de base de datos creadas/verificadas")

    try:
        from app.models.usuario import Usuario
        from app.routers.auth import crear_hash_password
        db = SessionLocal()
        try:
            admin_user = db.query(Usuario).filter(Usuario.email == "admin@ocr.com").first()
            if not admin_user:
                nuevo_admin = Usuario(
                    email="admin@ocr.com",
                    nombre="Administrador Sistema",
                    password_hash=crear_hash_password("Admin123!"),
                    rol="admin",
                    activo=True
                )
                db.add(nuevo_admin)
                db.commit()
                logger.info("Usuario administrador inicial creado: admin@ocr.com")
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
