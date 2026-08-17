"""
Router de Autenticación
Endpoints: Login, Registro, Perfil
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import (
    LoginRequest, TokenResponse, UsuarioCreate, UsuarioResponse, TokenData
)
from app.config import settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ──────────────────────────────────────────
# UTILIDADES JWT
# ──────────────────────────────────────────
def crear_hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verificar_password(password_plano: str, hash_guardado: str) -> bool:
    try:
        return pwd_context.verify(password_plano, hash_guardado)
    except Exception as err:
        logger.error(f"Error verificando password: {err}")
        return False


def crear_token_acceso(data: dict) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_usuario_actual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Usuario:
    """Dependency: obtiene el usuario actual desde el JWT"""
    credenciales_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credenciales_exception
    except JWTError:
        raise credenciales_exception

    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario or not usuario.activo:
        raise credenciales_exception

    return usuario


def get_admin_actual(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
    """Dependency: requiere rol de administrador"""
    if usuario.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador"
        )
    return usuario


# ──────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────
@router.post("/login", response_model=TokenResponse, summary="Iniciar sesión")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Autenticar usuario y obtener token JWT"""
    email_limpio = request.email.strip()
    usuario = db.query(Usuario).filter(
        Usuario.email.ilike(email_limpio),
        Usuario.activo == True
    ).first()

    if not usuario or not verificar_password(request.password, usuario.password_hash):
        logger.warning(f"Intento de login fallido: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    # Actualizar último login
    usuario.ultimo_login = datetime.utcnow()
    db.commit()

    token = crear_token_acceso({"sub": str(usuario.id), "email": usuario.email})
    logger.info(f"Login exitoso: {usuario.email}")

    return TokenResponse(
        access_token=token,
        usuario=UsuarioResponse.model_validate(usuario)
    )


@router.post("/login/form", summary="Login formato form (OAuth2)")
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login compatible con OAuth2 (para Swagger UI)"""
    request = LoginRequest(email=form_data.username, password=form_data.password)
    resultado = login(request, db)
    return {"access_token": resultado.access_token, "token_type": "bearer"}


@router.post("/register", response_model=UsuarioResponse, status_code=201, summary="Registrar usuario")
def registrar(request: UsuarioCreate, db: Session = Depends(get_db)):
    """Registrar nuevo usuario en el sistema"""
    # Verificar email único
    if db.query(Usuario).filter(Usuario.email == request.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado"
        )

    usuario = Usuario(
        email=request.email,
        nombre=request.nombre,
        password_hash=crear_hash_password(request.password),
        rol=request.rol,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    logger.info(f"Usuario registrado: {usuario.email}")

    return UsuarioResponse.model_validate(usuario)


@router.get("/me", response_model=UsuarioResponse, summary="Perfil actual")
def perfil_actual(usuario: Usuario = Depends(get_usuario_actual)):
    """Obtener información del usuario autenticado"""
    return UsuarioResponse.model_validate(usuario)
