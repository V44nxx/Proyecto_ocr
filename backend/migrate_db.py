"""
Script de migración rápida de esquema PostgreSQL.
Añade columnas faltantes a la tabla personas si no existen.
"""
import sys
from sqlalchemy import text

sys.path.insert(0, "backend")

from app.database import engine, SessionLocal


def migrar_columnas():
    print("Ejecutando migración de esquema en PostgreSQL...")
    db = SessionLocal()
    try:
        queries = [
            "ALTER TABLE personas ADD COLUMN IF NOT EXISTS grupo_documento_id VARCHAR(100);",
            "ALTER TABLE personas ADD COLUMN IF NOT EXISTS pagina_frente INTEGER;",
            "ALTER TABLE personas ADD COLUMN IF NOT EXISTS pagina_reverso INTEGER;",
            "ALTER TABLE personas ADD COLUMN IF NOT EXISTS pagina_numero INTEGER;",
            "ALTER TABLE personas ADD COLUMN IF NOT EXISTS tipo_documento VARCHAR(50) DEFAULT 'CEDULA_CIUDADANIA';",
            "ALTER TABLE personas ADD COLUMN IF NOT EXISTS estado_registro VARCHAR(30) DEFAULT 'VALID';",
            "ALTER TABLE personas ADD COLUMN IF NOT EXISTS motor_ocr VARCHAR(50) DEFAULT 'google_document_ai';",
            "ALTER TABLE personas ADD COLUMN IF NOT EXISTS detalles_campos JSONB;"
        ]
        for q in queries:
            db.execute(text(q))
        db.commit()
        print("Migración completada con éxito. Todas las columnas requeridas existen.")
    except Exception as e:
        db.rollback()
        print(f"Error en migración de BD: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    migrar_columnas()
