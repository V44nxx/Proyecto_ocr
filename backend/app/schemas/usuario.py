"""Schemas Pydantic: Autenticación y Usuario"""
from pydantic import AfterValidator, BaseModel, EmailStr, field_validator
from typing import Annotated, List, Optional
from datetime import datetime
import uuid

from app.utils.contrasenas import validar_contrasena

# Toda contraseña que se define (crear usuario, cambiarla o restablecerla) pasa por la misma política
PasswordNueva = Annotated[str, AfterValidator(validar_contrasena)]


class UsuarioBase(BaseModel):
    email: EmailStr
    nombre: Optional[str] = ""


class UsuarioCreate(UsuarioBase):
    password: PasswordNueva
    rol: str = "usuario"

    @field_validator("rol")
    @classmethod
    def rol_valido(cls, v):
        if v not in ["admin", "usuario"]:
            raise ValueError("Rol debe ser 'admin' o 'usuario'")
        return v


class UsuarioResponse(UsuarioBase):
    id: uuid.UUID
    rol: str
    activo: bool
    fecha_creacion: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str



class OlvidePasswordRequest(BaseModel):
    email: EmailStr


class RestablecerPasswordRequest(BaseModel):
    token: str
    password_nueva: PasswordNueva


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nueva: PasswordNueva


class RestablecerPasswordAdminRequest(BaseModel):
    password_nueva: PasswordNueva


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None


class RegistroAuditoriaResponse(BaseModel):
    fecha: datetime
    email: Optional[str] = None
    accion: str
    ip: Optional[str] = None
    detalle: Optional[dict] = None

    class Config:
        from_attributes = True


class RegistrosAuditoriaResponse(BaseModel):
    total: int
    registros: List[RegistroAuditoriaResponse]
