"""
Router de Exportación
Endpoint: Generar y descargar XLSX
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app.models.usuario import Usuario
from app.routers.auth import get_usuario_actual
from app.services.exportacion_service import exportacion_service
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/exportacion", tags=["Exportación"])


@router.get("/xlsx", summary="Exportar personas a Excel")
def exportar_xlsx(
    requiere_revision: bool = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Genera un archivo XLSX con todos los registros de personas.
    Retorna el archivo para descarga directa.
    """
    try:
        filtros = {}
        if requiere_revision is not None:
            filtros["requiere_revision"] = requiere_revision

        ruta_archivo = exportacion_service.exportar_personas(db, filtros or None)

        if not Path(ruta_archivo).exists():
            raise HTTPException(status_code=500, detail="Error generando archivo Excel")

        nombre_descarga = Path(ruta_archivo).name
        logger.info(f"Exportación XLSX descargada por {usuario.email}: {nombre_descarga}")

        return FileResponse(
            path=ruta_archivo,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=nombre_descarga,
            headers={"Content-Disposition": f"attachment; filename={nombre_descarga}"}
        )

    except Exception as e:
        logger.error(f"Error en exportación: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando exportación: {str(e)}")


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
