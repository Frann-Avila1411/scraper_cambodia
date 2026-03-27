#Flujo principal del scraper.
#este módulo contiene la lógica de búsqueda de marca, validación de resultados
#y descarga de archivos de salida.

import asyncio
import json
import logging
import os
import random
import urllib.parse
from typing import Optional, Tuple

import aiohttp
from playwright.async_api import async_playwright
from tenacity import RetryError

from .config import (
    DETAIL_URL_TEMPLATE,
    LOGO_URL_TEMPLATE,
    OUTPUT_DIR,
    REQUIRED_COOKIES,
    SEARCH_API_URL,
    SEARCH_PAGE_URL,
    USER_AGENT,
)
from .network import fetch_data
from .reporting import build_detail_html, summarize_result, write_debug_results


def normalize_filing_number(value: str) -> str:
    #Normaliza el Filing Number para comparar textos sin símbolos
    if not value:
        return ""
    return "".join(ch for ch in value.upper() if ch.isalnum())


def select_mark_result(results: list, filing_number: str) -> Optional[dict]:
    #Busca coincidencia exacta del número dentro de una lista de resultados
    target = normalize_filing_number(filing_number)
    candidate_keys = [
        "filing_number",
        "application_number",
        "application_no",
        "app_no",
        "number",
    ]

    for item in results:
        for key in candidate_keys:
            if normalize_filing_number(str(item.get(key, ""))) == target:
                return item
    return None


def extract_candidate_ids(strategies: list) -> list:
    #Toma IDs candidatos sin repetir desde estrategias previas
    ids = []
    seen = set()
    for strategy in strategies:
        for sample_id in strategy.get("sample_ids", []):
            if sample_id and sample_id not in seen:
                ids.append(sample_id)
                seen.add(sample_id)
    return ids


def html_contains_filing(html_content: bytes, filing_number: str) -> bool:
    #Verifica si el HTML contiene el Filing Number solicitado
    target = normalize_filing_number(filing_number)
    if not target:
        return False
    html_normalized = normalize_filing_number(html_content.decode("utf-8", errors="ignore"))
    return target in html_normalized


def item_matches_filing(item: dict, filing_number: str) -> bool:
    #valida si un resultado corresponde al Filing Number solicitado
    target = normalize_filing_number(filing_number)
    candidates = [
        item.get("filing_number", ""),
        item.get("application_number", ""),
        item.get("application_no", ""),
        item.get("number", ""),
        item.get("registration_number", ""),
    ]

    for candidate in candidates:
        if not candidate:
            continue
        candidate_text = str(candidate)
        candidate_clean = candidate_text.split("(")[0].strip()
        if normalize_filing_number(candidate_clean) == target:
            return True

    return False


async def search_result_by_pagination(
    session: aiohttp.ClientSession,
    filing_number: str,
    max_pages: int = 80,
) -> Tuple[Optional[dict], Optional[int]]:
    #Busca coincidencia recorriendo varias páginas de resultados
    for page in range(1, max_pages + 1):
        payload = {
            "search": {"key": "filing_number", "value": filing_number},
            "page": page,
            "per_page": 50,
        }

        try:
            data = await fetch_data(session, "POST", SEARCH_API_URL, json=payload)
        except RetryError as exc:
            logging.warning(
                "[%s] Se aborta paginación por límite o error repetido en página %s: %s",
                filing_number.replace("/", ""),
                page,
                exc,
            )
            break
        except aiohttp.ClientResponseError as exc:
            logging.warning(
                "[%s] Error HTTP en paginación (página %s): %s",
                filing_number.replace("/", ""),
                page,
                exc.status,
            )
            break

        results = data.get("data", {}).get("data", [])
        if not results:
            break

        for item in results:
            if item_matches_filing(item, filing_number):
                return item, page

        if page % 25 == 0:
            logging.info(
                "[%s] Sin coincidencia tras escanear %s páginas globales.",
                filing_number.replace("/", ""),
                page,
            )

        await asyncio.sleep(0.2)

    return None, None


