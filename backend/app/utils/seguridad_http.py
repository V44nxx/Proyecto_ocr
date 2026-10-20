"""
Cabeceras de seguridad y reglas de CORS de la API.

- Cada respuesta lleva cabeceras que impiden incrustar la API en otra página, adivinar tipos de
  contenido o filtrar la dirección de origen; en producción también HSTS.
- Las respuestas de /api/ no se guardan en ninguna caché salvo que la ruta diga otra cosa: casi todas
  llevan datos personales.
- CORS: solo los orígenes del frontend configurados (lista exacta o expresión regular completa).
"""
import re
from typing import Dict, Optional

from app.config import settings

# La API solo devuelve JSON, imágenes y archivos: no necesita cargar nada ni dejarse incrustar
CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
# La documentación interactiva (fuera de producción) carga Swagger UI desde un CDN
RUTAS_DOCUMENTACION = ("/docs", "/redoc")


def origen_permitido(origen: Optional[str]) -> bool:
    if not origen:
        return False
    if origen in settings.CORS_ORIGINS:
        return True
    return bool(settings.CORS_ORIGIN_REGEX and re.fullmatch(settings.CORS_ORIGIN_REGEX, origen))


def cabeceras_cors(origen: Optional[str]) -> Dict[str, str]:
    """Cabeceras CORS para respuestas armadas a mano (los errores 500 no pasan por CORSMiddleware)."""
    if origen_permitido(origen):
        return {"Access-Control-Allow-Origin": origen, "Vary": "Origin"}
    return {}


def cabeceras_seguridad(ruta: str = "") -> Dict[str, str]:
    cabeceras = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Cross-Origin-Opener-Policy": "same-origin",
    }
    if not ruta.startswith(RUTAS_DOCUMENTACION):
        cabeceras["Content-Security-Policy"] = CSP_API
    if settings.es_produccion:
        cabeceras["Strict-Transport-Security"] = "max-age=31536000"
    return cabeceras


class CabecerasSeguridadMiddleware:
    """Middleware ASGI: agrega las cabeceras de seguridad sin leer ni retrasar el cuerpo."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ruta = scope.get("path", "")

        async def send_con_cabeceras(mensaje):
            if mensaje["type"] == "http.response.start":
                existentes = {nombre.lower() for nombre, _ in mensaje.get("headers", [])}
                extra = [(k.lower().encode("latin-1"), v.encode("latin-1"))
                         for k, v in cabeceras_seguridad(ruta).items() if k.lower().encode("latin-1") not in existentes]
                if ruta.startswith("/api/") and b"cache-control" not in existentes:
                    extra.append((b"cache-control", b"no-store"))
                mensaje["headers"] = list(mensaje.get("headers", [])) + extra
            await send(mensaje)

        await self.app(scope, receive, send_con_cabeceras)
