# NASA Near-Earth Object (NEO) Watch — Kappa Pipeline 🛰️

> A self-running, Kappa-inspired pipeline that ingests NASA's Near-Earth Object data daily via automated GitHub Actions, cleans genuinely messy multi-unit telemetry, and loads it into Snowflake for analysis.

---

## 🤖 What Makes This Project Different

Unlike a typical portfolio ETL that runs once against a static Kaggle CSV, this pipeline **runs itself**: a GitHub Actions cron job pulls fresh data from NASA's live API every day, with zero manual intervention, and commits each day's raw response as an immutable record. It's a small, honest example of production thinking — automated collection, defensive data quality checks, and a cloud data warehouse — applied at portfolio scale.

---

## 📌 Business Questions Answered
- How many potentially hazardous objects approach Earth on a given day, and how does that vary over time?
- Which currently tracked asteroids pose the greatest actual risk (a combination of proximity, size, and speed)?
- What relationship, if any, exists between an object's size/velocity and NASA's "potentially hazardous" classification?

---

## 🏗️ Architecture — Why Kappa, Not Medallion-Only

```
NASA NeoWs API (daily feed for "today")
      │
      ▼  GitHub Actions cron — runs unattended every day at 12:00 UTC
 Bronze Layer     → Raw JSON, one immutable file per day, committed to Git (append-only log)
      │
      ▼  Reprocessed over the full log — not a separate batch job
 Silver Layer     → Nested JSON flattened, units normalized (km, km/h), type-cast, deduplicated
      │
      ▼  Python + Snowflake connector
  Gold Layer      → NEO_FACTS, DAILY_SUMMARY, HAZARD_WATCHLIST tables in Snowflake
      │
      ▼
 Power BI Dashboard  → Connected live to Snowflake
```

In a Kappa architecture there's no separate batch layer and speed layer — everything replays through the *same* ingestion and transformation code, whether it's today's new record or a manual backfill of past days. That's literally how this project was built: `scripts/backfill_bronze.py` seeded 18 days of history by calling the exact same `fetch_neo_bronze.py` functions the daily cron uses — reprocessing history through the pipeline, not a separate one-off script.

---

