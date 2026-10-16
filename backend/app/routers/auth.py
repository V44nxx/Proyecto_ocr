"""
Router de Autenticación
Endpoints: Login, Registro, Perfil
"""
import hashlib
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import func
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
    LoginRequest, TokenResponse, UsuarioCreate, UsuarioResponse, TokenData,
    OlvidePasswordRequest, RestablecerPasswordRequest, CambiarPasswordRequest, RestablecerPasswordAdminRequest,
)
from app.config import settings
from app.utils.limitador import Limitador, ip_cliente, mensaje_espera
from app.utils.logger import app_logger as logger

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Límites de intentos (ventanas de 15 minutos)
VENTANA_INTENTOS = 15 * 60
limite_login_correo = Limitador(5, VENTANA_INTENTOS)        # fallos por correo
limite_login_ip = Limitador(20, VENTANA_INTENTOS)           # fallos por IP, con cualquier correo
limite_cambio_password = Limitador(5, VENTANA_INTENTOS)     # contraseña actual equivocada, por usuario
limite_recuperacion_ip = Limitador(5, VENTANA_INTENTOS)     # pedidos de enlace de recuperación por IP
limite_restablecer_ip = Limitador(10, VENTANA_INTENTOS)     # enlaces inválidos por IP


# ──────────────────────────────────────────
# UTILIDADES PASSWORD
# Motor: passlib (bcrypt) con fallback a bcrypt directo
# ──────────────────────────────────────────
def crear_hash_password(password: str) -> str:
    """Genera hash bcrypt de la contraseña usando bcrypt directo"""
    pwd_bytes = password.encode("utf-8")[:72]
    if _BCRYPT_OK:
        return _bcrypt.hashpw(pwd_bytes, _bcrypt.gensalt(rounds=12)).decode("utf-8")
    if _PASSLIB_OK:
        return _pwd_context.hash(password)
    raise RuntimeError("No hay motor de hashing disponible (instala passlib o bcrypt)")


def verificar_password(password_plano: str, hash_guardado: str) -> bool:
    """Verifica contraseña con triple fallback: bcrypt directo → passlib"""
    if not password_plano or not hash_guardado:
        return False

    pwd_bytes = password_plano.encode("utf-8")[:72]

    # Intento 1: bcrypt directo
    if _BCRYPT_OK:
        try:
            hash_b = hash_guardado.encode("utf-8") if isinstance(hash_guardado, str) else hash_guardado
            result = _bcrypt.checkpw(pwd_bytes, hash_b)
            logger.debug(f"[Auth] Verificación bcrypt directo: {result}")
            return result
        except Exception as e:
            logger.warning(f"[Auth] bcrypt.checkpw falló: {e} — probando passlib")

    # Intento 2: passlib (maneja $2b$, $2a$, $2y$ y cualquier formato bcrypt)
    if _PASSLIB_OK:
        try:
            result = _pwd_context.verify(password_plano, hash_guardado)
            logger.debug(f"[Auth] Verificación passlib: {result}")
            return result
        except Exception as e:
            logger.warning(f"[Auth] passlib.verify falló: {type(e).__name__}: {e}")

    logger.error("[Auth] Todos los métodos de verificación fallaron")
    return False


# ──────────────────────────────────────────
# UTILIDADES JWT
# ──────────────────────────────────────────
def crear_token_acceso(data: dict) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire, "iat": int(time.time())})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _token_vigente(payload: dict, usuario: Usuario) -> bool:
    """Un cambio de contraseña sube la versión de sesión e invalida los tokens con la versión anterior."""
    try:
        version_token = int(payload.get("ver") or 0)
    except (TypeError, ValueError):
        return False
    return version_token == int(usuario.version_sesion or 0)


def _establecer_password(usuario: Usuario, password_nueva: str) -> None:
    """Guarda la contraseña nueva, cierra las sesiones anteriores y anula cualquier enlace de recuperación."""
    usuario.password_hash = crear_hash_password(password_nueva)
    usuario.password_cambiada_en = datetime.now(timezone.utc)
    usuario.version_sesion = (usuario.version_sesion or 0) + 1
    usuario.reset_token_hash = None
    usuario.reset_token_expira = None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
    if not usuario or not usuario.activo or not _token_vigente(payload, usuario):
        raise credenciales_exception

    return usuario


