import time
import psycopg2
from psycopg2 import OperationalError
from metadata_model import SchemaMeta
from ddl_generator import generate_ddl, generate_fk_constraints

def load_schema_to_postgres(schema: SchemaMeta,
                            host="localhost",
                            port=5432,
                            db="finance_synth",
                            user="postgres",
                            password="postgres"):
    # Wait for Postgres to be ready (useful when running in Docker)
    max_attempts = 10
    delay_seconds = 3
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[schema_loader] Connecting to Postgres (attempt {attempt}/{max_attempts})...")
            conn = psycopg2.connect(
                host=host, port=port, dbname=db, user=user, password=password
            )
            break
        except OperationalError as exc:
            if attempt == max_attempts:
                print("[schema_loader] Failed to connect to Postgres after multiple attempts.")
                raise
            print(f"[schema_loader] Postgres not ready yet: {exc}. Retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)

    conn.autocommit = True
    cur = conn.cursor()

    ddls = generate_ddl(schema)
    for table_name, sql in ddls.items():
        cur.execute(sql)

    fk_ddls = generate_fk_constraints(schema)
    for name, sql in fk_ddls.items():
        try:
            cur.execute(sql)
        except psycopg2.Error:
            # e.g., if FK already exists in reruns
            pass

    cur.close()
    conn.close()