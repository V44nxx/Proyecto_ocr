"""
Límite de intentos con ventana deslizante (inicios de sesión fallidos, códigos equivocados, etc.).

En el servidor la cuenta vive en la base (tabla intentos_limitados): sobrevive a los reinicios de cada
despliegue y la comparten varios procesos de uvicorn. La clave (correo, IP o usuario) se guarda como hash.
Sin base (pruebas sin PostgreSQL, o si no conectó al arrancar) la cuenta se lleva en memoria.
Si la base falla en plena petición, el límite no bloquea a nadie: sin base tampoco hay inicio de sesión.
"""
import hashlib
import math
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, List

from fastapi import Request
from app.utils.logger import app_logger as logger

_TODOS: List["Limitador"] = []
_EN_BASE = False
RETENCION_HORAS = 24      # los intentos más viejos no cuentan para ninguna ventana y se borran al arrancar


def usar_base_de_datos(activo: bool) -> None:
    """Al arrancar con la base lista, los límites pasan a contarse en ella."""
    global _EN_BASE
    _EN_BASE = activo


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _hash(clave: str) -> str:
    return hashlib.sha256(str(clave).encode("utf-8")).hexdigest()


def _sesion():
    from app import database   # al llamar: las pruebas cambian SessionLocal por la base de pruebas
    return database.SessionLocal()


class Limitador:
    def __init__(self, tipo: str, maximo: int, ventana_segundos: int):
        self.tipo = tipo
        self.maximo = maximo
        self.ventana = ventana_segundos
        self._eventos: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()
        self._registros = 0
        _TODOS.append(self)

    # ── En la base ──────────────────────────────────────────────────

    def _espera_en_base(self, clave: str) -> int:
        from app.models.intento_limitado import IntentoLimitado
        ahora = _ahora()
        db = _sesion()
        try:
            momentos = [m for (m,) in db.query(IntentoLimitado.momento).filter(
                IntentoLimitado.limitador == self.tipo,
                IntentoLimitado.clave == _hash(clave),
                IntentoLimitado.momento > ahora - timedelta(seconds=self.ventana),
            ).order_by(IntentoLimitado.momento).all()]
        finally:
            db.close()
        if len(momentos) < self.maximo:
            return 0
        # Se puede volver a intentar cuando salgan de la ventana los que sobran del máximo
        libera = momentos[len(momentos) - self.maximo] + timedelta(seconds=self.ventana)
        return max(1, math.ceil((libera - ahora).total_seconds()))

    def _registrar_en_base(self, clave: str) -> None:
        from app.models.intento_limitado import IntentoLimitado
        db = _sesion()
        try:
            db.add(IntentoLimitado(limitador=self.tipo, clave=_hash(clave), momento=_ahora()))
            db.commit()
        finally:
            db.close()

    def _borrar_en_base(self, clave=None) -> None:
        from app.models.intento_limitado import IntentoLimitado
        db = _sesion()
        try:
            consulta = db.query(IntentoLimitado).filter(IntentoLimitado.limitador == self.tipo)
            if clave is not None:
                consulta = consulta.filter(IntentoLimitado.clave == _hash(clave))
            consulta.delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    # ── En memoria ──────────────────────────────────────────────────

    def _vigentes(self, clave: str, ahora: float) -> Deque[float]:
        cola = self._eventos.get(clave)
        if cola is None:
            return deque()
        while cola and cola[0] <= ahora - self.ventana:
            cola.popleft()
        if not cola:
            self._eventos.pop(clave, None)
        return cola

    def _espera_en_memoria(self, clave: str) -> int:
        ahora = time.monotonic()
        with self._lock:
            cola = self._vigentes(clave, ahora)
            if len(cola) < self.maximo:
                return 0
            return max(1, math.ceil(cola[0] + self.ventana - ahora))

    def _registrar_en_memoria(self, clave: str) -> None:
        ahora = time.monotonic()
        with self._lock:
            self._registros += 1
            if self._registros % 500 == 0:  # de vez en cuando, soltar las claves que ya vencieron
                for otra in list(self._eventos):
                    self._vigentes(otra, ahora)
            cola = self._vigentes(clave, ahora)
            cola.append(ahora)
            self._eventos[clave] = cola

    def vaciar_memoria(self) -> None:
        with self._lock:
            self._eventos.clear()

    # ── Interfaz ────────────────────────────────────────────────────

    def espera(self, clave: str) -> int:
        """Segundos que faltan para poder intentar de nuevo; 0 si puede intentar ya."""
        if not _EN_BASE:
            return self._espera_en_memoria(clave)
        try:
            return self._espera_en_base(clave)
        except Exception as e:
            logger.warning(f"Límite '{self.tipo}': no se pudo consultar la base ({type(e).__name__})")
            return 0

    def registrar(self, clave: str) -> None:
        if not _EN_BASE:
            return self._registrar_en_memoria(clave)
        try:
            self._registrar_en_base(clave)
        except Exception as e:
            logger.warning(f"Límite '{self.tipo}': no se pudo anotar el intento ({type(e).__name__})")

    def reiniciar(self, clave: str) -> None:
        if not _EN_BASE:
            with self._lock:
                self._eventos.pop(clave, None)
            return
        try:
            self._borrar_en_base(clave)
        except Exception as e:
            logger.warning(f"Límite '{self.tipo}': no se pudo reiniciar la cuenta ({type(e).__name__})")

    def vaciar(self) -> None:
        self.vaciar_memoria()
        if _EN_BASE:
            self._borrar_en_base()


def vaciar_todos() -> None:
    """Borra todas las cuentas (para las pruebas)."""
    for limitador in _TODOS:
        limitador.vaciar()


def vaciar_memoria() -> None:
    """Lo que perdía un reinicio cuando la cuenta vivía solo en memoria (para las pruebas)."""
    for limitador in _TODOS:
        limitador.vaciar_memoria()


def purgar_vencidos() -> int:
    """Borra los intentos de más de RETENCION_HORAS (se llama al arrancar). Devuelve cuántos borró."""
    from app.models.intento_limitado import IntentoLimitado
    db = _sesion()
    try:
        borrados = db.query(IntentoLimitado).filter(
            IntentoLimitado.momento < _ahora() - timedelta(hours=RETENCION_HORAS)
        ).delete(synchronize_session=False)
        db.commit()
        return borrados
    finally:
        db.close()


def mensaje_espera(segundos: int, motivo: str = "Demasiados intentos fallidos") -> str:
    minutos = max(1, math.ceil(segundos / 60))
    return f"{motivo}. Espera {minutos} {'minuto' if minutos == 1 else 'minutos'} e intenta de nuevo."


def ip_cliente(request: Request) -> str:
    """
    IP del cliente. Detrás de Traefik, la IP real llega primera en X-Forwarded-For (Traefik descarta
    la cabecera que mande el propio cliente). Sin la cabecera, la de la conexión.
    """
    reenviada = request.headers.get("x-forwarded-for", "")
    if reenviada.strip():
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"
