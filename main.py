#Este archivo solo prepara lo básico, logs, carpeta de salida y argumentos
#y luego ejecuta el flujo principal del scraper.

import asyncio

from scraper.cli import parse_filing_numbers_from_cli
from scraper.config import ensure_output_dir, setup_logging
from scraper.workflow import run_scraper


if __name__ == "__main__":
    setup_logging()
    ensure_output_dir()
    filing_numbers_cli = parse_filing_numbers_from_cli()
    asyncio.run(run_scraper(filing_numbers_cli))
