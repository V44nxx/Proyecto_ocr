"""
Script para limpiar la base de datos de pruebas (personas, documentos, comparaciones y diferencias)
sin eliminar esquemas ni usuarios.
"""
import sys

sys.path.insert(0, "backend")

from app.database import SessionLocal
from app.models.persona import Persona
from app.models.documento import Documento
from app.models.comparacion import Comparacion
from app.models.diferencia import Diferencia


def limpiar_base_datos():
    db = SessionLocal()
    try:
        num_difs = db.query(Diferencia).delete()
        num_comps = db.query(Comparacion).delete()
        num_pers = db.query(Persona).delete()
        num_docs = db.query(Documento).delete()
        db.commit()
        print(f"Base de datos limpia correctamente:")
        print(f" - {num_difs} diferencias eliminadas")
        print(f" - {num_comps} comparaciones eliminadas")
        print(f" - {num_pers} personas eliminadas")
        print(f" - {num_docs} documentos eliminados")
    except Exception as e:
        db.rollback()
        print(f"Error limpiando base de datos: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    limpiar_base_datos()
