#Funciones de red del scraper.
#aquí se centraliza el envío de peticiones con reintentos y pausas para
#evitar errores por exceso de tráfico.

import asyncio
import logging
import random
from typing import Any

import aiohttp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import MIN_SECONDS_BETWEEN_REQUESTS, REQUESTS_PER_MINUTE
from .rate_limiter import RequestRateLimiter

RATE_LIMITER = RequestRateLimiter(
    requests_per_minute=REQUESTS_PER_MINUTE,
    min_interval_seconds=MIN_SECONDS_BETWEEN_REQUESTS,
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    before_sleep=lambda retry_state: logging.warning(
        "Reintentando petición por error de red... Intento %s",
        retry_state.attempt_number,
    ),
)
async def fetch_data(session: aiohttp.ClientSession, method: str, url: str, **kwargs) -> Any:
    #Realiza una petición HTTP y devuelve JSON o bytes.
    #también aplica control de ritmo y espera especial cuando el servidor
    #responde con límites temporales.
    await RATE_LIMITER.wait_turn()
    async with getattr(session, method.lower())(url, **kwargs) as response:
        if response.status in (429, 403):
            retry_after_header = response.headers.get("Retry-After")
            retry_after = None
            if retry_after_header and retry_after_header.isdigit():
                retry_after = int(retry_after_header)

            if retry_after is None:
                retry_after = random.uniform(45, 90) if response.status == 429 else random.uniform(20, 45)

            logging.warning(
                "Respuesta %s en %s. Esperando %.1fs antes de reintentar.",
                response.status,
                url,
                retry_after,
            )
            await asyncio.sleep(retry_after)

        response.raise_for_status()
        if kwargs.get("json") is not None or method.upper() == "POST":
            return await response.json()
        return await response.read(), response.headers.get("Content-Type", "")
