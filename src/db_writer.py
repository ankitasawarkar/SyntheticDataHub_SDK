from typing import Dict
import pandas as pd
from sqlalchemy import create_engine, text


def write_to_postgres(data: Dict[str, pd.DataFrame],
                      host="localhost",
                      port=5432,
                      db="finance_synth",
                      user="postgres",
                      password="postgres",
                      append: bool = False):
    """Write generated dataframes to Postgres.

    The current behavior is to fully refresh the target tables
    on each run so that the pipeline can be re-run without
    primary key conflicts from previous data loads.
    """

    url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    engine = create_engine(url)

    # Truncate all involved tables before inserting new rows so that
    # deterministic primary keys (e.g. CUS_000001) do not clash with
    # existing data from previous runs.
    # In append mode, keep existing data and identities.
    table_names = list(data.keys())
    if table_names and not append:
        quoted = ", ".join(f'"{name}"' for name in table_names)
        truncate_sql = f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"
        print(f"[db_writer] Truncating tables before load: {quoted}")
        with engine.begin() as conn:
            conn.execute(text(truncate_sql))
    elif table_names and append:
        quoted = ", ".join(f'"{name}"' for name in table_names)
        print(f"[db_writer] Append mode: NOT truncating tables {quoted}")

    for table, df in data.items():
        df.to_sql(table, engine, if_exists="append", index=False)