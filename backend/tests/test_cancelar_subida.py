"""
Tests para el endpoint de cancelar subida y procesamiento de documentos.
Verifica que los documentos, archivos en disco y personas asociadas sean removidos por completo.
"""
import uuid
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.models.documento import Documento
from app.models.persona import Persona
from app.models.comparacion import Comparacion
from app.models.usuario import Usuario
from app.routers.documentos import (
    CancelarSubidaRequest,
    cancelar_subida_o_procesamiento,
)


def test_cancelar_subida_documento_especifico(tmp_path):
    """Verifica que al cancelar un documento específico, se remueve de BD y disco."""
    user_id = uuid.uuid4()
    usuario = Usuario(id=user_id, email="test@example.com", rol="digitador")

    pdf_file = tmp_path / "test_doc.pdf"
    pdf_file.write_bytes(b"%PDF mock content")

    doc_id = uuid.uuid4()
    doc = Documento(
        id=doc_id,
        usuario_id=user_id,
        nombre_original="test_doc.pdf",
        nombre_archivo="test_doc.pdf",
        ruta_archivo=str(pdf_file),
        estado="procesando",
    )

    p_id = uuid.uuid4()
    persona = Persona(
        id=p_id,
        documento_id=doc_id,
        usuario_id=user_id,
        numero_identificacion="12345678",
        nombre_completo="TEST PERSONA",
    )

    excel_file = tmp_path / "comp_excel.xlsx"
    excel_file.write_bytes(b"mock excel")

    comp_id = uuid.uuid4()
    comp = Comparacion(
        id=comp_id,
        usuario_id=user_id,
        nombre_archivo="comp_excel.xlsx",
        nombre_original="planilla.xlsx",
        ruta_archivo=str(excel_file),
        estado="pendiente",
    )

    db = MagicMock()
    # Mock queries
    def mock_query(model):
        m_q = MagicMock()
        if model == Documento:
            m_q.filter.return_value.all.return_value = [doc]
            m_q.filter.return_value.first.return_value = doc
        elif model == Persona:
            m_q.filter.return_value.delete.return_value = 1
        elif model == Comparacion:
            m_q.filter.return_value.first.return_value = comp
            m_q.filter.return_value.all.return_value = [comp]
        return m_q

    db.query.side_effect = mock_query

    req = CancelarSubidaRequest(
        documento_ids=[str(doc_id)],
        comparacion_id=str(comp_id),
        todos_en_proceso=False,
    )

    res = cancelar_subida_o_procesamiento(payload=req, db=db, usuario=usuario)

    assert res["ok"] is True
    assert res["eliminados"] == 1

    # Verificar que los archivos en disco fueron eliminados
    assert not pdf_file.exists()
    assert not excel_file.exists()

    # Verificar que se llamó a db.delete para el documento y la comparación
    db.delete.assert_any_call(doc)
    db.delete.assert_any_call(comp)
    db.commit.assert_called()


def test_cancelar_subida_aislamiento_usuario(tmp_path):
    """Verifica que un usuario no pueda cancelar documentos de otro usuario."""
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()
    usuario1 = Usuario(id=user1_id, email="user1@example.com", rol="digitador")

    doc_otro_usuario = Documento(
        id=uuid.uuid4(),
        usuario_id=user2_id,
        nombre_original="otro.pdf",
        estado="procesando",
    )

    db = MagicMock()
    # Cuando usuario 1 busca documentos, la consulta con filter(usuario_id == user1_id) devuelve vacio
    m_q = MagicMock()
    m_q.filter.return_value.all.return_value = []
    db.query.return_value = m_q

    req = CancelarSubidaRequest(
        documento_ids=[str(doc_otro_usuario.id)],
        todos_en_proceso=False,
    )

    res = cancelar_subida_o_procesamiento(payload=req, db=db, usuario=usuario1)

    assert res["ok"] is True
    assert res["eliminados"] == 0
    # No se debió borrar nada
    db.delete.assert_not_called()
