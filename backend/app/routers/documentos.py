"""
Router de Documentos
Endpoints: Upload PDF, listar, detalle, eliminar, preview de página
"""
import uuid
import io
import shutil
from pathlib import Path
from typing import List, Optional, Union
from datetime import datetime
import threading

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.documento import Documento
from app.models.usuario import Usuario
from app.schemas.documento import DocumentoResponse
from app.routers.auth import get_usuario_actual, get_usuario_desde_token_o_query
from app.services.ocr_service import ocr_service
from app.config import settings
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/documentos", tags=["Documentos"])


def _validar_pdf(file: UploadFile):
    """Valida que el archivo sea un PDF válido"""
    fname = (file.filename or "").strip()
    if not fname.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Solo se aceptan archivos PDF (extensión .pdf). Archivo recibido: '{fname}'"
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
    files: Optional[List[UploadFile]] = File(default=None, description="Uno o múltiples archivos PDF"),
    file: Optional[UploadFile] = File(default=None, description="Archivo PDF individual"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Sube uno o múltiples archivos PDF y los encola para procesamiento OCR.
    Acepta tanto el parámetro 'files' (múltiple) como 'file' (individual).
    El procesamiento ocurre en segundo plano.
    """
    archivos_recibidos: List[UploadFile] = []
    if files:
        archivos_recibidos.extend([f for f in files if f and f.filename])
    if file and file.filename:
        archivos_recibidos.append(file)

    if not archivos_recibidos:
        raise HTTPException(status_code=400, detail="No se enviaron archivos PDF válidos")

    resultados = []

    for file in archivos_recibidos:
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
    """Lista todos los documentos subidos por el usuario (o todos si es admin)"""
    query = db.query(Documento)
    if usuario.rol != "admin":
        query = query.filter(Documento.usuario_id == usuario.id)

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
    query = db.query(Documento).filter(Documento.id == documento_id)
    if usuario.rol != "admin":
        query = query.filter(Documento.usuario_id == usuario.id)
    documento = query.first()

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

    meta = documento.metadatos or {}
    progreso = meta.get("progreso")
    if progreso is None:
        if documento.estado == "completado":
            progreso = 100
        elif documento.estado == "procesando":
            progreso = 25
        elif documento.estado == "error":
            progreso = 100
        else:
            progreso = 0

    paso = meta.get("paso")
    if not paso:
        if documento.estado == "completado":
            paso = "Procesamiento completado"
        elif documento.estado == "procesando":
            paso = "Procesando documento con OCR..."
        elif documento.estado == "error":
            paso = "Error durante el procesamiento"
        else:
            paso = "Pendiente en cola"

    personas_count = len(documento.personas) if documento.personas else meta.get("personas_extraidas", 0)

    return {
        "id": str(documento.id),
        "nombre_original": documento.nombre_original,
        "estado": documento.estado,
        "progreso": progreso,
        "paso": paso,
        "total_paginas": documento.total_paginas or meta.get("total_paginas", 0),
        "pagina_actual": meta.get("pagina_actual", 0),
        "personas_count": personas_count,
        "confianza_ocr": float(documento.confianza_ocr) if documento.confianza_ocr else None,
        "tiempo_procesamiento_ms": documento.tiempo_procesamiento_ms,
        "mensaje_error": documento.mensaje_error,
        "fecha_procesamiento": documento.fecha_procesamiento,
        "metadatos": meta,
    }



@router.delete("/{documento_id}", status_code=204, summary="Eliminar documento")
def eliminar_documento(
    documento_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Elimina un documento y su archivo asociado"""
    query = db.query(Documento).filter(Documento.id == documento_id)
    if usuario.rol != "admin":
        query = query.filter(Documento.usuario_id == usuario.id)
    documento = query.first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Eliminar archivo físico
    try:
        if documento.ruta_archivo and Path(documento.ruta_archivo).exists():
            Path(documento.ruta_archivo).unlink()
    except Exception as e:
        logger.warning(f"No se pudo eliminar archivo físico {documento.ruta_archivo}: {e}")

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


@router.get(
    "/{documento_id}/pagina/{numero}",
    summary="Vista previa de página del PDF como imagen",
    response_class=StreamingResponse,
)
def preview_pagina_pdf(
    documento_id: str,
    numero: int,
    request: Request,
    dpi: int = 150,
    token: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_desde_token_o_query),
):
    """
    Renderiza la página `numero` (1-indexed) del PDF asociado al documento
    y la devuelve como imagen PNG. Permite al frontend mostrar una vista
    previa de la página exacta donde se detectó la persona.
    """
    # 1. Obtener el documento
    query = db.query(Documento).filter(Documento.id == documento_id)
    if usuario.rol != "admin":
        query = query.filter(Documento.usuario_id == usuario.id)
    documento = query.first()

    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # 2. Verificar que el archivo existe
    ruta = Path(documento.ruta_archivo) if documento.ruta_archivo else None
    if not ruta or not ruta.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Archivo PDF no disponible en el servidor: {documento.nombre_original}"
        )

    # 3. Renderizar con PyMuPDF
    try:
        import fitz  # PyMuPDF
        pdf_doc = fitz.open(str(ruta))
        total_paginas = len(pdf_doc)

        # Convertir a 0-indexed y validar rango
        idx = numero - 1
        if idx < 0 or idx >= total_paginas:
            pdf_doc.close()
            raise HTTPException(
                status_code=400,
                detail=f"Página {numero} fuera de rango. El documento tiene {total_paginas} página(s)."
            )

        page = pdf_doc[idx]
        # Calcular zoom para el DPI solicitado (base PDF = 72 DPI)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png_bytes = pix.tobytes("png")
        pdf_doc.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renderizando página {numero} del PDF {documento_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al renderizar la página del PDF: {str(e)}")

    return StreamingResponse(
        io.BytesIO(png_bytes),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": f'inline; filename="doc_{documento_id}_p{numero}.png"',
        },
    )