## 📊 Data Source
| Dataset | Source |
|---|---|
| Near-Earth Object daily feed | [NASA NeoWs API](https://api.nasa.gov) |

> Requires a free API key from api.nasa.gov. Not included in this repo — set as `NASA_API_KEY` (local `.env` or GitHub Secret).

---

## 🧹 Data Quality: What Was Actually Dirty

- **Numeric fields arrive as strings, not numbers.** `relative_velocity` and `miss_distance` are returned as text by the API — a silent type defect, not a missing-value problem, and easy to miss if you don't check dtypes explicitly.
- **`estimated_diameter` is nested across 4 unit systems at once** (kilometers, meters, miles, feet). Only kilometers were kept; the other three were discarded deliberately during flattening.
- **`close_approach_data` is a list**, not a single object — an asteroid can have zero, one, or multiple approach events per record. The flattening logic handles all three cases explicitly instead of assuming exactly one.
- **Backfilling historical dates can create duplicate (asteroid, approach date) pairs** if ever re-run. Deduplication keeps the most recently ingested version of each pair.
- **A real production bug was found and fixed during this build**: loading a pandas dataframe with timezone-aware timestamps into Snowflake via `write_pandas` without `use_logical_type=True` silently corrupted dates — `2026-08-06` loaded as the year `77090`. Fixed by explicitly enabling Arrow logical types on load.

> Over the initial 18-day monitoring window (Aug 6–23, 2026), the cleaned dataset ended up with **0 null values and 0 true duplicates** — a legitimate finding about this specific window, not evidence the defensive checks were unnecessary. Type coercion, unit normalization, and deduplication run unconditionally on every load, regardless of whether that day's data needed fixing.

**Snapshot as of Aug 23, 2026** (grows daily — see [Actions history](../../actions) for the live log): 81 objects tracked across 18 days, 11 flagged as potentially hazardous, closest recorded approach ~2.52 million km.

---

## 🛠️ Tech Stack
| Layer | Tools |
|---|---|
| Ingestion | Python, `requests`, GitHub Actions (cron) |
| Storage (Bronze/Silver) | JSON (Git-tracked), Parquet |
| Transformation | Pandas |
| Warehouse (Gold) | Snowflake |
| Visualization | Power BI — see [`/powerbi`](./powerbi/) folder |
| Orchestration | GitHub Actions (scheduled + manual dispatch) |
| Version Control | Git, GitHub |

---

## 📁 Project Structure
```
nasa-neo-kappa-pipeline/
│
├── .github/
│   └── workflows/
│       └── daily_ingest.yml       ← runs the Bronze ingestion every day, unattended
│
├── data/
│   ├── bronze/                    ← raw JSON, one immutable file per day (tracked by Git)
│   └── silver/                    ← cleaned Parquet output (not tracked by Git)
│
├── notebooks/
│   └── 02_silver_transform.ipynb  ← cleaning, unit normalization, deduplication
│
├── scripts/
│   ├── fetch_neo_bronze.py        ← core ingestion logic (used by cron AND backfill)
│   ├── backfill_bronze.py         ← seeds historical days by replaying the same logic
│   └── load_gold_snowflake.py     ← loads Silver into Snowflake, builds Gold tables via SQL
│
├── powerbi/
│   └── NASA_NEO_Watch_Dashboard.pbix
│
├── .env.example
├── requirements.txt
├── .gitignore
└── README.md
```

---

## ⚙️ How to Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/Cahudisa/nasa-neo-kappa-pipeline.git
cd nasa-neo-kappa-pipeline

# 2. Create environment
conda create -n nasa-neo-pipeline python=3.10 -y
conda activate nasa-neo-pipeline
pip install -r requirements.txt

# 3. Set up credentials
cp .env.example .env          # fill in your Snowflake credentials
set NASA_API_KEY=your_key     # Windows (use `export` on Mac/Linux)

# 4. Ingest data
python scripts/fetch_neo_bronze.py       # today only
python scripts/backfill_bronze.py        # optional: seeds N past days

# 5. Run the Silver transformation
# open notebooks/02_silver_transform.ipynb and run all cells

# 6. Load the Gold layer into Snowflake
python scripts/load_gold_snowflake.py

# 7. Open the dashboard
# powerbi/NASA_NEO_Watch_Dashboard.pbix — connect with your own Snowflake credentials
```

---

## 💼 Business Impact

Even at portfolio scale, this pipeline is built the way a production monitoring feed would be: unattended daily collection means no one has to remember to "run the report" — the same discipline that matters for daily sales feeds, fraud alerts, or supply chain telemetry, where a missed manual step means a missed event. A small daily API pull committed as an immutable, auditable log is a low-cost alternative to a full orchestration platform when scale doesn't (yet) justify one — and it scales cleanly into one when it does.

---

## 🚧 Path to Production

**Already implemented:**
- ✅ Automated, unattended ingestion (GitHub Actions cron)
- ✅ Immutable, auditable append-only log (Bronze tracked in Git history)
- ✅ Defensive data quality checks (type coercion, deduplication) that run regardless of outcome
- ✅ Separation of concerns: cloud warehouse for Gold, not local files

**What a full production version would add:**
- Automate the Silver/Gold steps (currently notebook/script-driven) as a second scheduled GitHub Actions job
- Data quality alerting (e.g., Slack/email notification on API failure or an unexpected duplicate spike)
- Secrets managed via a dedicated vault instead of GitHub Secrets for a multi-service setup
- Snowflake Tasks + Streams for incremental Gold builds instead of `CREATE OR REPLACE TABLE` on every run

---

## 👤 Author
**Carlos Díaz** — Data Engineer
[GitHub](https://github.com/Cahudisa)
