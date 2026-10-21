"""Schemas Pydantic: Comparación y Diferencias"""
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
import uuid

from app.utils.errores import mensaje_error_visible

ERROR_COMPARACION = "No se pudo completar la comparación. Usa «Reintentar» o vuelve a subir la planilla."


class ComparacionResponse(BaseModel):
    id: uuid.UUID
    nombre_original: str
    nombre_archivo: Optional[str] = None
    estado: str
    total_registros_bd: int
    total_registros_excel: int
    total_coincidentes: int
    total_diferentes: int
    total_faltantes_bd: int
    total_nuevos_bd: int
    fecha_carga: datetime
    fecha_ejecucion: Optional[datetime]
    tiempo_procesamiento_ms: Optional[int]
    mensaje_error: Optional[str] = None

    @field_validator("mensaje_error")
    @classmethod
    def sin_detalles_internos(cls, v: Optional[str]) -> Optional[str]:
        return mensaje_error_visible(v, ERROR_COMPARACION)

    class Config:
        from_attributes = True


class DiferenciaResponse(BaseModel):
    id: uuid.UUID
    numero_identificacion: str
    campo: Optional[str]
    valor_bd: Optional[str]
    valor_excel: Optional[str]
    tipo_diferencia: str

    class Config:
        from_attributes = True


class ReporteComparacion(BaseModel):
    comparacion: ComparacionResponse
    diferencias: List[DiferenciaResponse]
    resumen: dict
