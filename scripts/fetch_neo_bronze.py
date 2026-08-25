"""
NASA NeoWs Bronze Layer Ingestion
----------------------------------
Fetches Near Earth Object data for a single date and appends it as a new
immutable JSON record to the Bronze layer. Designed to run daily via a
GitHub Actions cron job (Kappa-inspired: one append-only log, no separate
batch/speed layers).

Env vars:
    NASA_API_KEY  (required) - your free key from https://api.nasa.gov
    TARGET_DATE   (optional) - YYYY-MM-DD, defaults to today (UTC).
                                Useful for manual backfilling of past dates.
"""
import os
import sys
import json
from pathlib import Path
from datetime import date, datetime, timezone

import requests

NASA_API_URL = "https://api.nasa.gov/neo/rest/v1/feed"
BRONZE_DIR = Path("data/bronze")


def fetch_neo_data(target_date: str, api_key: str) -> dict:
    """Fetch the raw NEO feed for a single date from the NASA NeoWs API."""
    params = {
        "start_date": target_date,
        "end_date": target_date,
        "api_key": api_key,
    }
    response = requests.get(NASA_API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def save_bronze_record(payload: dict, target_date: str) -> Path:
    """Persist the raw API response as a date-stamped, append-only JSON file."""
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BRONZE_DIR / f"neo_{target_date}.json"

    if output_path.exists():
        print(f"[SKIP] {output_path} already exists — Bronze is append-only, not overwritten.")
        return output_path

    envelope = {
        "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "NASA NeoWs API - feed endpoint",
        "query_date": target_date,
        "raw_response": payload,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)

    print(f"[OK] Saved {output_path}")
    return output_path


def main():
    api_key = os.environ.get("NASA_API_KEY")
    if not api_key:
        print("ERROR: NASA_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    target_date = os.environ.get("TARGET_DATE", date.today().isoformat())

    try:
        payload = fetch_neo_data(target_date, api_key)
    except requests.RequestException as e:
        print(f"ERROR: NASA API request failed: {e}", file=sys.stderr)
        sys.exit(1)

    save_bronze_record(payload, target_date)


if __name__ == "__main__":
    main()