def get_usuario_desde_token_o_query(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Dependency especial: acepta JWT tanto del header 'Authorization: Bearer ...'
    como del query param '?token=...' (necesario para usar en <img src> del frontend).
    """
    credenciales_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    raw_token: Optional[str] = None

    # 1. Intentar leer desde header Authorization
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_token = auth_header[7:]

    # 2. Fallback: query param ?token=
    if not raw_token:
        raw_token = request.query_params.get("token")

    if not raw_token:
        raise credenciales_exception

    try:
        payload = jwt.decode(raw_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credenciales_exception
    except JWTError:
        raise credenciales_exception

    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario or not usuario.activo or not _token_vigente(payload, usuario):
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
_HASH_SENUELO: Optional[str] = None


def _hash_senuelo() -> str:
    """Hash de una clave al azar: se verifica contra él cuando el correo no existe, para que tarde lo mismo."""
    global _HASH_SENUELO
    if _HASH_SENUELO is None:
        _HASH_SENUELO = crear_hash_password(secrets.token_urlsafe(16))
    return _HASH_SENUELO


def _demasiados_intentos(segundos: int, motivo: str = "Demasiados intentos fallidos") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=mensaje_espera(segundos, motivo),
        headers={"Retry-After": str(segundos)},
    )


@router.post("/login", response_model=TokenResponse, summary="Iniciar sesión")
def login(request: LoginRequest, http: Request, db: Session = Depends(get_db)):
    """
    Autenticar usuario y obtener token JWT.
    El correo se compara exacto (sin comodines). Tras 5 fallos en 15 minutos con un correo, o 20 desde
    una IP, responde 429 hasta que pase la ventana, exista o no la cuenta.
    """
    email_limpio = request.email.strip().lower()
    ip = ip_cliente(http)
    espera = max(limite_login_correo.espera(email_limpio), limite_login_ip.espera(ip))
    if espera:
        logger.warning(f"Login bloqueado por demasiados intentos: {email_limpio} desde {ip}")
        raise _demasiados_intentos(espera)

    usuario = db.query(Usuario).filter(
        func.lower(Usuario.email) == email_limpio,
        Usuario.activo == True
    ).first()

    # Con un correo que no existe también se verifica una contraseña, para que la respuesta tarde lo mismo
    clave_valida = verificar_password(request.password, usuario.password_hash if usuario else _hash_senuelo())
    if not usuario or not clave_valida:
        limite_login_correo.registrar(email_limpio)
        limite_login_ip.registrar(ip)
        logger.warning(f"Login fallido para {email_limpio} desde {ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )
    limite_login_correo.reiniciar(email_limpio)

    # Actualizar último login
    usuario.ultimo_login = datetime.utcnow()
    db.commit()

    token = crear_token_acceso({"sub": str(usuario.id), "email": usuario.email, "ver": usuario.version_sesion or 0})
    logger.info(f"Login exitoso: {usuario.email}")

    return TokenResponse(
        access_token=token,
        usuario=UsuarioResponse.model_validate(usuario)
    )


@router.post("/register", response_model=UsuarioResponse, status_code=201, summary="Registrar usuario")
def registrar(
    request: UsuarioCreate,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_admin_actual),
):
    """Registrar nuevo usuario en el sistema (solo admin)"""
    if db.query(Usuario).filter(func.lower(Usuario.email) == request.email.strip().lower()).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado"
        )

    nombre_final = (
        request.nombre.strip()
        if request.nombre and request.nombre.strip()
        else request.email.split("@")[0].replace(".", " ").title()
    )

    usuario = Usuario(
        email=request.email.strip().lower(),
        nombre=nombre_final,
        password_hash=crear_hash_password(request.password),
        rol=request.rol,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    logger.info(f"Usuario registrado: {usuario.email}")

    return UsuarioResponse.model_validate(usuario)


@router.get("/users", response_model=List[UsuarioResponse], summary="Listar usuarios")
def listar_usuarios(
    usuario_actual: Usuario = Depends(get_admin_actual),
    db: Session = Depends(get_db)
):
    """Listar todos los usuarios registrados (solo admin)"""
    return db.query(Usuario).order_by(Usuario.fecha_creacion.desc()).all()


@router.delete("/users/{user_id}", summary="Eliminar usuario")
def eliminar_usuario(
    user_id: str,
    usuario_actual: Usuario = Depends(get_admin_actual),
    db: Session = Depends(get_db)
):
    """
    Eliminar usuario por ID (solo admin).
    Se eliminan también sus fichas, personas y comparaciones, con sus archivos en disco,
    para que sus datos no queden sin dueño ni pasen a otra cuenta.
    """
    import uuid as uuid_pkg
    from pathlib import Path
    from app.models.comparacion import Comparacion
    from app.models.documento import Documento
    from app.models.persona import Persona

    if str(usuario_actual.id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propia cuenta de usuario"
        )
    try:
        uid = uuid_pkg.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    u = db.query(Usuario).filter(Usuario.id == uid).first()
    if not u:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    email_eliminado = u.email
    docs = db.query(Documento.id, Documento.ruta_archivo).filter(Documento.usuario_id == uid).all()
    comps = db.query(Comparacion.ruta_archivo).filter(Comparacion.usuario_id == uid).all()
    doc_ids = [d.id for d in docs]

    personas_eliminadas = db.query(Persona).filter(Persona.usuario_id == uid).delete(synchronize_session=False)
    if doc_ids:
        personas_eliminadas += db.query(Persona).filter(Persona.documento_id.in_(doc_ids)).delete(synchronize_session=False)
    fichas_eliminadas = db.query(Documento).filter(Documento.usuario_id == uid).delete(synchronize_session=False)
    db.query(Comparacion).filter(Comparacion.usuario_id == uid).delete(synchronize_session=False)
    db.delete(u)
    db.commit()

    # Archivos en disco (PDF, planillas y vistas previas en caché)
    rutas = [d.ruta_archivo for d in docs] + [c.ruta_archivo for c in comps]
    cache_dir = settings.upload_path / "cache_previews"
    for doc_id in doc_ids:
        rutas.extend(str(p) for p in cache_dir.glob(f"{doc_id}_p*.*"))
    for ruta in rutas:
        try:
            if ruta and Path(ruta).is_file():
                Path(ruta).unlink()
        except Exception as e:
            logger.warning(f"No se pudo borrar el archivo {ruta} del usuario eliminado: {e}")

    logger.info(
        f"Usuario {email_eliminado} eliminado junto con {fichas_eliminadas} ficha(s) y {personas_eliminadas} persona(s)"
    )
    return {
        "message": "Usuario eliminado exitosamente",
        "fichas_eliminadas": fichas_eliminadas,
        "personas_eliminadas": personas_eliminadas,
    }


@router.post("/users/{user_id}/password", summary="Restablecer la contraseña de un usuario (solo admin)")
def restablecer_password_usuario(
    user_id: str,
    request: RestablecerPasswordAdminRequest,
    usuario_actual: Usuario = Depends(get_admin_actual),
    db: Session = Depends(get_db),
):
    """El administrador asigna una contraseña nueva a otro usuario; sus sesiones abiertas se cierran."""
    if str(usuario_actual.id) == user_id:
        raise HTTPException(status_code=400, detail="Para tu propia cuenta usa «Cambiar contraseña».")
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    u = db.query(Usuario).filter(Usuario.id == uid).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    _establecer_password(u, request.password_nueva)
    db.commit()
    logger.info(f"Contraseña de {u.email} restablecida por el administrador {usuario_actual.email}")
    return {"message": f"Contraseña de {u.email} restablecida. Sus sesiones abiertas se cerraron."}


@router.post("/cambiar-password", response_model=TokenResponse, summary="Cambiar la contraseña propia")
def cambiar_password(
    request: CambiarPasswordRequest,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """
    Cambia la contraseña del usuario actual. Cierra las demás sesiones y devuelve un token nuevo
    para que esta siga abierta. Una contraseña actual incorrecta responde 400 (no 401, que cerraría la sesión).
    """
    clave_usuario = str(usuario.id)
    espera = limite_cambio_password.espera(clave_usuario)
    if espera:
        raise _demasiados_intentos(espera)
    if not verificar_password(request.password_actual, usuario.password_hash):
        limite_cambio_password.registrar(clave_usuario)
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")
    limite_cambio_password.reiniciar(clave_usuario)
    if request.password_nueva == request.password_actual:
        raise HTTPException(status_code=400, detail="La contraseña nueva debe ser distinta de la actual.")
    _establecer_password(usuario, request.password_nueva)
    db.commit()
    db.refresh(usuario)
    logger.info(f"Contraseña cambiada por el propio usuario: {usuario.email}")
    token = crear_token_acceso({"sub": str(usuario.id), "email": usuario.email, "ver": usuario.version_sesion})
    return TokenResponse(access_token=token, usuario=UsuarioResponse.model_validate(usuario))


MENSAJE_OLVIDE = (
    "Si el correo está registrado, te enviamos un enlace para restablecer la contraseña. "
    "Revisa también la carpeta de spam."
)


@router.post("/olvide-password", summary="Pedir un enlace para restablecer la contraseña")
def olvide_password(
    request: OlvidePasswordRequest,
    background_tasks: BackgroundTasks,
    http: Request,
    db: Session = Depends(get_db),
):
    """
    Envía por correo un enlace de un solo uso que vence en RECUPERACION_MINUTOS.
    La respuesta es la misma exista o no el correo, y se envía como máximo un correo cada 2 minutos por cuenta.
    Desde una misma IP se aceptan 5 pedidos cada 15 minutos.
    """
    from app.services.correo_service import correo_configurado, enviar_correo_recuperacion

    base_frontend = settings.FRONTEND_URL.rstrip("/")
    if settings.ENVIRONMENT == "production" and ("localhost" in base_frontend or "127.0.0.1" in base_frontend):
        # Sin FRONTEND_URL los enlaces del correo apuntarían a localhost y no abrirían
        logger.error("Recuperación por correo desactivada: falta FRONTEND_URL con la dirección pública del frontend")
        base_frontend = ""
    if not correo_configurado() or not base_frontend:
        raise HTTPException(
            status_code=503,
            detail="La recuperación por correo todavía no está configurada. Pide al administrador que restablezca tu contraseña.",
        )

    ip = ip_cliente(http)
    espera = limite_recuperacion_ip.espera(ip)
    if espera:
        raise _demasiados_intentos(espera, "Demasiadas solicitudes de recuperación")
    limite_recuperacion_ip.registrar(ip)

    email = request.email.strip().lower()
    usuario = db.query(Usuario).filter(func.lower(Usuario.email) == email, Usuario.activo == True).first()
    if usuario:
        ahora = datetime.now(timezone.utc)
        minutos = settings.RECUPERACION_MINUTOS
        pedido_en = usuario.reset_token_expira - timedelta(minutes=minutos) if usuario.reset_token_expira else None
        if pedido_en and pedido_en > ahora - timedelta(minutes=2):
            logger.info(f"Recuperación de contraseña repetida en menos de 2 minutos para {usuario.email}; no se reenvía")
        else:
            token = secrets.token_urlsafe(32)
            usuario.reset_token_hash = _hash_token(token)
            usuario.reset_token_expira = ahora + timedelta(minutes=minutos)
            db.commit()
            enlace = f"{base_frontend}/restablecer-contrasena?token={token}"
            background_tasks.add_task(enviar_correo_recuperacion, usuario.email, usuario.nombre, enlace, minutos)
            logger.info(f"Recuperación de contraseña solicitada para {usuario.email}")
    return {"message": MENSAJE_OLVIDE}


@router.post("/restablecer-password", summary="Elegir una contraseña nueva con el enlace del correo")
def restablecer_password(request: RestablecerPasswordRequest, http: Request, db: Session = Depends(get_db)):
    ip = ip_cliente(http)
    espera = limite_restablecer_ip.espera(ip)
    if espera:
        raise _demasiados_intentos(espera)
    token = (request.token or "").strip()
    usuario = db.query(Usuario).filter(Usuario.reset_token_hash == _hash_token(token)).first() if token else None
    if (
        not usuario
        or not usuario.activo
        or not usuario.reset_token_expira
        or usuario.reset_token_expira < datetime.now(timezone.utc)
    ):
        limite_restablecer_ip.registrar(ip)
        raise HTTPException(
            status_code=400,
            detail="El enlace no es válido o ya venció. Pide uno nuevo desde «¿Olvidaste tu contraseña?».",
        )
    _establecer_password(usuario, request.password_nueva)
    db.commit()
    logger.info(f"Contraseña restablecida con el enlace del correo: {usuario.email}")
    return {"message": "Tu contraseña se cambió. Ya puedes iniciar sesión con la nueva."}


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
