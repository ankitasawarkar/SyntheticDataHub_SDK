from typing import Dict, Any, List, Set

from .db import get_connection, DBConfig


def plan_table_order(db_schema_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return tables in an order where parents come before children (FK-aware).

    Used for generation (parents first) and truncation (children first when reversed).
    """
    table_by_id: Dict[str, Dict[str, Any]] = {}
    for t in db_schema_list:
        tid = f"{t['schema']}.{t['table']}"
        table_by_id[tid] = t

    graph: Dict[str, Set[str]] = {tid: set() for tid in table_by_id.keys()}
    indegree: Dict[str, int] = {tid: 0 for tid in table_by_id.keys()}

    for t in db_schema_list:
        child_id = f"{t['schema']}.{t['table']}"
        for fk in t["constraints"].get("foreign_keys", []):
            parent_id = f"{fk['references']['schema']}.{fk['references']['table']}"
            if parent_id == child_id:
                continue
            if parent_id in graph and child_id in graph:
                if child_id not in graph[parent_id]:
                    graph[parent_id].add(child_id)
                    indegree[child_id] += 1

    from collections import deque

    queue: "deque[str]" = deque([tid for tid, deg in indegree.items() if deg == 0])
    ordered_ids: List[str] = []

    while queue:
        tid = queue.popleft()
        ordered_ids.append(tid)
        for child in graph[tid]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if len(ordered_ids) != len(table_by_id):
        remaining = [tid for tid in table_by_id.keys() if tid not in ordered_ids]
        ordered_ids.extend(remaining)

    return [table_by_id[tid] for tid in ordered_ids]


def truncate_all_synthetic_tables(config: DBConfig, db_schema_list: List[Dict[str, Any]]) -> None:
    """Truncate all known tables in a FK-safe order (children first)."""
    ordered_tables = plan_table_order(db_schema_list)
    ordered_tables = list(reversed(ordered_tables))
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            for t in ordered_tables:
                schema = t["schema"]
                table = t["table"]
                sql = f'TRUNCATE TABLE "{schema}"."{table}" RESTART IDENTITY CASCADE'
                cur.execute(sql)
        # Explicitly commit the truncation transaction so that all tables are
        # truly emptied before we start inserting synthetic rows.
        conn.commit()
    print("Truncated all user tables (FK-safe order).")
