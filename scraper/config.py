#Configuración central del scraper.
#Este módulo reúne rutas, constantes y ajustes generales para evitar valores
#duplicados en distintos archivos.


import logging
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)
REQUIRED_COOKIES = ["laravel_session", "XSRF-TOKEN"]

DEFAULT_FILING_NUMBERS = [
    "KH/49633/12",
    "KH/59286/14",
    "KH/83498/19",
]

REQUESTS_PER_MINUTE = 30
MIN_SECONDS_BETWEEN_REQUESTS = 1.1

SEARCH_API_URL = "https://digitalip.cambodiaip.gov.kh/api/v1/web/trademark-search"
SEARCH_PAGE_URL = "https://digitalip.cambodiaip.gov.kh/en/trademark-search"
DETAIL_URL_TEMPLATE = (
    "https://digitalip.cambodiaip.gov.kh/en/trademark-search/trademark-detail?afnb={id_interno}"
)
LOGO_URL_TEMPLATE = (
    "https://digitalip.cambodiaip.gov.kh/trademark-detail-logo/{id_interno}?type=ts_logo_detail_screen"
)


def ensure_output_dir() -> None:
    #Crea la carpeta de salida si no existe
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def setup_logging() -> None:
    #Configura el formato de logs que se verá en consola
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )
