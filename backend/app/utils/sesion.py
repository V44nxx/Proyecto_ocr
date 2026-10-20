"""
Dónde viaja la sesión y cómo se protege.

- El navegador la lleva en una cookie HttpOnly (ningún script la puede leer), SameSite=Strict y, en producción,
  Secure con el prefijo __Host-. Otros clientes (scripts, JMeter, ZAP) pueden seguir usando Authorization: Bearer.
- CSRF: una petición que cambia datos usando la cookie debe venir del frontend. Si trae Origin, ese origen debe
  estar permitido (CORS_ORIGINS / CORS_ORIGIN_REGEX) o ser el mismo sitio que atiende la petición (proxy del frontend).
"""
from http.cookies import SimpleCookie
from typing import Optional, Tuple
from urllib.parse import urlparse

from fastapi import Request, Response

from app.config import settings
from app.utils.seguridad_http import origen_permitido

METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def poner_cookie_sesion(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.nombre_cookie_sesion,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        secure=settings.cookie_segura,
        httponly=True,
        samesite="strict",
    )


def borrar_cookie_sesion(response: Response) -> None:
    response.delete_cookie(key=settings.nombre_cookie_sesion, path="/", secure=settings.cookie_segura,
                           httponly=True, samesite="strict")


def token_de_peticion(request: Request) -> Tuple[Optional[str], bool]:
    """(token, vino_en_la_cookie). La cabecera Authorization tiene prioridad sobre la cookie."""
    cabecera = request.headers.get("authorization", "")
    if cabecera.startswith("Bearer ") and cabecera[7:].strip():
        return cabecera[7:].strip(), False
    cookie = request.cookies.get(settings.nombre_cookie_sesion)
    return (cookie, True) if cookie else (None, False)


def token_de_cabeceras_asgi(cabeceras: dict) -> Optional[str]:
    """Lo mismo para un middleware ASGI, con las cabeceras crudas (bytes)."""
    autorizacion = cabeceras.get(b"authorization", b"").decode("latin-1")
    if autorizacion.startswith("Bearer ") and autorizacion[7:].strip():
        return autorizacion[7:].strip()
    galletas = SimpleCookie()
    try:
        galletas.load(cabeceras.get(b"cookie", b"").decode("latin-1"))
    except Exception:
        return None
    m = galletas.get(settings.nombre_cookie_sesion)
    return m.value if m else None


def origen_confiable(request: Request) -> bool:
    """Para peticiones que cambian datos con la cookie: el origen es el frontend o el mismo sitio."""
    origen = request.headers.get("origin")
    if not origen:
        return True  # los navegadores mandan Origin en estas peticiones; sin él no es un navegador de otro sitio
    if origen_permitido(origen):
        return True
    host_origen = urlparse(origen).netloc.lower()
    valores = f'{request.headers.get("x-forwarded-host", "")},{request.headers.get("host", "")}'
    hosts_propios = {h.strip().lower() for h in valores.split(",") if h.strip()}
    return bool(host_origen) and host_origen in hosts_propios
