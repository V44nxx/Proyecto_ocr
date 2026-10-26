"""Schemas Pydantic: Autenticación y Usuario"""
from pydantic import AfterValidator, BaseModel, EmailStr, Field, field_validator
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
    doble_factor_activo: bool = False

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """
    Sesión iniciada (access_token y usuario) o, para un administrador, el paso siguiente: `requiere_2fa` con el
    `desafio` que se manda junto con el código (y `configurar_2fa` si todavía no tiene la app vinculada).
    """
    access_token: Optional[str] = None
    token_type: str = "bearer"
    usuario: Optional[UsuarioResponse] = None
    requiere_2fa: bool = False
    configurar_2fa: bool = False
    desafio: Optional[str] = None
    codigos_respaldo: Optional[List[str]] = None           # solo al activar: se muestran una vez
    codigos_respaldo_restantes: Optional[int] = None       # al entrar con un código de respaldo


class DesafioRequest(BaseModel):
    desafio: str = Field(max_length=2000)


class CodigoDobleFactorRequest(DesafioRequest):
    codigo: str = Field(max_length=32)


class ConfigurarDobleFactorResponse(BaseModel):
    secreto: str
    uri: str
    qr: str


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
