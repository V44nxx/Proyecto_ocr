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

# Usar passlib como motor principal (compatible con hashes de bcrypt directo Y de passlib)
try:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _PASSLIB_OK = True
except ImportError:
    _pwd_context = None
    _PASSLIB_OK = False

# bcrypt directo como fallback
try:
    import bcrypt as _bcrypt
    _BCRYPT_OK = True
except ImportError:
    _bcrypt = None
    _BCRYPT_OK = False

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import (
    LoginRequest, TokenResponse, UsuarioCreate, UsuarioResponse, TokenData
)
from app.config import settings
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login/form")


# ──────────────────────────────────────────
# UTILIDADES PASSWORD
# Motor: passlib (bcrypt) con fallback a bcrypt directo
# ──────────────────────────────────────────
def crear_hash_password(password: str) -> str:
    """Genera hash bcrypt de la contraseña usando passlib"""
    if _PASSLIB_OK:
        return _pwd_context.hash(password)
    if _BCRYPT_OK:
        return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")
    raise RuntimeError("No hay motor de hashing disponible (instala passlib o bcrypt)")


def verificar_password(password_plano: str, hash_guardado: str) -> bool:
    """Verifica contraseña con triple fallback: passlib → bcrypt directo"""
    if not password_plano or not hash_guardado:
        return False

    # Intento 1: passlib (maneja $2b$, $2a$, $2y$ y cualquier formato bcrypt)
    if _PASSLIB_OK:
        try:
            result = _pwd_context.verify(password_plano, hash_guardado)
            logger.debug(f"[Auth] Verificación passlib: {result}")
            return result
        except Exception as e:
            logger.warning(f"[Auth] passlib.verify falló: {type(e).__name__}: {e} — probando bcrypt directo")

    # Intento 2: bcrypt directo
    if _BCRYPT_OK:
        try:
            pwd_b = password_plano.encode("utf-8")
            hash_b = hash_guardado.encode("utf-8") if isinstance(hash_guardado, str) else hash_guardado
            result = _bcrypt.checkpw(pwd_b, hash_b)
            logger.debug(f"[Auth] Verificación bcrypt directo: {result}")
            return result
        except Exception as e:
            logger.error(f"[Auth] bcrypt.checkpw falló: {type(e).__name__}: {e}")

    logger.error("[Auth] Todos los métodos de verificación fallaron")
    return False


# ──────────────────────────────────────────
# UTILIDADES JWT
# ──────────────────────────────────────────
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
    email_limpio = request.email.strip().lower()
    usuario = db.query(Usuario).filter(
        Usuario.email.ilike(email_limpio),
        Usuario.activo == True
    ).first()

    if not usuario:
        logger.warning(f"Login fallido (usuario no encontrado): {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    if not verificar_password(request.password, usuario.password_hash):
        logger.warning(f"Login fallido (password inválido): {request.email}")
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
    if db.query(Usuario).filter(Usuario.email.ilike(request.email.strip())).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado"
        )

    usuario = Usuario(
        email=request.email.strip().lower(),
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


@router.get("/health", tags=["Sistema"], summary="Health check del backend")
def health_check_api(db: Session = Depends(get_db)):
    """Verificación de salud del backend, accesible via /api/auth/health"""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        db_ok = False
    return {
        "status": "ok" if db_ok else "degradado",
        "database": "conectada" if db_ok else "sin conexión",
    }
