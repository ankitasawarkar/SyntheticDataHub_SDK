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
# ===== example ETT profile (ACTIVE) =====

# Core connection info used by src.synthetic_pipeline.pipeline.main
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ett
DB_USER=postgres
DB_PASSWORD=postgres

# Optional: generic SQLAlchemy URL (used by db.py when present).
# If set, this overrides the host/port/name/user/password above.
DB_CONFIG=postgresql+psycopg2://postgres:postgres@localhost:5432/ett

# Folder with sample CSVs for this schema
SAMPLE_DIR=ett

# Base table whose CSV row count drives proportional scaling
BASE_TABLE_FOR_SAMPLE_OVERRIDE=ett_project

# Target rows for the base table; other tables scale from CSV ratios
TARGET_ROWS_PER_TABLE=100000

# Rows per insert batch (higher = faster but more memory)
BATCH_SIZE=50000

# If true: also profile existing rows already in the DB tables.
# For CSV-only profiling, keep this false and rely on SAMPLE_DIR above.
USE_EXISTING_DATA_PROFILE=false

# If true: after insert, run extra queries to report FK violations.
# Turning this off speeds up runs; the database still enforces FK constraints.
VALIDATE_FK=true

# If true: do NOT truncate; append after existing max PK values.
# If false: truncate all user tables before inserting synthetic data.
APPEND_MODE=false
```

Key variables:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` – basic Postgres connection settings used by the pipeline entrypoint.
- `DB_CONFIG` – full SQLAlchemy URL; if set, it overrides the basic connection settings and is used everywhere.
- `SAMPLE_DIR` – folder with CSVs for the active schema (e.g. `sample_data`, `dealer_db`, `ett`).
- `BASE_TABLE_FOR_SAMPLE_OVERRIDE` – base table name (e.g. `customer`, `dealer`, `ett_project`) that **has a CSV**; other tables scale from its row count.
- `TARGET_ROWS_PER_TABLE` – target rows for the base table; others are scaled from CSV ratios when overrides are enabled.
- `BATCH_SIZE` – number of rows inserted per batch (higher = faster but more memory).
- `USE_EXISTING_DATA_PROFILE` – `true`/`false`; profile live DB data when `true` (slower but more realistic).
- `VALIDATE_FK` – `true`/`false`; run an extra FK validation query after inserts.
- `APPEND_MODE` – `true`/`false`; append to existing data instead of truncating tables first.

To switch between schemas (finance / dealer / ett), create one block per schema
and keep only one profile uncommented at a time.

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
| finance (src, jdf)    | 100000                | 20000      | 1353.29        | 22.6 (~23)               |
| finance (src, jdf)    | 100000                | 20000      | 545.73         | 9.1                      |
| finance (src, jdf)    | 100000                | 50000      | 1049.31        | 17.5                     |
| dealer (src, dealer ) | 100000                | 20000      | 328.69         | 5.5                      |

Actual performance will vary with hardware, network latency to PostgreSQL, and whether `USE_EXISTING_DATA_PROFILE` is enabled.

For faster large runs (e.g. ~1M rows in the base table):
- Increase `TARGET_ROWS_PER_TABLE` (e.g. `1000000`).
- Use a larger `BATCH_SIZE` (e.g. `50000` or `100000` if memory allows).
- Keep `USE_EXISTING_DATA_PROFILE=false` to avoid extra DB scans.

-------------------------------------
### Finance schema detailed 100k/50k run

For `TARGET_ROWS_PER_TABLE=100000` and `BATCH_SIZE=50000`, the final row counts were:
`{'public.Branch': 19192, 'public.Customer': 100000, 'public.Merchant': 100000, 'public.Account': 302020, 'public.Card': 403030, 'public.Loan': 79798, 'public.Transaction': 504040, 'public.LoanPayment': 302020}` with `FK violations: {}` and `Pipeline execution time: 1049.31 seconds`.

-------------------------------------
### Dealer schema performance 

DB_CONFIG=postgresql+psycopg2://postgres:postgres@localhost:5432/dealer
SAMPLE_DIR=dealer_db
BASE_TABLE_FOR_SAMPLE_OVERRIDE=dealer
TARGET_ROWS_PER_TABLE=1000000
BATCH_SIZE=500000
USE_EXISTING_DATA_PROFILE=false
Row counts per table: {'public.dealer': 1000000, 'public.dealer_contract': 1000000, 'public.dealer_order': 2020408, 'public.dealer_region': 1000000, 'public.manufacturer': 1000000, 'public.product': 2020408}
FK violations: {}
Pipeline execution time: 4475.07 seconds = 01:14:35hr

### ETT schema performance (CSV-based, FK validation on)

Using ETT CSVs with `BASE_TABLE_FOR_SAMPLE_OVERRIDE=ett_project` and FK validation enabled:

| Workload       | TARGET_ROWS | BATCH_SIZE | BASE_TABLE_FOR_SAMPLE_OVERRIDE | FK validation | Time        |
|----------------|------------|-----------|---------------------------------|---------------|------------|
| ett (CSV, ETT) | 50000     | 100000    | ett_project                     | on            | 18.30 min   |
| ett (CSV, ETT) | 100000     | 50000     | ett_project                     | on            | 3.82 min    |
| ett (CSV, ETT) | 10000      | 5000      | ett_project                     | on            | 1.21 min    |
| ett (CSV, ETT) | 1000       | 500       | ett_project                     | on            | 7.71 sec    |

For the 500k run, the final row counts were:
`{'public.ett_org': 31250, 'public.ett_customer': 500000, 'public.ett_location': 62500, 'public.ett_project': 500000, 'public.ett_person': 93750, 'public.ett_task': 500000, 'public.ett_proj_team': 71034, 'public.ett_proj_timelog': 19657}` with `FK violations: {}` and `Pipeline execution time: 1098.08 seconds`.

For the 100k run, the final row counts were:
`{'public.ett_org': 6250, 'public.ett_customer': 100000, 'public.ett_location': 12500, 'public.ett_project': 100000, 'public.ett_person': 18750, 'public.ett_task': 100000, 'public.ett_proj_team': 14206, 'public.ett_proj_timelog': 4060}` with `FK violations: {}`.