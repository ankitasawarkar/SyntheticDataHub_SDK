# JDF Synthetic Data Project

This project generates realistic synthetic data for finance and dealer schemas using PostgreSQL and CSV samples.

## Project Structure

- `src/synthetic_pipeline/`
  - `db.py` – generic DB connection via SQLAlchemy URL (`DB_CONFIG`).
  - `schema.py` – discovers tables, columns, PK/FK/UNIQUE constraints.
  - `profiling.py` – profiles existing DB and sample CSV distributions (optional).
  - `overrides.py` – builds per-table row targets from sample CSVs.
  - `generator.py` – generates synthetic rows with FK and uniqueness handling.
  - `ordering.py` – FK-safe table order and truncate helper.
  - `insert.py` – batch inserts into PostgreSQL.
  - `validation.py` – FK referential-integrity checks.
  - `pipeline.py` – batched end-to-end pipeline entrypoint.
- `synthetic_data_with_sample_rows copy.ipynb` – notebook version of the same pipeline logic for interactive runs and exploration.
- `sample_data/` – finance sample CSVs (e.g. `Customer.csv`, `Branch.csv`, etc.).
- `dealer_db/` – dealer sample CSVs.

## Prerequisites

- Python 3.9+ with the project `requirements.txt` installed into your environment.
- PostgreSQL database reachable from your machine.
- A `.env` file at project root with connection and pipeline settings.

## .env Configuration

Single `.env` file with comment/uncomment profiles, for example:

```env
# ===== finance profile (ACTIVE) =====
DB_CONFIG=postgresql+psycopg2://postgres:postgres@localhost:5432/jdf
SAMPLE_DIR=sample_data
BASE_TABLE_FOR_SAMPLE_OVERRIDE=customer
TARGET_ROWS_PER_TABLE=100000
BATCH_SIZE=20000
USE_EXISTING_DATA_PROFILE=false

# ===== dealer profile (INACTIVE) =====
# DB_CONFIG=postgresql+psycopg2://postgres:postgres@localhost:5432/dealer_db
# SAMPLE_DIR=dealer_db
# BASE_TABLE_FOR_SAMPLE_OVERRIDE=dealer
# TARGET_ROWS_PER_TABLE=200000
# BATCH_SIZE=20000
# USE_EXISTING_DATA_PROFILE=false
```

Key variables:
- `DB_CONFIG` – full SQLAlchemy URL (driver + user + password + host + db).
- `SAMPLE_DIR` – folder with CSVs for the active schema (`sample_data` or `dealer_db`).
- `BASE_TABLE_FOR_SAMPLE_OVERRIDE` – base table name (e.g. `customer` / `dealer`) that **has a CSV**; other tables scale from its row count.
- `TARGET_ROWS_PER_TABLE` – target rows for the base table; others are scaled from CSV ratios.
- `BATCH_SIZE` – number of rows inserted per batch (higher = faster but more memory).
- `USE_EXISTING_DATA_PROFILE` – `true`/`false`; profile live DB data when `true` (slower but more realistic).

To switch between finance and dealer, just comment/uncomment the relevant block and keep only one active profile.

## Sample CSV Placement

- Place finance CSVs under `sample_data/` with filenames matching table names, e.g.:
  - `sample_data/Customer.csv`
  - `sample_data/Branch.csv`
  - `sample_data/Account.csv`
  - etc.
- Place dealer CSVs under `dealer_db/` with the same convention, e.g. `dealer_db/dealer.csv`, `dealer_db/product.csv`.
- The pipeline automatically detects `<table>.csv` for each table in the schema and uses their row counts and value distributions.

## Running the Pipeline (src)

From the project root:

```bash
python -m src.synthetic_pipeline.pipeline
```

This will:
- Connect to the DB specified by `DB_CONFIG`.
- Discover schema and FK-safe order.
- Optionally profile existing DB and sample CSVs.
- Truncate all user tables (FK-safe, committed).
- Generate synthetic data in batches, honoring PK/UNIQUE constraints.
- Insert data and validate FK integrity.

The final row counts and FK validation summary are printed to stdout.

## Running via Notebook

1. Open `synthetic_data_with_sample_rows copy.ipynb` in VS Code or Jupyter.
2. Ensure `.env` is configured as above.
3. Run cells in order:
   - Cell 3: DB helpers (DBConfig, `get_connection`, `fetch_db_schema`).
   - Cell 11: environment config (`DB_HOST`, `DB_CONFIG`, `TARGET_ROWS_PER_TABLE`, etc.).
   - Cell 14: schema discovery and FK-safe table order.
   - Cell 17: profiling from DB and/or CSVs.
   - Cell 18: batched synthetic pipeline run.
4. The notebook prints per-table row counts and FK results, mirroring the src pipeline.

## Performance Notes

Example observed performance on a finance workload:

| Workload              | TARGET_ROWS_PER_TABLE | BATCH_SIZE | Time (seconds) | Time (minutes, approx.) |
|-----------------------|-----------------------|------------|----------------|--------------------------|
| finance (src, jdf)       | 100000                | 20000      | 1353.29        | 22.6 (~23)               |
| finance (notebook)    | 100000                | 20000      | –              | ~19                      |
| finance (src, jdf)    | 100000                | 20000      | 545.73         | 9.1                      |
| dealer (src, dealer ) | 100000                | 20000      | 328.69         | 5.5                      |

Actual performance will vary with hardware, network latency to PostgreSQL, and whether `USE_EXISTING_DATA_PROFILE` is enabled.

For faster large runs (e.g. ~1M rows in the base table):
- Increase `TARGET_ROWS_PER_TABLE` (e.g. `1000000`).
- Use a larger `BATCH_SIZE` (e.g. `50000` or `100000` if memory allows).
- Keep `USE_EXISTING_DATA_PROFILE=false` to avoid extra DB scans.

-------------------------------------
DB_CONFIG=postgresql+psycopg2://postgres:postgres@localhost:5432/dealer
SAMPLE_DIR=dealer_db
BASE_TABLE_FOR_SAMPLE_OVERRIDE=dealer
TARGET_ROWS_PER_TABLE=1000000
BATCH_SIZE=500000
USE_EXISTING_DATA_PROFILE=false
Row counts per table: {'public.dealer': 1000000, 'public.dealer_contract': 1000000, 'public.dealer_order': 2020408, 'public.dealer_region': 1000000, 'public.manufacturer': 1000000, 'public.product': 2020408}
FK violations: {}
Pipeline execution time: 4475.07 seconds = 01:14:35hr