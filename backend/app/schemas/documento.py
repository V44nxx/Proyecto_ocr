"""Schemas Pydantic: Documento y Persona"""
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
import uuid


# ──────────────────────────────────────────
# Documento Schemas
# ──────────────────────────────────────────
class DocumentoResponse(BaseModel):
    id: uuid.UUID
    nombre_original: str
    estado: str
    total_paginas: int
    confianza_ocr: Optional[Decimal]
    mensaje_error: Optional[str]
    tiempo_procesamiento_ms: Optional[int]
    fecha_carga: datetime
    fecha_procesamiento: Optional[datetime]

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Persona Schemas
# ──────────────────────────────────────────
class PersonaBase(BaseModel):
    numero_identificacion: str
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    fecha_expedicion: Optional[date] = None
    lugar_expedicion: Optional[str] = None
    sexo: Optional[str] = None


class PersonaCreate(PersonaBase):
    documento_id: Optional[uuid.UUID] = None
    confianza_extraccion: Optional[Decimal] = None
    requiere_revision: bool = False
    texto_ocr_crudo: Optional[str] = None

    @field_validator("numero_identificacion")
    @classmethod
    def validar_identificacion(cls, v):
        """
        Valida cédula colombiana: solo dígitos, longitud 6-10.
        FIX: el rango anterior era 6-12. Colombia tiene máximo 10 dígitos
        en cédulas actuales. 11-12 dígitos son concatenaciones por error OCR.
        """
        v = str(v).strip().replace(" ", "").replace(".", "").replace(",", "")
        if not v.isdigit():
            raise ValueError(
                f"El número de identificación debe contener solo dígitos. "
                f"Recibido: '{v}'"
            )
        if len(v) < 6 or len(v) > 10:
            raise ValueError(
                f"Cédula colombiana debe tener 6-10 dígitos. "
                f"Recibido: {len(v)} dígitos ('{v}')"
            )
        return v

    @field_validator("sexo")
    @classmethod
    def normalizar_sexo(cls, v):
        if v is None:
            return v
        v = v.upper().strip()
        if v in ["M", "MASCULINO", "HOMBRE", "MALE"]:
            return "M"
        if v in ["F", "FEMENINO", "MUJER", "FEMALE"]:
            return "F"
        return None


class PersonaUpdate(BaseModel):
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    fecha_expedicion: Optional[date] = None
    lugar_expedicion: Optional[str] = None
    sexo: Optional[str] = None
    requiere_revision: Optional[bool] = None


class PersonaResponse(PersonaBase):
    id: uuid.UUID
    documento_id: Optional[uuid.UUID]
    pagina_numero: Optional[int] = None
    tipo_documento: Optional[str] = "CEDULA_CIUDADANIA"
    estado_registro: Optional[str] = "VALID"
    motor_ocr: Optional[str] = "google_document_ai"
    confianza_extraccion: Optional[Decimal]
    requiere_revision: bool
    detalles_campos: Optional[dict] = None
    fecha_registro: datetime
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Resultado OCR
# ──────────────────────────────────────────
class ResultadoOCR(BaseModel):
    """Resultado del procesamiento OCR de un documento"""
    documento_id: uuid.UUID
    estado: str
    total_paginas: int
    confianza_promedio: float
    personas_extraidas: List[PersonaResponse]
    tiempo_procesamiento_ms: int
    requieren_revision: int
    errores: List[str] = []