async def search_result_via_playwright(filing_number: str, cookies_dict: dict) -> Optional[dict]:
    #Intenta encontrar la marca replicando la búsqueda desde la interfaz web
    search_obj = {"key": "filing_number", "value": filing_number}
    search_encoded = urllib.parse.quote(json.dumps(search_obj, separators=(",", ":")))
    urls = [
        f"{SEARCH_PAGE_URL}/new?tab=0&page=1&per_page=20&search={search_encoded}",
        f"{SEARCH_PAGE_URL}?tab=0&page=1&per_page=20&search={search_encoded}",
    ]

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)

        cookies = []
        for name in REQUIRED_COOKIES:
            value = cookies_dict.get(name)
            if value:
                cookies.append(
                    {
                        "name": name,
                        "value": value,
                        "url": "https://digitalip.cambodiaip.gov.kh",
                    }
                )

        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()
        responses = []

        def on_response(resp):
            if "/api/v1/web/trademark-search" in resp.url:
                responses.append(resp)

        page.on("response", on_response)

        for attempt in range(1, 4):
            for url in urls:
                try:
                    responses.clear()
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(3500)

                    for resp in reversed(responses):
                        try:
                            data = await resp.json()
                        except Exception:
                            continue

                        results = data.get("data", {}).get("data", [])
                        for item in results:
                            if item_matches_filing(item, filing_number):
                                await browser.close()
                                return item
                except Exception as exc:
                    logging.warning(
                        "[%s] Falló intento UI %s en %s: %s",
                        filing_number.replace("/", ""),
                        attempt,
                        url,
                        exc,
                    )
                    continue

            await asyncio.sleep(1.5)

        await browser.close()

    return None


async def resolve_id_by_detail(
    session: aiohttp.ClientSession,
    filing_number: str,
    candidate_ids: list,
    page_headers: dict,
) -> Optional[str]:
    #Valida IDs candidatos abriendo la página de detalle y buscando el número
    limit = min(30, len(candidate_ids))
    for idx, candidate_id in enumerate(candidate_ids[:limit], start=1):
        detail_url = DETAIL_URL_TEMPLATE.format(id_interno=candidate_id)
        try:
            html_content, _ = await fetch_data(
                session,
                "GET",
                detail_url,
                headers=page_headers,
            )
        except Exception:
            continue

        if html_contains_filing(html_content, filing_number):
            return candidate_id

        if idx % 10 == 0:
            logging.info(
                "[%s] Revisados %s ids candidatos sin coincidencia exacta en HTML.",
                filing_number.replace("/", ""),
                idx,
            )

    return None


async def search_exact_result(session: aiohttp.ClientSession, filing_number: str) -> Tuple[Optional[dict], list]:
    #Prueba combinaciones de búsqueda por API hasta encontrar match exacto
    strategies = []
    values = [filing_number, normalize_filing_number(filing_number)]
    keys = [
        "filing_number",
        "application_number",
        "application_no",
        "number",
        "registration_number",
    ]

    for key in keys:
        for value in values:
            payload = {
                "search": {"key": key, "value": value},
                "page": 1,
                "per_page": 50,
            }

            data = await fetch_data(session, "POST", SEARCH_API_URL, json=payload)
            results = data.get("data", {}).get("data", [])
            mark_info = select_mark_result(results, filing_number)

            strategies.append(
                {
                    "key": key,
                    "value": value,
                    "result_count": len(results),
                    "sample_ids": [r.get("id") for r in results[:5]],
                    "sample_records": [summarize_result(r) for r in results[:3]],
                }
            )

            if mark_info:
                return mark_info, strategies

    return None, strategies


async def get_cookies() -> dict:
    #Obtiene cookies de sesión necesarias para consultar el sitio
    for attempt in range(1, 4):
        cookies_dict = {}
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=USER_AGENT)
            page = await context.new_page()

            try:
                await page.goto(SEARCH_PAGE_URL, wait_until="networkidle", timeout=60000)
            except Exception as exc:
                logging.warning(
                    "Fallo al esperar networkidle para cookies (intento %s): %s. Reintentando con domcontentloaded.",
                    attempt,
                    exc,
                )
                await page.goto(SEARCH_PAGE_URL, wait_until="domcontentloaded", timeout=60000)

            cookies = await context.cookies()
            for cookie in cookies:
                if cookie["name"] in REQUIRED_COOKIES:
                    cookies_dict[cookie["name"]] = cookie["value"]

            await browser.close()

        if all(name in cookies_dict for name in REQUIRED_COOKIES):
            return cookies_dict

        logging.warning(
            "Cookies incompletas en intento %s: %s",
            attempt,
            sorted(list(cookies_dict.keys())),
        )
        await asyncio.sleep(2)

    raise RuntimeError("No se pudieron capturar todas las cookies requeridas después de varios intentos")


