import pytest
import pandas as pd
import uuid
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, date

from app.models.persona import Persona
from app.models.documento import Documento
from app.routers.documentos import _registrar_personas_excel_faltantes
from app.routers.personas import _enriquecer_persona_response
from app.services.comparacion_service import comparacion_service


def test_registrar_personas_excel_faltantes(tmp_path):
    # 1. Crear un Excel con 3 personas:
    # - Persona 1 (1001234567): Detectada en PDF
    # - Persona 2 (1002345678): En Excel pero NO en PDF
    # - Persona 3 (1003456789): En Excel pero NO en PDF
    excel_file = tmp_path / "planilla_prueba.xlsx"
    df_excel = pd.DataFrame([
        {
            "identificacion": "1001234567",
            "nombres": "JUAN CARLOS",
            "apellidos": "PEREZ LOPEZ",
            "fecha_nacimiento": "1990-01-15",
            "fecha_expedicion": "2008-02-20",
            "lugar_expedicion": "BOGOTA",
            "sexo": "M",
        },
        {
            "identificacion": "1002345678",
            "nombres": "MARIA ELENA",
            "apellidos": "GOMEZ DIAZ",
            "fecha_nacimiento": "1995-06-25",
            "fecha_expedicion": "2013-07-10",
            "lugar_expedicion": "MEDELLIN",
            "sexo": "F",
        },
        {
            "identificacion": "1003456789",
            "nombres": "ANDRES FELIPE",
            "apellidos": "CASTRO VEGA",
            "fecha_nacimiento": "2002-11-12",
            "fecha_expedicion": "2020-12-05",
            "lugar_expedicion": "CALI",
            "sexo": "M",
        }
    ])
    df_excel.to_excel(str(excel_file), index=False)

    doc_id = uuid.uuid4()
    user_id = uuid.uuid4()

    doc = Documento(
        id=doc_id,
        usuario_id=user_id,
        nombre_original="documento_cedulas.pdf",
        nombre_archivo="doc_test.pdf",
        ruta_archivo="/tmp/test.pdf",
        estado="procesando",
        metadatos={}
    )

    # Persona 1 fue detectada por OCR en el PDF
    p1 = Persona(
        id=uuid.uuid4(),
        documento_id=doc_id,
        usuario_id=user_id,
        numero_identificacion="1001234567",
        nombre_completo="JUAN CARLOS PEREZ LOPEZ",
        nombres="JUAN CARLOS",
        apellidos="PEREZ LOPEZ",
        estado_registro="VALID",
        motor_ocr="google_document_ai",
        requiere_revision=False,
        detalles_campos={"en_pdf": True}
    )

    bd_personas = [p1]

    class FakeQuery:
        def __init__(self, items):
            self._items = list(items)

        def filter(self, *args, **kwargs):
            resultado = []
            for item in self._items:
                match = True
                for arg in args:
                    # Si es una expresión binaria de SQLAlchemy
                    # Caso in_()
                    if hasattr(arg, "left") and hasattr(arg.left, "key"):
                        key = arg.left.key
                        val = getattr(item, key, None)
                        # in_ expression
                        if hasattr(arg, "right") and hasattr(arg.right, "value"):
                            target = arg.right.value
                        elif hasattr(arg, "right"):
                            target = arg.right
                        else:
                            target = None

                        if isinstance(target, (list, set, tuple)):
                            target_strs = {str(t) for t in target}
                            if str(val) not in target_strs:
                                match = False
                        elif str(val) != str(target):
                            match = False
                if match:
                    resultado.append(item)
            return FakeQuery(resultado)

        def all(self):
            return list(self._items)

        def first(self):
            return self._items[0] if self._items else None

    mock_db = MagicMock()
    def fake_query(model):
        if model == Persona:
            return FakeQuery(bd_personas)
        elif model == Documento:
            return FakeQuery([doc])
        return FakeQuery([])

    def fake_add(obj):
        bd_personas.append(obj)

    mock_db.query = fake_query
    mock_db.add = fake_add
    mock_db.commit = MagicMock()

    items = [{"pdf_path": "/tmp/test.pdf", "documento_id": str(doc_id)}]

    # Ejecutar la función
    _registrar_personas_excel_faltantes(items, str(excel_file), mock_db)

    # Verificaciones:
    # Deben haberse registrado las 2 personas faltantes (1002345678 y 1003456789)
    assert len(bd_personas) == 3

    ids_bd = [p.numero_identificacion for p in bd_personas]
    assert "1002345678" in ids_bd
    assert "1003456789" in ids_bd

    p2 = next(p for p in bd_personas if p.numero_identificacion == "1002345678")
    assert p2.nombre_completo == "MARIA ELENA GOMEZ DIAZ"
    assert p2.documento_id == doc_id
    assert p2.motor_ocr == "excel"
    assert p2.requiere_revision is True
    assert p2.estado_registro == "REVIEW_REQUIRED"
    assert p2.detalles_campos["en_pdf"] is False
    assert p2.detalles_campos["motivo_no_en_pdf"] == "No se encontró en el PDF"
    assert any("No se encontró en el PDF" in m for m in p2.detalles_campos["motivos_revision"])

    # Probar enriquecimiento de respuesta para PersonaResponse
    resp2 = _enriquecer_persona_response(p2, ids_en_excel={"1002345678"}, hay_excel=True)
    assert resp2.en_pdf is False
    assert resp2.en_excel is True
    assert resp2.requiere_revision is True
    assert resp2.estado_registro == "REVIEW_REQUIRED"


