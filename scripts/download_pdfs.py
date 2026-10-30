"""Download BCRP PDFs (Inflation Reports and Monetary Program notes) to data/pdfs/.

www.bcrp.gob.pe asks for an interactive human verification that we do not automate.
This script opens a VISIBLE Chromium window: if the site shows a verification, solve
it once by hand. After that the script reuses the same browser session to discover
and download the PDFs. Files are validated by their %PDF signature, not by HTTP status
(the bot filter answers 200 with an HTML page).

Usage: uv run python scripts/download_pdfs.py [--years 2024 2025 2026]
Output: data/pdfs/<file>.pdf and data/pdfs/index.json (url, file, sha256, bytes).
"""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/pdfs"
HOME = "https://www.bcrp.gob.pe/"
LISTING_PAGES = [
    "https://www.bcrp.gob.pe/politica-monetaria/notas-informativas-del-programa-monetario.html",
    "https://www.bcrp.gob.pe/publicaciones/reporte-de-inflacion.html",
]
RI_MONTHS = ["marzo", "junio", "setiembre", "diciembre"]
RI_URL = "https://www.bcrp.gob.pe/docs/Publicaciones/Reporte-Inflacion/{y}/{m}/reporte-de-inflacion-{m}-{y}.pdf"
WANTED = re.compile(r"(Reporte-Inflacion|Notas-Informativas|nota-informativa)", re.I)


def wait_for_human(page: Page, timeout_s: int = 300) -> None:
    """Block until the site stops serving the Incapsula verification page."""
    page.goto(HOME, wait_until="load", timeout=60_000)
    deadline = time.time() + timeout_s
    warned = False
    while "_Incapsula_Resource" in page.content():
        if not warned:
            print(">> Resuelve la verificación en la ventana de Chromium (máx. 5 min)...")
            warned = True
        if time.time() > deadline:
            raise SystemExit("La verificación no se completó a tiempo.")
        page.wait_for_timeout(2_000)
    print("Sesión verificada.")


def discover(page: Page, years: list[str]) -> list[str]:
    urls = {RI_URL.format(y=y, m=m) for y in years for m in RI_MONTHS}
    for listing in LISTING_PAGES:
        page.goto(listing, wait_until="load", timeout=60_000)
        for href in re.findall(r'href="([^"]+\.pdf)"', page.content(), re.I):
            url = urljoin(listing, href)
            if WANTED.search(url) and any(y in url for y in years):
                urls.add(url)
    return sorted(urls)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", default=["2024", "2025", "2026"])
    years = parser.parse_args().years
    OUT.mkdir(parents=True, exist_ok=True)
    index_path = OUT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}

    with sync_playwright() as p:
        # Persistent profile: the verification survives between runs.
        ctx = p.chromium.launch_persistent_context(str(ROOT / "data/.browser"), headless=False)
        page = ctx.new_page()
        wait_for_human(page)
        urls = discover(page, years)
        print(f"{len(urls)} PDFs candidatos")
        for url in urls:
            if url in index:
                continue
            resp = ctx.request.get(url, timeout=120_000)
            body = resp.body()
            if not body.startswith(b"%PDF"):
                print(f"  -- {resp.status} no es PDF (no existe o bloqueado): {url}")
                continue
            name = url.rsplit("/", 1)[-1]
            (OUT / name).write_bytes(body)
            index[url] = {"file": name, "sha256": hashlib.sha256(body).hexdigest(),
                          "bytes": len(body)}  # fmt: skip
            index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
            print(f"  OK {name} ({len(body) // 1024} KB)")
            time.sleep(1)  # be gentle with the site
        ctx.close()
    print(f"Listo: {len(index)} PDFs en {OUT}")


if __name__ == "__main__":
    main()
