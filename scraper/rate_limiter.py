#Control de ritmo de peticiones
#este módulo evita enviar demasiadas solicitudes en poco tiempo.

import asyncio
import random
import time
from collections import deque


class RequestRateLimiter:
    #Limita la cantidad de solicitudes para reducir bloqueos

    def __init__(self, requests_per_minute: int, min_interval_seconds: float):
        self.requests_per_minute = requests_per_minute
        self.min_interval_seconds = min_interval_seconds
        self._window_seconds = 60.0
        self._timestamps = deque()
        self._last_request_ts = 0.0
        self._lock = asyncio.Lock()

    async def wait_turn(self) -> None:
        #Espera lo necesario antes de permitir la siguiente petición
        async with self._lock:
            now = time.monotonic()

            while self._timestamps and (now - self._timestamps[0]) > self._window_seconds:
                self._timestamps.popleft()

            min_interval_wait = self.min_interval_seconds - (now - self._last_request_ts)
            if min_interval_wait > 0:
                await asyncio.sleep(min_interval_wait + random.uniform(0.05, 0.2))
                now = time.monotonic()

            if len(self._timestamps) >= self.requests_per_minute:
                wait_for_slot = self._window_seconds - (now - self._timestamps[0])
                if wait_for_slot > 0:
                    await asyncio.sleep(wait_for_slot + random.uniform(0.1, 0.5))
                    now = time.monotonic()

                while self._timestamps and (now - self._timestamps[0]) > self._window_seconds:
                    self._timestamps.popleft()

            self._timestamps.append(now)
            self._last_request_ts = now