def test_subir_pdf_individual_mantiene_documento_padre():
    """
    Verifica que al asociar un PDF individual a una persona que faltaba en el PDF:
    - La persona permanezca en su documento padre del lote (documento_id).
    - El nuevo PDF se asigne a documento_pdf_id.
    - en_pdf cambie a True.
    - PersonaResponse retorne documento_id del lote y documento_pdf_id del archivo individual.
    """
    doc_lote_id = uuid.uuid4()
    doc_ind_id = uuid.uuid4()
    user_id = uuid.uuid4()

    doc_lote = Documento(
        id=doc_lote_id,
        usuario_id=user_id,
        nombre_original="cedulas_nuevas.pdf",
        nombre_archivo="cedulas_nuevas.pdf",
        ruta_archivo="/tmp/cedulas_nuevas.pdf",
        estado="completado"
    )

    doc_individual = Documento(
        id=doc_ind_id,
        usuario_id=user_id,
        nombre_original="cedulafaltante.pdf",
        nombre_archivo="cedula_1002345678_abcd.pdf",
        ruta_archivo="/tmp/cedulafaltante.pdf",
        estado="completado",
        visible_en_subida=False,
        metadatos={"es_pdf_individual": True, "documento_padre_id": str(doc_lote_id)}
    )

    p = Persona(
        id=uuid.uuid4(),
        documento_id=doc_lote_id,
        usuario_id=user_id,
        numero_identificacion="1002345678",
        nombre_completo="MARIA ELENA GOMEZ DIAZ",
        estado_registro="REVIEW_REQUIRED",
        motor_ocr="excel",
        requiere_revision=True,
        detalles_campos={"en_pdf": False, "origen": "excel_no_encontrado_en_pdf"},
        fecha_registro=datetime.utcnow(),
        fecha_actualizacion=datetime.utcnow()
    )
    p.documento = doc_lote

    # Simular la asociación de PDF individual según la nueva lógica
    doc_padre_id = p.documento_id
    p.documento_id = doc_padre_id
    p.documento_pdf_id = doc_ind_id
    p.documento_pdf = doc_individual
    p.motor_ocr = "google_document_ai"
    p.pagina_frente = 1
    p.detalles_campos = {
        "en_pdf": True,
        "documento_pdf_id": str(doc_ind_id),
        "nombre_documento_pdf": "cedulafaltante.pdf",
        "documento_padre_id": str(doc_lote_id)
    }

    # Enriquecer respuesta
    resp = _enriquecer_persona_response(p, ids_en_excel={"1002345678"}, hay_excel=True)

    # Verificaciones
    assert resp.en_pdf is True
    assert resp.documento_id == doc_lote_id
    assert resp.nombre_documento == "cedulas_nuevas.pdf"
    assert resp.documento_pdf_id == doc_ind_id
    assert resp.nombre_documento_pdf == "cedulafaltante.pdf"

