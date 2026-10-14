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
                "UPDATE personas SET nombre_completo = TRIM(CONCAT(COALESCE(nombres, ''), ' ', COALESCE(apellidos, ''))) WHERE (nombre_completo IS NULL OR nombre_completo = '') AND (nombres IS NOT NULL OR apellidos IS NOT NULL);",
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS usuario_id UUID REFERENCES usuarios(id) ON DELETE CASCADE;",
                "CREATE INDEX IF NOT EXISTS ix_personas_usuario_id ON personas (usuario_id);",
                "UPDATE personas p SET usuario_id = d.usuario_id FROM documentos d WHERE p.documento_id = d.id AND p.usuario_id IS NULL;",
                "ALTER TABLE personas DROP CONSTRAINT IF EXISTS personas_numero_identificacion_key;",
                # La cédula es única por usuario, pero puede haber varias personas sin cédula ("") en la misma cuenta
                "DROP INDEX IF EXISTS uq_personas_usuario_identificacion;",
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_personas_usuario_identificacion_v2 ON personas (usuario_id, numero_identificacion) WHERE usuario_id IS NOT NULL AND numero_identificacion <> '';",
                "ALTER TABLE documentos ADD COLUMN IF NOT EXISTS visible_en_subida BOOLEAN DEFAULT TRUE;",
                "UPDATE documentos SET visible_en_subida = TRUE WHERE visible_en_subida IS NULL;",
                "ALTER TABLE documentos ADD COLUMN IF NOT EXISTS archivo_binario BYTEA;",
                "ALTER TABLE comparaciones ADD COLUMN IF NOT EXISTS archivo_binario BYTEA;",
                "ALTER TABLE personas ADD COLUMN IF NOT EXISTS documento_pdf_id UUID REFERENCES documentos(id) ON DELETE SET NULL;",
                "ALTER TABLE documentos DROP CONSTRAINT IF EXISTS documentos_estado_check;",
                "ALTER TABLE documentos ADD CONSTRAINT documentos_estado_check CHECK (estado IN ('pendiente', 'procesando', 'completado', 'error', 'revision', 'cancelado'));"
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

    # ── Auto-curación de personas con PDF individual desvinculadas de su lote principal ──
    # Solo toca personas cuyo documento actual es un PDF individual subido desde "Subir PDF"
    # (cedula_*.pdf o es_pdf_individual) y las devuelve a la ficha que las registró en su snapshot.
    try:
        from app.models.persona import Persona
        from app.models.documento import Documento
        db_s = SessionLocal()
        try:
            def _es_pdf_individual(doc) -> bool:
                if not doc:
                    return False
                meta = doc.metadatos if isinstance(doc.metadatos, dict) else {}
                return bool(meta.get("es_pdf_individual")) or (doc.nombre_archivo or "").lower().startswith("cedula_")

            docs_lote = db_s.query(Documento).filter(Documento.metadatos.isnot(None)).all()
            for d_padre in docs_lote:
                if _es_pdf_individual(d_padre):
                    continue
                snap = d_padre.metadatos.get("personas_extraidas_datos") if isinstance(d_padre.metadatos, dict) else None
                if not snap or not isinstance(snap, list):
                    continue
                for item in snap:
                    pid = item.get("id") if isinstance(item, dict) else None
                    if not pid:
                        continue
                    pers = db_s.query(Persona).filter(Persona.id == pid).first()
                    if not pers or pers.documento_id == d_padre.id or pers.documento_pdf_id:
                        continue
                    doc_ind = pers.documento
                    if not _es_pdf_individual(doc_ind) or doc_ind.usuario_id != d_padre.usuario_id:
                        continue
                    pers.documento_pdf_id = doc_ind.id
                    pers.documento_id = d_padre.id
                    det = dict(pers.detalles_campos or {})
                    det["en_pdf"] = True
                    det["documento_pdf_id"] = str(doc_ind.id)
                    det["documento_padre_id"] = str(d_padre.id)
                    det.pop("motivo_no_en_pdf", None)
                    pers.detalles_campos = det
                    doc_ind.visible_en_subida = False
                    meta = dict(doc_ind.metadatos or {})
                    meta["es_pdf_individual"] = True
                    meta["documento_padre_id"] = str(d_padre.id)
                    doc_ind.metadatos = meta

            db_s.commit()
            logger.info("Auto-curación de documentos individuales completada con éxito.")
        finally:
            db_s.close()
    except Exception as heal_err:
        logger.warning(f"Aviso en curación de personas/documentos: {heal_err}")

    # ── Saneamiento de nombres y reevaluación de estado de revisión ──
    try:
        from app.models.persona import Persona
        from app.utils.name_cleaner import resolver_nombre_completo, limpiar_tokens_ruido
        from app.utils.validators import validador
        db_s = SessionLocal()
        try:
            personas = db_s.query(Persona).all()
            modificados = 0
            for p in personas:
                detalles = p.detalles_campos or {}
                disc_excel = detalles.get("discrepancia_excel") if isinstance(detalles, dict) else None
                # Los nombres corregidos a mano (PUT de persona o "Corregir" en Comparación) no se recalculan
                nombre_revisado_a_mano = bool(
                    {"nombre_completo", "nombres", "apellidos"} & set(p.campos_revisados or [])
                )
                if nombre_revisado_a_mano:
                    pass
                elif disc_excel and isinstance(disc_excel, dict) and disc_excel.get("nombre_excel"):
                    nom_ofic = disc_excel["nombre_excel"].strip()
                    if nom_ofic and p.nombre_completo != nom_ofic:
                        p.nombre_completo = nom_ofic
                        modificados += 1
                else:
                    nomb_limp = validador.normalizar_nombre(limpiar_tokens_ruido(p.nombres or ""))
                    apel_limp = validador.normalizar_nombre(limpiar_tokens_ruido(p.apellidos or ""))
                    nom_limpio = resolver_nombre_completo(nomb_limp, apel_limp, p.nombre_completo)

                    if nomb_limp != (p.nombres or ""):
                        p.nombres = nomb_limp or None
                        modificados += 1
                    if apel_limp != (p.apellidos or ""):
                        p.apellidos = apel_limp or None
                        modificados += 1
                    if nom_limpio and nom_limpio != p.nombre_completo:
                        p.nombre_completo = nom_limpio
                        modificados += 1

                det_actual = dict(p.detalles_campos or {})
                tiene_datos, motivos_rev = validador.evaluar_persona_completa(
                    numero_identificacion=p.numero_identificacion,
                    nombres=p.nombres,
                    apellidos=p.apellidos,
                    nombre_completo=p.nombre_completo,
                    fecha_nacimiento=p.fecha_nacimiento,
                    fecha_expedicion=p.fecha_expedicion,
                    lugar_expedicion=p.lugar_expedicion,
                    sexo=p.sexo,
                    confianza=float(p.confianza_extraccion or 0),
                    detalles_campos=det_actual,
                    motor_ocr=p.motor_ocr,
                    tipo_documento=p.tipo_documento,
                )
                nuevo_req = not tiene_datos
                nuevo_est = "VALID" if tiene_datos else ("FALLBACK_TESSERACT" if p.motor_ocr == "tesseract_fallback" else "REVIEW_REQUIRED")
                
                det = det_actual
                if motivos_rev:
                    det["motivos_revision"] = motivos_rev
                else:
                    det.pop("motivos_revision", None)

                # Mantener sincronizado detalles_campos de nombre_completo
                if "nombre_completo" in det and isinstance(det["nombre_completo"], dict):
                    det["nombre_completo"]["valor"] = p.nombre_completo
                    det["nombre_completo"]["value"] = p.nombre_completo
                    es_v_nom, mot_v_nom = validador.validar_nombre_estricto(p.nombre_completo)
                    det["nombre_completo"]["status"] = "VALID" if es_v_nom else "REVIEW_REQUIRED"
                    if not es_v_nom:
                        det["nombre_completo"]["reason"] = mot_v_nom

                p.detalles_campos = det

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
        db = SessionLocal()
        try:
            crear_admin_inicial(db)
        finally:
            db.close()
    except Exception as err:
        logger.warning(f"No se pudo verificar/crear el administrador inicial: {err}")


