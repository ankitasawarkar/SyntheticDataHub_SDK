from typing import Dict, Any, List, Optional

from psycopg2.extras import execute_batch

from .db import DBConfig, get_connection
from .generator import _table_id
from .ordering import plan_table_order


def _truncate_string_value(value: Any, max_length: Optional[int]) -> Any:
    if value is None:
        return None
    if max_length is None:
        return value
    if not isinstance(max_length, int) or max_length <= 0:
        return value
    s = str(value)
    if len(s) <= max_length:
        return value
    return s[:max_length]


def insert_synthetic_dataset(
    config: DBConfig,
    db_schema_list: List[Dict[str, Any]],
    synthetic_data: Dict[str, List[Dict[str, Any]]],
    batch_size: int = 1000,
) -> None:
    """Insert synthetic_data into Postgres following FK-safe order.

    Strings are truncated to each column's max_length just before insert.
    """
    ordered_tables = plan_table_order(db_schema_list)

    with get_connection(config) as conn:
        with conn.cursor() as cur:
            for t in ordered_tables:
                tid = _table_id(t)
                rows = synthetic_data.get(tid) or []
                if not rows:
                    continue

                columns = [c["name"] for c in t["columns"]]
                col_max = {c["name"]: c.get("max_length") for c in t["columns"]}

                # Quote schema, table, and column names to handle mixed-case
                # identifiers and reserved words safely.
                placeholders = ", ".join(["%s"] * len(columns))
                col_list_sql = ", ".join(f'"{c}"' for c in columns)
                sql = (
                    f'INSERT INTO "{t["schema"]}"."{t["table"]}" '
                    f'({col_list_sql}) VALUES ({placeholders})'
                )

                batch: List[tuple] = []
                for row in rows:
                    vals = []
                    for c in columns:
                        v = row.get(c)
                        if isinstance(v, str):
                            v = _truncate_string_value(v, col_max.get(c))
                        vals.append(v)
                    batch.append(tuple(vals))
                    if len(batch) >= batch_size:
                        execute_batch(cur, sql, batch)
                        batch = []
                if batch:
                    execute_batch(cur, sql, batch)
        conn.commit()
