"""
Bronze Layer Backfill Utility
------------------------------
One-off script to seed historical NEO data into the Bronze layer, so Silver/Gold
can be built with realistic volume without waiting weeks for the daily GitHub
Actions cron to accumulate it naturally.

Reuses the exact same fetch/save logic as fetch_neo_bronze.py — backfilling by
replaying the same ingestion code path over past dates is itself a Kappa pattern
(reprocessing history through the pipeline, not a separate batch job).

Run this from the project root:
    python scripts\\backfill_bronze.py

Env vars:
    NASA_API_KEY  (required)
    DAYS_BACK     (optional) - how many past days to backfill, defaults to 15
"""
import os
import sys
import time
from datetime import date, timedelta

from fetch_neo_bronze import fetch_neo_data, save_bronze_record


def main():
    api_key = os.environ.get("NASA_API_KEY")
    if not api_key:
        print("ERROR: NASA_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    days_back = int(os.environ.get("DAYS_BACK", "15"))
    today = date.today()

    dates_to_fetch = [today - timedelta(days=offset) for offset in range(1, days_back + 1)]
    dates_to_fetch.sort()  # oldest first, so the log reads chronologically

    print(f"Backfilling {len(dates_to_fetch)} days: {dates_to_fetch[0]} to {dates_to_fetch[-1]}")

    succeeded, failed = 0, []
    for target_date in dates_to_fetch:
        date_str = target_date.isoformat()
        try:
            payload = fetch_neo_data(date_str, api_key)
            save_bronze_record(payload, date_str)
            succeeded += 1
        except Exception as e:
            print(f"[FAIL] {date_str}: {e}", file=sys.stderr)
            failed.append(date_str)

        time.sleep(1)  # polite pacing, NASA's rate limit is generous but no need to rush

    print(f"\nDone. {succeeded} succeeded, {len(failed)} failed.")
    if failed:
        print(f"Failed dates: {failed}")


if __name__ == "__main__":
    main()
