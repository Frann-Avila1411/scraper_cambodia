#Generación de salidas del scraper
#Incluye la creación del HTML de detalle y archivos de apoyo para depuración.

import html
import json
import os
import urllib.parse
from typing import Dict, List

from .config import DETAIL_URL_TEMPLATE, OUTPUT_DIR


def write_debug_results(clean_number: str, strategies: List[dict]) -> None:
    #Guarda un JSON con información de búsqueda cuando no hay coincidencia
    debug_path = os.path.join(OUTPUT_DIR, f"{clean_number}_debug_search.json")
    with open(debug_path, "w", encoding="utf-8") as file_obj:
        json.dump(strategies, file_obj, ensure_ascii=False, indent=2)


def summarize_result(item: dict) -> Dict[str, object]:
    #Extrae campos útiles de un resultado para inspección rápida
    fields_of_interest = [
        "id",
        "filing_number",
        "application_number",
        "application_no",
        "number",
        "registration_number",
        "mark_name",
        "logo",
        "status",
    ]

    summary: Dict[str, object] = {"_keys": sorted(list(item.keys()))}
    for field in fields_of_interest:
        if field in item:
            summary[field] = item.get(field)
    return summary


def normalize_text(value) -> str:
    #Convierte valores vacíos o nulos en texto legible
    if value is None:
        return "N/A"
    text = str(value).strip()
    return text if text else "N/A"


def build_detail_html(
    mark_info: dict,
    filing_number: str,
    internal_id: str,
    image_file_name: str,
) -> str:
    #Construye un HTML simple y legible con los datos de la marca
    title = normalize_text(mark_info.get("title") or mark_info.get("mark_name") or "Marca")

    fields = [
        ("Filing Number", mark_info.get("number") or filing_number),
        ("Application Number", mark_info.get("application_number") or mark_info.get("application_no") or internal_id),
        ("Registration Number", mark_info.get("registration_number")),
        ("Owner", mark_info.get("owner")),
        ("Address", mark_info.get("address")),
        ("Representative", mark_info.get("representative")),
        ("Status", mark_info.get("status")),
        ("Nice Class", mark_info.get("nice_class")),
        ("Country", mark_info.get("country")),
        ("Application Date", mark_info.get("application_date")),
        ("Registration Date", mark_info.get("registration_date")),
        ("Publication Date", mark_info.get("publication_date")),
        ("Expiration Date", mark_info.get("expiration_date")),
        ("Type of Mark", mark_info.get("type_of_mark")),
        ("Kind of Mark", mark_info.get("kind_of_mark")),
    ]

    rows: List[str] = []
    for label, value in fields:
        rows.append(
            "          <tr>\n"
            f"            <th>{html.escape(label)}</th>\n"
            f"            <td>{html.escape(normalize_text(value))}</td>\n"
            "          </tr>"
        )

    rows_html = "\n".join(rows)
    official_url = DETAIL_URL_TEMPLATE.format(id_interno=urllib.parse.quote(internal_id))

    html_lines = [
        "<!doctype html>",
        "<html lang='es'>",
        "  <head>",
        "    <meta charset='utf-8'>",
        "    <meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"    <title>{html.escape(title)} - {html.escape(filing_number)}</title>",
        "    <style>",
        "      body{font-family:Segoe UI,Arial,sans-serif;background:#f6f7fb;color:#1f2937;margin:0;padding:24px;}",
        "      .wrap{max-width:900px;margin:0 auto;}",
        "      .card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin-bottom:16px;}",
        "      h1{margin:0 0 8px;font-size:28px;}",
        "      p.meta{margin:0;color:#4b5563;font-size:14px;}",
        "      table{width:100%;border-collapse:collapse;margin-top:12px;}",
        "      th,td{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top;}",
        "      th{width:240px;color:#111827;background:#f9fafb;}",
        "      img{max-width:320px;height:auto;border:1px solid #e5e7eb;border-radius:8px;padding:6px;background:#fff;}",
        "      a{color:#1d4ed8;text-decoration:none;}",
        "      a:hover{text-decoration:underline;}",
        "    </style>",
        "  </head>",
        "  <body>",
        "    <div class='wrap'>",
        "      <section class='card'>",
        f"        <h1>{html.escape(title)}</h1>",
        f"        <p class='meta'>Filing solicitado: {html.escape(filing_number)} | ID interno: {html.escape(internal_id)}</p>",
        f"        <p class='meta'>Fuente oficial: <a href='{html.escape(official_url)}' target='_blank' rel='noopener noreferrer'>{html.escape(official_url)}</a></p>",
        "      </section>",
        "      <section class='card'>",
        "        <h2>Detalle de la marca</h2>",
        "        <table>",
        f"{rows_html}",
        "        </table>",
        "      </section>",
    ]

    if image_file_name:
        html_lines.extend(
            [
                "      <section class='card'>",
                "        <h2>Logo</h2>",
                f"        <img src='{html.escape(image_file_name)}' alt='Logo de la marca {html.escape(title)}'>",
                "      </section>",
            ]
        )

    html_lines.extend(
        [
            "    </div>",
            "  </body>",
            "</html>",
        ]
    )

    return "\n".join(html_lines) + "\n"