async def search_and_download(filing_number: str, cookies_dict: dict) -> None:
    #Ejecuta todo el proceso para un Filing Number
    #Busca la marca, genera el HTML de detalle y descarga la imagen.
    clean_number = filing_number.replace("/", "")
    xsrf_token_decoded = urllib.parse.unquote(cookies_dict.get("XSRF-TOKEN", ""))

    search_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-XSRF-TOKEN": xsrf_token_decoded,
        "Referer": SEARCH_PAGE_URL,
    }

    page_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": SEARCH_PAGE_URL,
    }

    image_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": SEARCH_PAGE_URL,
    }

    async with aiohttp.ClientSession(cookies=cookies_dict, headers=search_headers) as session:
        logging.info("[%s] Iniciando búsqueda.", clean_number)

        try:
            mark_info, strategies = await search_exact_result(session, filing_number)
        except Exception as exc:
            logging.error("[%s] Fallo crítico en la búsqueda: %s", clean_number, exc)
            return

        if not mark_info:
            logging.warning("[%s] Sin match exacto en API. Intentando búsqueda por UI (Playwright).", clean_number)
            mark_info = await search_result_via_playwright(filing_number, cookies_dict)
            if mark_info:
                logging.info("[%s] Coincidencia encontrada por UI con id=%s.", clean_number, mark_info.get("id"))

        if not mark_info:
            logging.warning("[%s] Sin match por UI. Intentando búsqueda por paginación global.", clean_number)
            mark_info, page_match = await search_result_by_pagination(session, filing_number)
            if mark_info:
                logging.info(
                    "[%s] Coincidencia encontrada por paginación en página %s con id=%s.",
                    clean_number,
                    page_match,
                    mark_info.get("id"),
                )

        if not mark_info:
            candidate_ids = extract_candidate_ids(strategies)
            logging.warning(
                "[%s] Sin match exacto en API. Probando %s ids candidatos contra HTML de detalle.",
                clean_number,
                len(candidate_ids),
            )
            validated_id = await resolve_id_by_detail(
                session,
                filing_number,
                candidate_ids,
                page_headers,
            )

            if not validated_id:
                write_debug_results(clean_number, strategies)
                logging.warning(
                    "[%s] No hubo coincidencia exacta para '%s'. Se guardó debug en %s_debug_search.json",
                    clean_number,
                    filing_number,
                    clean_number,
                )
                return

            mark_info = {
                "id": validated_id,
                "logo": True,
                "filing_number": filing_number,
            }
            logging.info("[%s] ID validado por contenido HTML: %s.", clean_number, validated_id)

        internal_id = mark_info.get("id")
        has_logo = mark_info.get("logo", False)

        filing_found = (
            mark_info.get("filing_number")
            or mark_info.get("application_number")
            or mark_info.get("application_no")
            or "desconocido"
        )
        logging.info("[%s] Resultado seleccionado: %s (id=%s).", clean_number, filing_found, internal_id)

        if not internal_id:
            logging.warning("[%s] No se obtuvo un ID interno.", clean_number)
            return

        image_output_name = f"{clean_number}_2.jpg" if has_logo else ""
        html_generated = build_detail_html(
            mark_info,
            filing_number,
            str(internal_id),
            image_output_name,
        )

        logging.info("[%s] Guardando detalle HTML estático con datos de la marca.", clean_number)
        try:
            with open(os.path.join(OUTPUT_DIR, f"{clean_number}_1.html"), "w", encoding="utf-8") as file_obj:
                file_obj.write(html_generated)
        except Exception as exc:
            logging.error("[%s] Falló el guardado del HTML: %s", clean_number, exc)

        if has_logo:
            logging.info("[%s] Descargando imagen.", clean_number)
            image_url = LOGO_URL_TEMPLATE.format(id_interno=internal_id)
            try:
                image_content, image_content_type = await fetch_data(
                    session,
                    "GET",
                    image_url,
                    headers=image_headers,
                )

                if not image_content_type.lower().startswith("image/"):
                    logging.warning(
                        "[%s] Content-Type inesperado para imagen: %s",
                        clean_number,
                        image_content_type,
                    )

                if len(image_content) < 1024:
                    logging.warning("[%s] Imagen muy pequeña (%s bytes).", clean_number, len(image_content))

                with open(os.path.join(OUTPUT_DIR, f"{clean_number}_2.jpg"), "wb") as file_obj:
                    file_obj.write(image_content)
            except Exception as exc:
                logging.error("[%s] Falló la descarga de la imagen: %s", clean_number, exc)
        else:
            logging.info("[%s] Imagen no disponible.", clean_number)


async def run_scraper(filing_numbers: list[str]) -> None:
    #Orquesta la ejecución completa para la lista de números recibida
    logging.info("Iniciando Playwright para capturar cookies...")
    try:
        cookies = await get_cookies()
        logging.info("Cookies capturadas con éxito.")
    except Exception as exc:
        logging.critical("No se pudieron obtener las cookies: %s", exc)
        return

    logging.info("Total de Filing Numbers a procesar: %s", len(filing_numbers))
    for number in filing_numbers:
        await search_and_download(number, cookies)
        await asyncio.sleep(random.uniform(3.0, 6.0))

    logging.info("Proceso finalizado.")
