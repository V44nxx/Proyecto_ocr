import uuid
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from pathlib import Path

from app.database import get_db
from app.models.comparacion import Comparacion
from app.models.usuario import Usuario
from app.routers.auth import get_usuario_actual
from app.services import auditoria
from app.services.exportacion_service import exportacion_service
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/exportacion", tags=["Exportación"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ExportarPersonasRequest(BaseModel):
    requiere_revision: Optional[bool] = None
    solo_menores: Optional[bool] = None
    documento_id: Optional[str] = None
    persona_ids: Optional[List[str]] = None


def borrar_archivo(ruta: str) -> None:
    """Los Excel generados tienen datos personales: se borran del servidor apenas se envían."""
    try:
        Path(ruta).unlink(missing_ok=True)
    except OSError as e:
        logger.warning(f"No se pudo borrar el archivo exportado {Path(ruta).name}: {e}")


def descarga_xlsx(ruta_archivo: str) -> FileResponse:
    nombre_descarga = Path(ruta_archivo).name
    return FileResponse(
        path=ruta_archivo,
        media_type=XLSX,
        filename=nombre_descarga,
        headers={
            "Content-Disposition": f'attachment; filename="{nombre_descarga}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Cache-Control": "private, no-store",
        },
        background=BackgroundTask(borrar_archivo, ruta_archivo),
    )


def _generar_descarga_personas(db: Session, usuario: Usuario, filtros: dict, request: Request):
    filtros_con_usuario = dict(filtros or {})
    filtros_con_usuario["usuario_id"] = str(usuario.id)
    filtros_con_usuario["es_admin"] = getattr(usuario, "rol", None) == "admin"
    ruta_archivo = exportacion_service.exportar_personas(db, filtros_con_usuario)
    if not Path(ruta_archivo).exists():
        raise HTTPException(status_code=500, detail="No se pudo generar el archivo Excel")

    logger.info(f"Exportación XLSX generada para {usuario.email}: {Path(ruta_archivo).name}")
    auditoria.registrar("exportacion_personas", request, usuario=usuario,
                        filtros={k: v for k, v in (filtros or {}).items() if k != "persona_ids"},
                        personas_seleccionadas=len(filtros.get("persona_ids") or []) or None)
    return descarga_xlsx(ruta_archivo)


@router.get("/xlsx", summary="Exportar personas a Excel (GET)")
def exportar_xlsx(
    requiere_revision: Optional[bool] = Query(None),
    solo_menores: Optional[bool] = Query(None),
    documento_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
    request: Request = None,
):
    """
    Genera un archivo XLSX filtrado por documento, estado de revisión o solo menores de edad.
    Retorna el archivo para descarga directa.
    """
    filtros = {}
    if requiere_revision is not None:
        filtros["requiere_revision"] = requiere_revision
    if solo_menores is not None:
        filtros["solo_menores"] = solo_menores
    if documento_id:
        filtros["documento_id"] = documento_id

    return _generar_descarga_personas(db, usuario, filtros, request)


@router.post("/xlsx", summary="Exportar selección de personas a Excel (POST)")
def exportar_personas_post(
    payload: ExportarPersonasRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
    request: Request = None,
):
    """
    Genera un archivo XLSX a partir de filtros y/o una lista específica de IDs de personas seleccionadas.
    """
    filtros = {}
    if payload.requiere_revision is not None:
        filtros["requiere_revision"] = payload.requiere_revision
    if payload.solo_menores is not None:
        filtros["solo_menores"] = payload.solo_menores
    if payload.documento_id:
        filtros["documento_id"] = payload.documento_id
    if payload.persona_ids:
        filtros["persona_ids"] = payload.persona_ids

    return _generar_descarga_personas(db, usuario, filtros, request)


@router.get("/diferencias/{comparacion_id}", summary="Exportar reporte de diferencias a Excel")
def exportar_diferencias_xlsx(
    comparacion_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
    request: Request = None,
):
    """Reporte de diferencias de una comparación del propio usuario."""
    try:
        comp_uuid = uuid.UUID(comparacion_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Comparación no encontrada")
    comparacion = db.query(Comparacion).filter(
        Comparacion.id == comp_uuid, Comparacion.usuario_id == usuario.id
    ).first()
    if not comparacion:
        raise HTTPException(status_code=404, detail="Comparación no encontrada")

    ruta_archivo = exportacion_service.exportar_reporte_diferencias(db, str(comp_uuid), usuario_id=usuario.id)
    if not Path(ruta_archivo).exists():
        raise HTTPException(status_code=500, detail="No se pudo generar el reporte de diferencias")
    auditoria.registrar("exportacion_diferencias", request, usuario=usuario, comparacion_id=str(comp_uuid))
    return descarga_xlsx(ruta_archivo)
