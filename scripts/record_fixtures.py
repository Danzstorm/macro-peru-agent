"""Verify every code in config/series.yml against the live API and save the responses
as test fixtures in tests/fixtures/bcrp_<code>.json.

Usage: uv run python scripts/record_fixtures.py
"""

import logging
from datetime import date
from pathlib import Path

import yaml

from macro_peru.bcrp.client import BcrpClient
from macro_peru.bcrp.periods import frequency

ROOT = Path(__file__).resolve().parents[1]
RANGES = {
    "diaria": (date(2026, 10, 15), date(2026, 10, 29)),
    "mensual": (date(2026, 1, 1), date(2026, 9, 1)),
    "trimestral": (date(2025, 1, 1), date(2026, 6, 1)),
    "anual": (date(2022, 1, 1), date(2025, 1, 1)),
}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    catalog = yaml.safe_load((ROOT / "config/series.yml").read_text(encoding="utf-8"))
    client = BcrpClient()
    for s in catalog["series"]:
        code = s["codigo"]
        assert frequency(code) == s["frecuencia"], f"{code}: frequency mismatch"
        start, end = RANGES[s["frecuencia"]]
        client.fetch_one(code, start, end)  # validates the response
        body = client.fetch_raw(code, start, end)
        (ROOT / f"tests/fixtures/bcrp_{code}.json").write_text(body, encoding="utf-8")
        print(f"OK {code} {s['alias']}")


if __name__ == "__main__":
    main()