def crear_admin_inicial(db) -> bool:
    """
    Crea el administrador inicial definido en ADMIN_EMAIL y ADMIN_PASSWORD si ese correo
    aún no existe. Nunca modifica usuarios existentes ni sus contraseñas.
    Retorna True si creó el usuario.
    """
    from pydantic import EmailStr, TypeAdapter
    from sqlalchemy import func
    from app.models.usuario import Usuario

    email = (settings.ADMIN_EMAIL or "").strip().lower()
    if not email or not settings.ADMIN_PASSWORD:
        if not db.query(Usuario).filter(Usuario.rol == "admin").first():
            logger.warning(
                "No existe ningún administrador. Define ADMIN_EMAIL y ADMIN_PASSWORD "
                "para crear el administrador inicial al arrancar."
            )
        return False

    # El login valida el correo con EmailStr: un correo que no pase no podría iniciar sesión
    try:
        TypeAdapter(EmailStr).validate_python(email)
    except ValueError:
        logger.error(f"ADMIN_EMAIL no es un correo válido para iniciar sesión: {email}")
        return False

    if db.query(Usuario).filter(func.lower(Usuario.email) == email).first():
        return False

    db.add(Usuario(
        email=email,
        nombre=settings.ADMIN_NOMBRE,
        password_hash=_hash_password(settings.ADMIN_PASSWORD),
        rol="admin",
        activo=True,
    ))
    db.commit()
    logger.info(f"Administrador inicial creado: {email}")
    return True


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
