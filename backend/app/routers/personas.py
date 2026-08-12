"""
Router de Personas
Endpoints: Listar, detalle, actualizar (corrección manual), eliminar
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.persona import Persona
from app.models.usuario import Usuario
from app.schemas.documento import PersonaResponse, PersonaUpdate
from app.routers.auth import get_usuario_actual
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/personas", tags=["Personas"])


@router.get("", response_model=List[PersonaResponse], summary="Listar personas")
def listar_personas(
    skip: int = 0,
    limit: int = 100,
    requiere_revision: Optional[bool] = Query(None),
    buscar: Optional[str] = Query(None, description="Buscar por nombre, apellido o cédula"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Lista todas las personas registradas con filtros opcionales"""
    query = db.query(Persona)

    if requiere_revision is not None:
        query = query.filter(Persona.requiere_revision == requiere_revision)

    if buscar:
        buscar_upper = f"%{buscar.upper()}%"
        query = query.filter(
            Persona.numero_identificacion.ilike(f"%{buscar}%") |
            Persona.nombres.ilike(buscar_upper) |
            Persona.apellidos.ilike(buscar_upper)
        )

    personas = query.order_by(Persona.fecha_registro.desc()).offset(skip).limit(limit).all()
    return [PersonaResponse.model_validate(p) for p in personas]


@router.get("/{persona_id}", response_model=PersonaResponse, summary="Detalle de persona")
def obtener_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Obtiene el detalle completo de una persona"""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return PersonaResponse.model_validate(persona)


@router.put("/{persona_id}", response_model=PersonaResponse, summary="Corregir datos de persona")
def actualizar_persona(
    persona_id: str,
    datos: PersonaUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """
    Permite corrección manual de datos extraídos por OCR.
    Registra qué campos fueron revisados manualmente.
    """
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    campos_revisados = list(persona.campos_revisados or [])
    campos_actualizados = []

    # Actualizar solo los campos enviados
    if datos.nombres is not None:
        persona.nombres = datos.nombres.upper()
        if "nombres" not in campos_revisados:
            campos_revisados.append("nombres")
        campos_actualizados.append("nombres")

    if datos.apellidos is not None:
        persona.apellidos = datos.apellidos.upper()
        if "apellidos" not in campos_revisados:
            campos_revisados.append("apellidos")
        campos_actualizados.append("apellidos")

    if datos.fecha_nacimiento is not None:
        persona.fecha_nacimiento = datos.fecha_nacimiento
        campos_actualizados.append("fecha_nacimiento")

    if datos.fecha_expedicion is not None:
        persona.fecha_expedicion = datos.fecha_expedicion
        campos_actualizados.append("fecha_expedicion")

    if datos.lugar_expedicion is not None:
        persona.lugar_expedicion = datos.lugar_expedicion.upper()
        campos_actualizados.append("lugar_expedicion")

    if datos.sexo is not None:
        persona.sexo = datos.sexo.upper()
        campos_actualizados.append("sexo")

    if datos.requiere_revision is not None:
        persona.requiere_revision = datos.requiere_revision

    persona.campos_revisados = campos_revisados

    from datetime import datetime
    persona.fecha_actualizacion = datetime.utcnow()
    db.commit()
    db.refresh(persona)

    logger.info(f"Persona {persona.numero_identificacion} actualizada. Campos: {campos_actualizados}")
    return PersonaResponse.model_validate(persona)


@router.delete("/{persona_id}", status_code=204, summary="Eliminar persona")
def eliminar_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Elimina un registro de persona"""
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    db.delete(persona)
    db.commit()
    logger.info(f"Persona eliminada: {persona.numero_identificacion}")


@router.get("/buscar/cedula/{cedula}", response_model=PersonaResponse, summary="Buscar por cédula")
def buscar_por_cedula(
    cedula: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Busca una persona por número de identificación exacto"""
    persona = db.query(Persona).filter(
        Persona.numero_identificacion == cedula.strip()
    ).first()

    if not persona:
        raise HTTPException(status_code=404, detail=f"No se encontró persona con cédula {cedula}")

    return PersonaResponse.model_validate(persona)
