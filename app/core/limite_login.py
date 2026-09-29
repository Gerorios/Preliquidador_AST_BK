"""Límite de intentos de login por identificador.

Regla acordada: 5 fallos dentro de 15 minutos bloquean ese identificador por
15 minutos; un login correcto resetea el contador.

Vive en memoria del proceso: mismo supuesto que _USUARIO_CACHE (auth.py) y el
candado de generación de preliquidaciones, que el backend corre con un solo
worker de uvicorn. Con más de un worker cada uno tendría su propio contador
(el límite efectivo se multiplicaría) y habría que moverlo a un lugar
compartido. Reiniciar el servicio lo vacía: es la salida si se bloquea a
alguien por error. Lo consume sólo app/core/auth.py.
"""
import math
import threading
import time
from typing import Callable, Optional


class LimitadorIntentos:
    def __init__(
        self,
        reloj: Callable[[], float] = time.monotonic,
        maximo: int = 5,
        ventana_seg: float = 900,
        bloqueo_seg: float = 900,
    ):
        # Reloj inyectable para testear sin esperar. monotonic por defecto:
        # un ajuste de la hora del servidor no alarga ni acorta un bloqueo.
        self.reloj = reloj
        self.maximo = maximo
        self.ventana_seg = ventana_seg
        self.bloqueo_seg = bloqueo_seg
        # clave -> (fallos, inicio_ventana, bloqueado_hasta)
        self._intentos: dict[str, tuple[int, float, Optional[float]]] = {}
        # login es un endpoint sync: FastAPI lo corre en un threadpool, así
        # que dos intentos simultáneos pueden leer-modificar-escribir la misma
        # entrada a la vez. Sin el lock, ráfagas en paralelo perderían fallos
        # y conseguirían más intentos que el máximo.
        self._lock = threading.Lock()

    def _vencida(self, entrada: tuple[int, float, Optional[float]], ahora: float) -> bool:
        """Una entrada deja de contar cuando no está bloqueada (o su bloqueo
        venció) y su ventana de conteo ya pasó."""
        _fallos, inicio, hasta = entrada
        if hasta is not None:
            return ahora >= hasta
        return ahora - inicio > self.ventana_seg

    def bloqueado_hasta(self, clave: str) -> Optional[float]:
        """Instante del reloj hasta el que la clave está bloqueada, o None."""
        with self._lock:
            entrada = self._intentos.get(clave)
            if entrada is None or entrada[2] is None:
                return None
            if self.reloj() >= entrada[2]:
                # Bloqueo cumplido: se borra para que el próximo fallo arranque
                # el contador de cero, no desde 5.
                del self._intentos[clave]
                return None
            return entrada[2]

    def segundos_restantes(self, clave: str) -> Optional[int]:
        """Segundos de bloqueo que le quedan a la clave, redondeados hacia
        arriba (para Retry-After: estando bloqueado nunca da 0), o None."""
        hasta = self.bloqueado_hasta(clave)
        if hasta is None:
            return None
        return math.ceil(hasta - self.reloj())

    def registrar_fallo(self, clave: str) -> None:
        with self._lock:
            ahora = self.reloj()
            # Poda de todas las entradas vencidas en cada fallo: sin esto, cada
            # identificador distinto que alguien pruebe quedaría para siempre y
            # el dict crecería sin límite. Recorrerlo entero es barato para la
            # cantidad de usuarios de este sistema.
            for k in [k for k, e in self._intentos.items() if self._vencida(e, ahora)]:
                del self._intentos[k]

            entrada = self._intentos.get(clave)
            if entrada is None:
                fallos, inicio = 1, ahora
            else:
                fallos, inicio, hasta = entrada
                if hasta is not None:
                    # Ya bloqueada: un fallo más no alarga el bloqueo. El
                    # endpoint chequea el bloqueo antes y no debería llegar acá.
                    return
                fallos += 1

            hasta = ahora + self.bloqueo_seg if fallos >= self.maximo else None
            self._intentos[clave] = (fallos, inicio, hasta)

    def exito(self, clave: str) -> None:
        """Login correcto: el contador de esa clave vuelve a cero."""
        with self._lock:
            self._intentos.pop(clave, None)

    def limpiar(self) -> None:
        with self._lock:
            self._intentos.clear()


limitador_login = LimitadorIntentos()
