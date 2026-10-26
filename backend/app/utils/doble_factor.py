"""
Verificación en dos pasos (TOTP, RFC 6238): obligatoria para los administradores.

- El secreto se guarda cifrado (Fernet) con una clave derivada de SECRET_KEY: una copia de la base sola no basta.
  Cambiar SECRET_KEY deja inservibles los secretos guardados: cada administrador entra con un código de respaldo,
  otro administrador se la restablece, o en el servidor `python -m app.restablecer_doble_factor <correo>`.
- Un código de la app sirve una sola vez: se guarda el último paso de 30 segundos usado.
- Los códigos de respaldo se guardan como hash SHA-256 (cada uno tiene 50 bits al azar) y sirven una vez.
- El desafío prueba que la contraseña ya se verificó. Es un JWT corto firmado con otra clave y con otra audiencia,
  así que nunca sirve como sesión.
"""
import base64
import hashlib
import hmac
import secrets
import time
from typing import List, Optional, Tuple

import jwt
import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings

EMISOR = "KondID"
DESAFIO_MINUTOS = 10          # alcanza para instalar la app y escanear el QR
_AUDIENCIA_DESAFIO = "kondid-2fa"
_PASO = 30                    # segundos de cada código
_DESFASE = 1                  # se acepta el código anterior y el siguiente (relojes un poco corridos)
_ALFABETO_RESPALDO = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"   # sin 0/O ni 1/I/L, que se confunden
CODIGOS_RESPALDO = 10


def requiere_doble_factor(usuario) -> bool:
    return getattr(usuario, "rol", None) == "admin" or bool(getattr(usuario, "totp_activo", False))


def _clave_derivada(uso: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=uso).derive(settings.SECRET_KEY.encode("utf-8"))


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_clave_derivada(b"kondid-totp-secreto")))


def generar_secreto() -> str:
    return pyotp.random_base32()


def cifrar_secreto(secreto: str) -> str:
    return _fernet().encrypt(secreto.encode("ascii")).decode("ascii")


def descifrar_secreto(cifrado: Optional[str]) -> Optional[str]:
    if not cifrado:
        return None
    try:
        return _fernet().decrypt(cifrado.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError):
        return None


AVISO_SECRETO_ILEGIBLE = (
    "no se puede leer el secreto guardado de su app de autenticación: casi seguro cambió SECRET_KEY "
    "(o el servidor está usando una temporal). Ningún código de la app le va a servir. Restablécela desde "
    "Usuarios o con `python -m app.restablecer_doble_factor <correo>`, y deja SECRET_KEY fija."
)


def secreto_ilegible(usuario) -> bool:
    return bool(usuario.totp_activo and usuario.totp_secreto) and descifrar_secreto(usuario.totp_secreto) is None


def avisar_secretos_ilegibles(db) -> List[str]:
    """Al arrancar: correos de las cuentas con la verificación activa cuyo secreto ya no se puede descifrar."""
    from app.models.usuario import Usuario
    from app.utils.logger import app_logger as logger
    afectados = sorted(u.email for u in db.query(Usuario).filter(Usuario.totp_activo == True).all()
                       if secreto_ilegible(u))
    if afectados:
        logger.error(f"Verificación en dos pasos de {', '.join(afectados)}: {AVISO_SECRETO_ILEGIBLE}")
    return afectados


def uri_aprovisionamiento(secreto: str, email: str) -> str:
    return pyotp.TOTP(secreto).provisioning_uri(name=email, issuer_name=EMISOR)


def qr_svg(uri: str) -> str:
    """QR del enlace otpauth:// como imagen SVG embebida (data:), oscuro sobre blanco para que la cámara lo lea."""
    return segno.make(uri, error="m").svg_data_uri(scale=5, border=2, dark="#111827", light="#ffffff")


def paso_valido(secreto: str, codigo: str, ultimo_paso: Optional[int], ahora: Optional[float] = None) -> Optional[int]:
    """Paso de 30 s al que corresponde el código, o None si no vale (equivocado, vencido o ya usado)."""
    codigo = (codigo or "").replace(" ", "")
    if len(codigo) != 6 or not codigo.isdigit():
        return None
    totp = pyotp.TOTP(secreto)
    actual = int((time.time() if ahora is None else ahora) // _PASO)
    for paso in range(actual - _DESFASE, actual + _DESFASE + 1):
        if hmac.compare_digest(totp.at(paso * _PASO), codigo):
            return paso if ultimo_paso is None or paso > ultimo_paso else None
    return None


def _normalizar_respaldo(codigo: str) -> str:
    return "".join(c for c in (codigo or "").upper() if c.isalnum())


def _hash_respaldo(codigo: str) -> str:
    return hashlib.sha256(_normalizar_respaldo(codigo).encode("ascii", "ignore")).hexdigest()


def generar_codigos_respaldo() -> Tuple[List[str], List[str]]:
    """(códigos para mostrar una vez, hashes para guardar). Formato XXXXX-XXXXX."""
    planos = set()
    while len(planos) < CODIGOS_RESPALDO:
        crudo = "".join(secrets.choice(_ALFABETO_RESPALDO) for _ in range(10))
        planos.add(f"{crudo[:5]}-{crudo[5:]}")
    planos = sorted(planos)
    return planos, [_hash_respaldo(c) for c in planos]


def usar_codigo_respaldo(hashes: Optional[List[str]], codigo: str) -> Optional[List[str]]:
    """Los hashes que quedan si el código es uno de ellos; None si no lo es."""
    if not hashes or len(_normalizar_respaldo(codigo)) != 10:
        return None
    buscado = _hash_respaldo(codigo)
    for guardado in hashes:
        if hmac.compare_digest(guardado, buscado):
            return [h for h in hashes if h != guardado]
    return None


def crear_desafio(usuario, configurar: bool, ahora: Optional[float] = None) -> str:
    emitido = int(time.time() if ahora is None else ahora)
    payload = {
        "sub": str(usuario.id),
        "ver": int(usuario.version_sesion or 0),
        "cfg": bool(configurar),
        "aud": _AUDIENCIA_DESAFIO,
        "iat": emitido,
        "exp": emitido + DESAFIO_MINUTOS * 60,
    }
    return jwt.encode(payload, _clave_derivada(b"kondid-desafio-2fa"), algorithm="HS256")


def leer_desafio(token: Optional[str]) -> Optional[dict]:
    try:
        return jwt.decode(token or "", _clave_derivada(b"kondid-desafio-2fa"), algorithms=["HS256"],
                          audience=_AUDIENCIA_DESAFIO)
    except jwt.InvalidTokenError:
        return None
