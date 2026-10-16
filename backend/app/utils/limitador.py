"""
Límite de intentos en memoria, con ventana deslizante.

Funciona porque el backend corre en un solo proceso de uvicorn: con varios procesos o réplicas,
cada uno llevaría su propia cuenta. Las cuentas se pierden al reiniciar, lo que es aceptable aquí.
"""
import math
import threading
import time
from collections import deque
from typing import Deque, Dict, List

from fastapi import Request

_TODOS: List["Limitador"] = []


class Limitador:
    def __init__(self, maximo: int, ventana_segundos: int):
        self.maximo = maximo
        self.ventana = ventana_segundos
        self._eventos: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()
        self._registros = 0
        _TODOS.append(self)

    def _vigentes(self, clave: str, ahora: float) -> Deque[float]:
        cola = self._eventos.get(clave)
        if cola is None:
            return deque()
        while cola and cola[0] <= ahora - self.ventana:
            cola.popleft()
        if not cola:
            self._eventos.pop(clave, None)
        return cola

    def espera(self, clave: str) -> int:
        """Segundos que faltan para poder intentar de nuevo; 0 si puede intentar ya."""
        ahora = time.monotonic()
        with self._lock:
            cola = self._vigentes(clave, ahora)
            if len(cola) < self.maximo:
                return 0
            return max(1, math.ceil(cola[0] + self.ventana - ahora))

    def registrar(self, clave: str) -> None:
        ahora = time.monotonic()
        with self._lock:
            self._registros += 1
            if self._registros % 500 == 0:  # de vez en cuando, soltar las claves que ya vencieron
                for otra in list(self._eventos):
                    self._vigentes(otra, ahora)
            cola = self._vigentes(clave, ahora)
            cola.append(ahora)
            self._eventos[clave] = cola

    def reiniciar(self, clave: str) -> None:
        with self._lock:
            self._eventos.pop(clave, None)

    def vaciar(self) -> None:
        with self._lock:
            self._eventos.clear()


def vaciar_todos() -> None:
    """Borra todas las cuentas (para las pruebas)."""
    for limitador in _TODOS:
        limitador.vaciar()


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
