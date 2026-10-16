"""Schemas Pydantic: Autenticación y Usuario"""
from pydantic import AfterValidator, BaseModel, EmailStr, field_validator
from typing import Annotated, Optional
from datetime import datetime
import uuid


class UsuarioBase(BaseModel):
    email: EmailStr
    nombre: Optional[str] = ""


class UsuarioCreate(UsuarioBase):
    password: str
    rol: str = "usuario"

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v

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


def _validar_password_nueva(v: str) -> str:
    if len(v) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede tener más de 72 caracteres")
    return v


PasswordNueva = Annotated[str, AfterValidator(_validar_password_nueva)]


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
