"""
Registro de auditoría: quién hizo qué, cuándo y desde dónde.

Se escribe en una sesión de base de datos propia, para que los intentos fallidos (que no hacen commit)
también queden registrados y para que un fallo al auditar nunca tumbe la acción del usuario.
Nunca guarda contraseñas ni tokens; las rutas pasan solo ids, conteos y nombres de campos, no cédulas ni nombres.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request

from app import database
from app.utils.limitador import ip_cliente
from app.utils.logger import app_logger as logger

# Claves que no se guardan aunque una ruta las pase por error
_CLAVES_PROHIBIDAS = {"password", "password_actual", "password_nueva", "contrasena", "clave", "token", "access_token"}


def _guardar_en_base(registro: dict) -> None:
    from app.models.auditoria import RegistroAuditoria
    db = database.SessionLocal()
    try:
        db.add(RegistroAuditoria(**registro))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"No se pudo guardar el registro de auditoría '{registro.get('accion')}': {type(e).__name__}")
    finally:
        db.close()


# Las pruebas sin base de datos lo reemplazan por una lista (ver tests/conftest.py)
_guardar = _guardar_en_base


def registrar(accion: str, request: Optional[Request] = None, usuario=None, email: Optional[str] = None,
              **detalle) -> None:
    """Registra una acción. Llamarlo después del commit de la acción, nunca antes."""
    try:
        datos = {k: v for k, v in detalle.items() if v is not None and k.lower() not in _CLAVES_PROHIBIDAS}
        correo = email or getattr(usuario, "email", None)
        registro = {
            "fecha": datetime.now(timezone.utc),
            "accion": accion,
            "usuario_id": getattr(usuario, "id", None),
            "email": correo[:255] if correo else None,
            "ip": ip_cliente(request)[:64] if request is not None else None,
            "detalle": datos or None,
        }
    except Exception as e:
        logger.warning(f"No se pudo armar el registro de auditoría '{accion}': {type(e).__name__}")
        return
    _guardar(registro)
