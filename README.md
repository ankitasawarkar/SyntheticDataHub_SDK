
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

You can either run Postgres locally or use Docker. The easiest is Docker:

```bash
docker compose up -d postgres
```

This starts a Postgres 15 container with database `finance_synth` and user/password `postgres/postgres`.

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

## Run Everything with Docker

You can also run the full pipeline (schema init + config + generate + load + validate) entirely inside Docker using the provided `docker-compose.yml`.

### 1. Build and start services

```bash
docker compose up --build
```

This will:
- Start a Postgres container (`finance-postgres`) on port `5432`.
- Build the SDK image from the Dockerfile.
- Run the `pipeline` CLI subcommand in the `sdk` container with default settings (EDL, config, 1000 rows).

### 2. Check logs

```bash
docker compose logs -f sdk
```

You should see logs for schema creation, data generation, inserts, and validation.

### 3. Connect to Postgres from host

With Docker running, you can connect using any Postgres client on your machine:

- Host: `localhost`
- Port: `5432`
- Database: `finance_synth`
- User: `postgres`
- Password: `postgres`

### 4. Clean up containers and volume

```bash
docker compose down -v
```

This stops containers and removes the `pgdata` volume used for Postgres data.
