from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app.models.usuario import Usuario
from app.routers.auth import get_usuario_actual
from app.services.exportacion_service import exportacion_service
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/exportacion", tags=["Exportación"])


class ExportarPersonasRequest(BaseModel):
    requiere_revision: Optional[bool] = None
    documento_id: Optional[str] = None
    persona_ids: Optional[List[str]] = None


def _generar_descarga_personas(db: Session, usuario: Usuario, filtros: dict):
    try:
        ruta_archivo = exportacion_service.exportar_personas(db, filtros or None)

        if not Path(ruta_archivo).exists():
            raise HTTPException(status_code=500, detail="Error generando archivo Excel")

        nombre_descarga = Path(ruta_archivo).name
        logger.info(f"Exportación XLSX generada para {usuario.email}: {nombre_descarga}")

        return FileResponse(
            path=ruta_archivo,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=nombre_descarga,
            headers={
                "Content-Disposition": f'attachment; filename="{nombre_descarga}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            }
        )
    except Exception as e:
        logger.error(f"Error en exportación: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando exportación: {str(e)}")


@router.get("/xlsx", summary="Exportar personas a Excel (GET)")
def exportar_xlsx(
    requiere_revision: Optional[bool] = Query(None),
    documento_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Genera un archivo XLSX filtrado por documento o estado de revisión.
    Retorna el archivo para descarga directa.
    """
    filtros = {}
    if requiere_revision is not None:
        filtros["requiere_revision"] = requiere_revision
    if documento_id:
        filtros["documento_id"] = documento_id

    return _generar_descarga_personas(db, usuario, filtros)


@router.post("/xlsx", summary="Exportar selección de personas a Excel (POST)")
def exportar_personas_post(
    payload: ExportarPersonasRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Genera un archivo XLSX a partir de filtros y/o una lista específica de IDs de personas seleccionadas.
    """
    filtros = {}
    if payload.requiere_revision is not None:
        filtros["requiere_revision"] = payload.requiere_revision
    if payload.documento_id:
        filtros["documento_id"] = payload.documento_id
    if payload.persona_ids:
        filtros["persona_ids"] = payload.persona_ids

    return _generar_descarga_personas(db, usuario, filtros)


@router.get("/diferencias/{comparacion_id}", summary="Exportar reporte de diferencias a Excel")
def exportar_diferencias_xlsx(
    comparacion_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    try:
        ruta_archivo = exportacion_service.exportar_reporte_diferencias(db, comparacion_id)
        if not Path(ruta_archivo).exists():
            raise HTTPException(status_code=500, detail="Error generando reporte de diferencias")

        nombre_descarga = Path(ruta_archivo).name
        return FileResponse(
            path=ruta_archivo,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=nombre_descarga,
            headers={"Content-Disposition": f"attachment; filename={nombre_descarga}"}
        )
    except Exception as e:
        logger.error(f"Error exportando diferencias: {e}")
        raise HTTPException(status_code=500, detail=str(e))
