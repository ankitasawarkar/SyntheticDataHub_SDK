from typing import Dict, Any, List

from .db import DBConfig, get_connection
from .generator import _table_id


def validate_referential_integrity(config: DBConfig, db_schema_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate FK constraints by checking for orphaned child rows.

    Returns a dict of violations per FK.
    """
    results: Dict[str, Any] = {}

    with get_connection(config) as conn:
        with conn.cursor() as cur:
            for t in db_schema_list:
                tid = _table_id(t)
                for fk in t["constraints"].get("foreign_keys", []):
                    child_cols = fk["columns"]
                    ref = fk["references"]
                    parent_schema = ref["schema"]
                    parent_table = ref["table"]
                    parent_cols = ref["columns"]

                    join_conditions = " AND ".join(
                        f'c."{c}" = p."{p}"' for c, p in zip(child_cols, parent_cols)
                    )
                    where_null = " AND ".join(f'c."{c}" IS NOT NULL' for c in child_cols)

                    sql = f"""
                    SELECT count(*) AS orphan_count
                    FROM "{t['schema']}"."{t['table']}" c
                    LEFT JOIN "{parent_schema}"."{parent_table}" p
                      ON {join_conditions}
                    WHERE {where_null} AND p."{parent_cols[0]}" IS NULL
                    """

                    cur.execute(sql)
                    row = cur.fetchone()
                    if isinstance(row, dict):
                        count = row.get("orphan_count", 0)
                    else:
                        count = row[0]
                    if count > 0:
                        key = f"{tid}:{','.join(child_cols)}->{parent_schema}.{parent_table}({','.join(parent_cols)})"
                        results[key] = {"orphan_count": count}

    return results
