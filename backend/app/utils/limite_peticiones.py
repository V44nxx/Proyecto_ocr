"""
Límites que se aplican antes de leer el cuerpo de una petición.

FastAPI lee el formulario completo antes de revisar la sesión, así que sin esto cualquiera, sin cuenta,
podría mandar archivos enormes. Este middleware (ASGI puro, sin leer el cuerpo por adelantado):
  - en las rutas de subida exige un token válido antes de recibir nada;
  - rechaza con 413 los cuerpos que pasan el tope (por Content-Length, o contando si no lo traen).
La sesión completa (usuario activo, versión de sesión) la sigue revisando la dependencia de cada ruta.
"""
import json
import re

from jose import JWTError, jwt

from app.config import settings

RUTAS_SUBIDA = re.compile(r"^/api/(documentos/upload|comparacion/upload|personas/[^/]+/subir-pdf)/?$")
LIMITE_GENERAL_BYTES = 2 * 1024 * 1024  # JSON y formularios pequeños
METODOS_CON_CUERPO = {"POST", "PUT", "PATCH"}


class _CuerpoDemasiadoGrande(Exception):
    pass


def _token_valido(cabecera: bytes) -> bool:
    texto = cabecera.decode("latin-1")
    if not texto.startswith("Bearer "):
        return False
    try:
        payload = jwt.decode(texto[7:], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return False
    return bool(payload.get("sub"))


async def _responder(send, estado: int, detalle: str) -> None:
    cuerpo = json.dumps({"detail": detalle}).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": estado,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(cuerpo)).encode())],
    })
    await send({"type": "http.response.body", "body": cuerpo})


class LimitePeticionesMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in METODOS_CON_CUERPO:
            await self.app(scope, receive, send)
            return

        es_subida = bool(RUTAS_SUBIDA.match(scope["path"]))
        limite = settings.max_subida_total_bytes if es_subida else LIMITE_GENERAL_BYTES
        mensaje_413 = (
            f"La subida supera el máximo de {settings.MAX_SUBIDA_TOTAL_MB} MB por envío."
            if es_subida else "La petición es demasiado grande."
        )
        cabeceras = dict(scope["headers"])

        if es_subida and not _token_valido(cabeceras.get(b"authorization", b"")):
            await _responder(send, 401, "Token inválido o expirado")
            return

        largo = cabeceras.get(b"content-length")
        if largo is not None:
            try:
                largo_int = int(largo)
            except ValueError:
                largo_int = -1
            if largo_int < 0:
                await _responder(send, 400, "Content-Length inválido")
                return
            if largo_int > limite:
                await _responder(send, 413, mensaje_413)
                return

        recibido = 0
        respuesta_iniciada = False

        async def receive_contado():
            nonlocal recibido
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                recibido += len(mensaje.get("body", b""))
                if recibido > limite:
                    raise _CuerpoDemasiadoGrande()
            return mensaje

        async def send_marcado(mensaje):
            nonlocal respuesta_iniciada
            if mensaje["type"] == "http.response.start":
                respuesta_iniciada = True
            await send(mensaje)

        try:
            await self.app(scope, receive_contado, send_marcado)
        except _CuerpoDemasiadoGrande:
            if not respuesta_iniciada:
                await _responder(send, 413, mensaje_413)
