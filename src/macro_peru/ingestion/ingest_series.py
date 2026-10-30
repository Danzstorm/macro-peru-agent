"""Fetch every series in config/series.yml from BCRPData and write one JSON file per
series to a landing directory, ready to be uploaded to the raw_api Volume.

Layout written under --out-dir (mirrors /Volumes/<catalog>/raw/raw_api/):
  series/ingest_date=YYYY-MM-DD/<code>_<run_id>.json   envelope + raw API payload
  catalog/series_catalogo.json                         curated catalog, one JSON per line

This runs in GitHub Actions, not on Databricks: the API needs headless Chromium to pass
its bot filter, and serverless compute lacks Chromium's system libraries.

Usage: uv run python -m macro_peru.ingestion.ingest_series --out-dir data/landing [--mode full]
"""

import argparse
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml

from macro_peru.bcrp.client import BcrpClient

ROOT = Path(__file__).resolve().parents[3]
FULL_START = date(2015, 1, 1)
INCREMENTAL_DAYS = 120  # recent values can be revised, silver keeps the latest


def load_catalog(path: Path = ROOT / "config/series.yml") -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["series"]


def ingest(out_dir: Path, mode: str, today: date, run_id: str) -> list[Path]:
    start = FULL_START if mode == "full" else today - timedelta(days=INCREMENTAL_DAYS)
    catalog = load_catalog()
    client = BcrpClient()
    series_dir = out_dir / "series" / f"ingest_date={today.isoformat()}"
    series_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for s in catalog:
        payload = client.fetch_one(s["codigo"], start, today)
        envelope = {
            "codigo": s["codigo"],
            "alias": s["alias"],
            "requested_start": start.isoformat(),
            "requested_end": today.isoformat(),
            "fetched_at": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "payload": payload,
        }
        path = series_dir / f"{s['codigo']}_{run_id}.json"
        path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
        s["nombre"] = payload["config"]["series"][0]["name"]
        written.append(path)
        print(f"OK {s['codigo']} {s['alias']}: {len(payload['periods'])} periods")

    catalog_dir = out_dir / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    lines = (json.dumps(s, ensure_ascii=False) for s in catalog)
    (catalog_dir / "series_catalogo.json").write_text("\n".join(lines), encoding="utf-8")
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    args = parser.parse_args()
    run_id = os.environ.get("GITHUB_RUN_ID") or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    ingest(args.out_dir, args.mode, date.today(), run_id)


if __name__ == "__main__":
    main()
