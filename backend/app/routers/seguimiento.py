"""
Seguimiento de fichas: cada usuario guarda el enlace de su panel de Google Apps Script
(y opcionalmente su correo de Google y la hoja de cálculo) para verlo dentro de KondID.
"""
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.database import get_db
from app.models.seguimiento_config import SeguimientoConfig
from app.models.usuario import Usuario
from app.routers.auth import get_usuario_actual
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/seguimiento", tags=["Seguimiento de fichas"])


def _validar_url(valor: str, host: str, prefijos: tuple, mensaje: str) -> str:
    url = (valor or "").strip()
    partes = urlparse(url)
    if partes.scheme != "https" or partes.hostname != host or not partes.path.startswith(prefijos):
        raise ValueError(mensaje)
    return url


class SeguimientoConfigRequest(BaseModel):
    url_panel: str
    correo_google: Optional[EmailStr] = None
    url_hoja: Optional[str] = None

    @field_validator("correo_google", "url_hoja", mode="before")
    @classmethod
    def vacio_a_none(cls, v):
        return v.strip() or None if isinstance(v, str) else v

    @field_validator("url_panel")
    @classmethod
    def validar_panel(cls, v: str) -> str:
        # Aplicación web de Apps Script: .../macros/s/ID/exec o .../a/macros/dominio/s/ID/exec
        return _validar_url(
            v, "script.google.com", ("/macros/s/", "/a/macros/"),
            "El enlace del panel debe ser la URL de la aplicación web de Apps Script "
            "(https://script.google.com/macros/s/.../exec)",
        )

    @field_validator("url_hoja")
    @classmethod
    def validar_hoja(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _validar_url(
            v, "docs.google.com", ("/spreadsheets/",),
            "El enlace de la hoja debe ser de Google Sheets (https://docs.google.com/spreadsheets/...)",
        )


class SeguimientoConfigResponse(BaseModel):
    url_panel: str
    correo_google: Optional[str] = None
    url_hoja: Optional[str] = None
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True


def _config_de(db: Session, usuario: Usuario) -> Optional[SeguimientoConfig]:
    return db.query(SeguimientoConfig).filter(SeguimientoConfig.usuario_id == usuario.id).first()


@router.get("/config", response_model=Optional[SeguimientoConfigResponse])
def obtener_config(usuario: Usuario = Depends(get_usuario_actual), db: Session = Depends(get_db)):
    """Configuración del usuario actual, o null si aún no la ha guardado"""
    return _config_de(db, usuario)


@router.put("/config", response_model=SeguimientoConfigResponse)
def guardar_config(
    request: SeguimientoConfigRequest,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    # Otra petición del mismo usuario puede borrar o crear la fila entre la lectura y el commit
    # (StaleDataError / IntegrityError): se deshace y se repite una vez con lo que haya en ese momento
    for intento in range(2):
        config = _config_de(db, usuario)
        if config is None:
            config = SeguimientoConfig(usuario_id=usuario.id)
            db.add(config)
        config.url_panel = request.url_panel
        config.correo_google = request.correo_google
        config.url_hoja = request.url_hoja
        try:
            db.commit()
            break
        except (StaleDataError, IntegrityError):
            db.rollback()
            if intento:
                raise
    db.refresh(config)
    logger.info(f"Seguimiento de fichas configurado por {usuario.email}")
    return config


@router.delete("/config")
def eliminar_config(usuario: Usuario = Depends(get_usuario_actual), db: Session = Depends(get_db)):
    config = _config_de(db, usuario)
    if config is None:
        raise HTTPException(status_code=404, detail="No hay configuración guardada")
    db.delete(config)
    db.commit()
    return {"message": "Configuración eliminada"}
