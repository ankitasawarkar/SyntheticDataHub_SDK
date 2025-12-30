
## Project Overview

This project is a small SDK + CLI for generating realistic synthetic banking data (customers, accounts, cards, loans, transactions) and loading it into Postgres. It is intended for demos, testing, and analytics without using real customer data.

### Main technologies

- Python for the CLI and core logic (`pandas`, `Faker`, `psycopg2`, `SQLAlchemy`).
- Postgres as the target database.
- Docker + Docker Compose to run Postgres and the SDK as containers.

### How the data model is defined

- An EDL file (`edl/edl_schema.edl`) defines tables, fields, primary keys, and foreign keys.
- The SDK parses this EDL into an in-memory metadata model and then:
  - Generates SQL DDL to create tables and constraints in Postgres.
  - Builds a JSON generator config with rules for synthesizing each column.

### How synthetic data is generated

- For each table, the synthetic generator:
  - Creates deterministic IDs (e.g., `CUS_000001`) with optional offsets for append mode.
  - Uses Faker and simple rules to generate names, dates, timestamps, and realistic numeric amounts.
  - Applies relationships so foreign keys (customer → account → transaction, loan → loan payments) are consistent.

### What the `pipeline` command does

The `pipeline` CLI command runs the full flow end-to-end:

1. Load or update the schema in Postgres from the EDL.
2. Build the generator config JSON.
3. Generate synthetic dataframes for each table.
4. Write data into Postgres, either as a full refresh or in append mode (with safe PK offsets).
5. Run validation on primary keys, foreign keys, required fields, and allowed values.

---

## High‑Level Pipeline Overview

The system follows this flow:

EDL → Metadata → DDL → Postgres Schema → Generator Config → Synthetic Data → Insert → Validate

Or visually:

EDL file
   ↓
EDL Parser (extract tables, fields, PK/FK)
   ↓
Metadata Model (in-memory representation)
   ↓
DDL Generator (CREATE TABLE + FK)
   ↓
Schema Loader (executes DDL in Postgres)
   ↓
Generator Config (JSON rules for synthetic data)
   ↓
Synthetic Generator (Faker-based multi-table)
   ↓
DB Writer (insert into Postgres)
   ↓
Validation (PK/FK integrity checks)

Everything is runnable locally with just Docker + Python.

---

## Quickstart (CLI)

### 1. Start Postgres

```bash

```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Load schema

```bash
python -m src.cli init_schema
```

This runs:
- `edl_parser.py`
- `ddl_generator.py`
- `schema_loader.py`

Result: Postgres now has all tables and constraints.

### 4. Build generator config

```bash
python -m src.cli build_config
```

This runs:
- `edl_parser.py`
- `generator_config.py`

Result: `schema_config.json` created.

### 5. Generate synthetic data and insert into Postgres

```bash
python -m src.cli generate --rows 5000
```

This runs:
- `synthetic_generator.py`
- `db_writer.py`

Result: synthetic data inserted into Postgres.

### 6. Validate

```bash
python -m src.cli validate
```

This runs:
- `validation.py`

Result: PK/FK and basic data quality report.

---

## NeMo Data Designer troubleshooting

If you are using the NeMo-backed EDL pipeline (`edl_nemo`), these helper scripts can be used to verify that the NeMo service and credentials are working:

- Healthcheck script: `scripts/nemo_healthcheck.sh`
   - Checks the `/health` endpoint at `${NEMO_BASE_URL:-http://localhost:8000}` and exits with status 0 on success.
   - Example (from repo root, in Bash / Git Bash / WSL):

      ```bash
      bash scripts/nemo_healthcheck.sh
      ```

- Local API test: `scripts/test_nemo_local.py`
   - Sends a small test `generate` request to `${NEMO_BASE_URL:-http://localhost:8000}/data-designer/v1/generate` using `NEMO_API_KEY` from your environment.
   - Prints the HTTP status and response body/JSON for quick debugging.
   - Example:

      ```bash
      python scripts/test_nemo_local.py
      ```

Make sure you have `NEMO_BASE_URL` and `NEMO_API_KEY` set in your environment (for example via the `.env` file) before running the NeMo pipelines or these scripts.

### 401 errors when pulling the NeMo container

If `docker compose pull nemo-data-designer` (or `docker pull nvcr.io/nvidia/nemo-microservices/data-designer:...`) fails with a `401 Unauthorized` error, it means Docker does not have permission to access the NeMo image in the NVIDIA registry:

- You need a valid NGC/NVIDIA account with access to the NeMo Data Designer image.
- Sign in and run `docker login nvcr.io` using your NGC credentials or generated API token.
- Make sure the image name and tag in `docker-compose.yml` match exactly what your organization or NVIDIA docs specify.

Until the registry authentication and image name are correct, the NeMo container will not start, and all NeMo-based pipelines (`edl_nemo`) will fail with connection errors to `localhost:8000`. Once the image pulls and the container is running and healthy, you can rerun `python test_nemo_local.py` and then the `edl_nemo` pipeline to generate data.
