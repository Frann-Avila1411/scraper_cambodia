#Entrada de datos por consola
#permite pasar Filing Numbers por argumentos o por archivo de texto

import argparse
import logging
from typing import List

from .config import DEFAULT_FILING_NUMBERS


def normalize_filing_list(values: List[str]) -> List[str]:
    #Limpia la lista recibida y elimina valores repetidos
    output: List[str] = []
    seen = set()

    for raw in values:
        if not raw:
            continue
        parts = [p.strip() for p in str(raw).split(",")]
        for part in parts:
            if not part:
                continue
            if part not in seen:
                output.append(part)
                seen.add(part)

    return output


def load_filing_numbers_from_file(file_path: str) -> List[str]:
    #Lee un archivo con un Filing Number por línea
    numbers: List[str] = []
    with open(file_path, "r", encoding="utf-8") as file_obj:
        for line in file_obj:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            numbers.append(line)
    return numbers


def parse_filing_numbers_from_cli() -> List[str]:
    #Obtiene Filing Numbers desde la consola.
    #Si no se envía nada, devuelve la lista base por defecto.

    parser = argparse.ArgumentParser(
        description="Scraper de marcas Cambodia IP por Filing Number"
    )
    parser.add_argument(
        "filing_numbers",
        nargs="*",
        help="Filing Number(s) a descargar. Ejemplo: KH/49633/12 KH/59286/14",
    )
    parser.add_argument(
        "-f",
        "--file",
        dest="file_path",
        help="Ruta a archivo .txt con un Filing Number por línea",
    )

    args = parser.parse_args()

    numbers: List[str] = []
    if args.file_path:
        try:
            numbers.extend(load_filing_numbers_from_file(args.file_path))
        except Exception as exc:
            logging.error("No se pudo leer el archivo de números '%s': %s", args.file_path, exc)

    if args.filing_numbers:
        numbers.extend(args.filing_numbers)

    numbers = normalize_filing_list(numbers)
    if numbers:
        return numbers

    logging.info("No se enviaron Filing Numbers por consola. Se usará la lista por defecto.")
    return DEFAULT_FILING_NUMBERS
