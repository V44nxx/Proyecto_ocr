"""
Test de persistencia y auto-restauración de archivos (PDF y Excel)
y de enriquecimiento de personas con evidencia de Excel.
"""
import uuid
from datetime import datetime
from pathlib import Path
from app.models.documento import Documento
from app.models.comparacion import Comparacion
from app.models.persona import Persona
from app.routers.personas import _enriquecer_persona_response


def test_documento_auto_restaurar(tmp_path, monkeypatch):
    """Verifica que si el PDF no existe en disco, se restaura desde archivo_binario"""
    monkeypatch.setattr("app.config.settings.UPLOAD_DIR", str(tmp_path))
    
    contenido_pdf = b"%PDF-1.4 mock pdf content test"
    nombre_archivo = f"test_doc_{uuid.uuid4().hex[:8]}.pdf"
    
    doc = Documento(
        id=uuid.uuid4(),
        nombre_archivo=nombre_archivo,
        nombre_original="original.pdf",
        ruta_archivo=str(tmp_path / nombre_archivo),
        archivo_binario=contenido_pdf,
    )
    
    # El archivo no existe aún en disco
    ruta_en_disco = tmp_path / nombre_archivo
    assert not ruta_en_disco.exists()
    
    # Llamar a obtener_ruta_o_restaurar
    ruta_obtenida = doc.obtener_ruta_o_restaurar()
    assert ruta_obtenida is not None
    assert ruta_obtenida.exists()
    assert ruta_obtenida.read_bytes() == contenido_pdf


def test_comparacion_auto_restaurar(tmp_path, monkeypatch):
    """Verifica que si el Excel no existe en disco, se restaura desde archivo_binario"""
    monkeypatch.setattr("app.config.settings.UPLOAD_DIR", str(tmp_path))
    
    contenido_excel = b"mock excel bytes"
    nombre_archivo = f"comp_{uuid.uuid4().hex[:8]}.xlsx"
    
    comp = Comparacion(
        id=uuid.uuid4(),
        nombre_archivo=nombre_archivo,
        nombre_original="planilla.xlsx",
        ruta_archivo=str(tmp_path / nombre_archivo),
        archivo_binario=contenido_excel,
    )
    
    ruta_en_disco = tmp_path / nombre_archivo
    assert not ruta_en_disco.exists()
    
    ruta_obtenida = comp.obtener_ruta_o_restaurar()
    assert ruta_obtenida is not None
    assert ruta_obtenida.exists()
    assert ruta_obtenida.read_bytes() == contenido_excel


def test_enriquecer_persona_con_evidencia_excel():
    """
    Verifica que si la persona fue enriquecida con Excel (source: excel_oficial),
    se marca en_excel=True directamente, incluso si ids_en_excel no contiene su ID
    o si los archivos se reiniciaron tras un despliegue.
    """
    ahora = datetime.utcnow()
    p = Persona(
        id=uuid.uuid4(),
        numero_identificacion="26629780",
        nombre_completo="MARIA MABEL RAMOS AGUIRRE",
        nombres="MARIA MABEL",
        apellidos="RAMOS AGUIRRE",
        tipo_documento="CEDULA_CIUDADANIA",
        requiere_revision=False,
        estado_registro="VALID",
        fecha_registro=ahora,
        fecha_actualizacion=ahora,
        detalles_campos={
            "nombre_completo": {
                "valor": "MARIA MABEL RAMOS AGUIRRE",
                "source": "excel_oficial",
                "status": "VALID"
            }
        },
        motor_ocr="google_document_ai",
        documento_id=str(uuid.uuid4()),
    )
    
    # Caso 1: hay_excel es False (disco reiniciado)
    resp = _enriquecer_persona_response(p, ids_en_excel=set(), hay_excel=False)
    assert resp.en_excel is True
    
    # Caso 2: hay_excel es True pero ids_en_excel está vacío (fallback parcial)
    resp2 = _enriquecer_persona_response(p, ids_en_excel=set(), hay_excel=True)
    assert resp2.en_excel is True


def test_enriquecer_persona_sin_excel():
    """Verifica que si la persona no tiene evidencia y hay_excel es True, en_excel es False"""
    ahora = datetime.utcnow()
    p = Persona(
        id=uuid.uuid4(),
        numero_identificacion="99999999",
        nombre_completo="PERSONA SIN EXCEL",
        nombres="PERSONA",
        apellidos="SIN EXCEL",
        tipo_documento="CEDULA_CIUDADANIA",
        requiere_revision=False,
        estado_registro="VALID",
        fecha_registro=ahora,
        fecha_actualizacion=ahora,
        detalles_campos={},
        motor_ocr="google_document_ai",
        documento_id=str(uuid.uuid4()),
    )
    
    resp = _enriquecer_persona_response(p, ids_en_excel={"12345678"}, hay_excel=True)
    assert resp.en_excel is False
