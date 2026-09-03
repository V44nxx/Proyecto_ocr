"""Schemas Pydantic: Comparación y Diferencias"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid


class ComparacionResponse(BaseModel):
    id: uuid.UUID
    nombre_original: str
    nombre_archivo: Optional[str] = None
    ruta_archivo: Optional[str] = None
    archivo_existe: Optional[bool] = None
    archivos_en_uploads: Optional[List[str]] = None
    error_carga_excel: Optional[str] = None
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
