"""
Router de Documentos
Endpoints: Upload PDF, listar, detalle, eliminar
"""
import uuid
import shutil
from pathlib import Path
from typing import List
from datetime import datetime
import threading

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.documento import Documento
from app.models.usuario import Usuario
from app.schemas.documento import DocumentoResponse
from app.routers.auth import get_usuario_actual
from app.services.ocr_service import ocr_service
from app.config import settings
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/documentos", tags=["Documentos"])


def _validar_pdf(file: UploadFile):
    """Valida que el archivo sea un PDF válido"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Solo se aceptan archivos PDF. Archivo recibido: {file.filename}"
        )

    if file.size and file.size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo muy grande. Máximo {settings.MAX_FILE_SIZE_MB}MB"
        )


def _procesar_ocr_background(pdf_path: str, documento_id: str):
    """
    Ejecuta OCR en hilo de fondo.
    Siempre usa su propia sesión (db_externa=None) para no compartir
    estado con el hilo principal.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        ocr_service.procesar_pdf(str(pdf_path), documento_id, db_externa=db)
    finally:
        db.close()


# ──────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────
@router.post(
    "/upload",
    summary="Subir PDF(s) para procesamiento OCR",
    status_code=202
)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Uno o múltiples archivos PDF"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Sube uno o múltiples archivos PDF y los encola para procesamiento OCR.
    El procesamiento ocurre en segundo plano.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    resultados = []

    for file in files:
        _validar_pdf(file)

        # Guardar archivo con nombre único
        nombre_unico = f"{uuid.uuid4()}_{file.filename}"
        ruta_archivo = settings.upload_path / nombre_unico

        content = await file.read()
        ruta_archivo.write_bytes(content)

        # Crear registro en BD
        documento = Documento(
            usuario_id=usuario.id,
            nombre_archivo=nombre_unico,
            nombre_original=file.filename,
            ruta_archivo=str(ruta_archivo),
            tamano_bytes=len(content),
            estado="procesando",
        )
        db.add(documento)
        db.commit()
        db.refresh(documento)

        # ── Encolar OCR en segundo plano ──────────────────────────────────
        # Evita timeout de HTTP cuando el PDF tiene decenas de páginas (ej. 42 págs)
        background_tasks.add_task(
            _procesar_ocr_background,
            str(ruta_archivo),
            str(documento.id),
        )

        logger.info(
            f"PDF encolado en segundo plano: {file.filename} (ID: {documento.id})"
        )

        resultados.append({
            "id": str(documento.id),
            "nombre_original": documento.nombre_original,
            "estado": "procesando",
            "mensaje": "Archivo recibido. Procesando páginas en segundo plano con Google Document AI.",
        })

    return {
        "total": len(resultados),
        "documentos": resultados,
    }


@router.get("", response_model=List[DocumentoResponse], summary="Listar documentos")
def listar_documentos(
    skip: int = 0,
    limit: int = 50,
    estado: str = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Lista todos los documentos subidos por el usuario"""
    query = db.query(Documento).filter(Documento.usuario_id == usuario.id)

    if estado:
        query = query.filter(Documento.estado == estado)

    documentos = query.order_by(Documento.fecha_carga.desc()).offset(skip).limit(limit).all()
    return [DocumentoResponse.model_validate(d) for d in documentos]


@router.get("/{documento_id}", response_model=DocumentoResponse, summary="Detalle de documento")
def obtener_documento(
    documento_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Obtiene el detalle de un documento específico"""
    documento = db.query(Documento).filter(
        Documento.id == documento_id,
        Documento.usuario_id == usuario.id
    ).first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    return DocumentoResponse.model_validate(documento)


@router.get("/{documento_id}/estado", summary="Estado de procesamiento OCR")
def estado_documento(
    documento_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Consulta el estado actual del procesamiento OCR de un documento"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    return {
        "id": str(documento.id),
        "estado": documento.estado,
        "confianza_ocr": float(documento.confianza_ocr) if documento.confianza_ocr else None,
        "tiempo_procesamiento_ms": documento.tiempo_procesamiento_ms,
        "mensaje_error": documento.mensaje_error,
        "fecha_procesamiento": documento.fecha_procesamiento,
    }


@router.delete("/{documento_id}", status_code=204, summary="Eliminar documento")
def eliminar_documento(
    documento_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Elimina un documento y su archivo asociado"""
    documento = db.query(Documento).filter(
        Documento.id == documento_id,
        Documento.usuario_id == usuario.id
    ).first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Eliminar archivo físico
    if documento.ruta_archivo and Path(documento.ruta_archivo).exists():
        Path(documento.ruta_archivo).unlink()

    db.delete(documento)
    db.commit()
    logger.info(f"Documento eliminado: {documento.nombre_original}")


@router.get("/dashboard/estadisticas", summary="Estadísticas del dashboard")
def estadisticas_dashboard(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Retorna estadísticas para el dashboard principal"""
    from app.models.persona import Persona

    total_docs = db.query(Documento).count()
    completados = db.query(Documento).filter(Documento.estado == "completado").count()
    en_proceso = db.query(Documento).filter(Documento.estado == "procesando").count()
    errores = db.query(Documento).filter(Documento.estado == "error").count()
    total_personas = db.query(Persona).count()
    revision = db.query(Persona).filter(Persona.requiere_revision == True).count()

    from app.models.comparacion import Comparacion
    total_comparaciones = db.query(Comparacion).count()

    return {
        "total_documentos": total_docs,
        "documentos_completados": completados,
        "documentos_procesando": en_proceso,
        "documentos_con_error": errores,
        "total_personas": total_personas,
        "personas_en_revision": revision,
        "total_comparaciones": total_comparaciones,
    }


@router.get("/{documento_id}/debug_espacial", summary="Trazabilidad y cajas delimitadoras espaciales")
def debug_espacial_documento(
    documento_id: str,
    pagina: int = 1,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Devuelve las cajas delimitadoras (LABEL, CANDIDATE, ACCEPTED, REJECTED) para depuración visual"""
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    from app.services.spatial_debug_service import spatial_debug_service
    # Para depuración visual, retornar reporte espacial de la página solicitada
    return spatial_debug_service.generar_reporte_debug(lines=[], page_num=pagina)
