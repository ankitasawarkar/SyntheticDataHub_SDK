from typing import Dict, Any, List
import os

import pandas as pd

from .generator import _table_id


def build_rows_per_table_override_from_sample(
    db_schema_list: List[Dict[str, Any]],
    sample_dir: str,
    base_table: str,
    target_rows_for_base: int,
) -> Dict[str, int]:
    """Infer rows_per_table_override from CSV row counts.

    - CSV files are expected to be named `<table>.csv` inside `sample_dir`.
    - `base_table` can be either `schema.table` or just `table` (case-insensitive).
    - All other tables are scaled proportionally to the base table's count.
    """
    counts: Dict[str, int] = {}
    table_name_to_tid: Dict[str, str] = {}  # lower(table_name) -> tid
    for t in db_schema_list:
        tid = _table_id(t)  # schema.table
        csv_name = f"{t['table']}.csv"
        csv_path = os.path.join(sample_dir, csv_name)
        if not os.path.exists(csv_path):
            continue
        df = pd.read_csv(csv_path)
        counts[tid] = len(df)
        table_name_to_tid[t["table"].lower()] = tid

    # Resolve base_table to a full table id (schema.table) if needed
    resolved_base = base_table
    if resolved_base not in counts:
        # Try matching by bare table name (case-insensitive)
        if "." not in base_table:
            base_name = base_table.lower()
            matches = [tid for name, tid in table_name_to_tid.items() if name == base_name]
            if len(matches) == 1:
                resolved_base = matches[0]
            elif len(matches) > 1:
                raise ValueError(
                    f"Base table '{base_table}' is ambiguous; candidates: {', '.join(matches)}. "
                    "Please use 'schema.table' format.",
                )

    if resolved_base not in counts:
        raise ValueError(
            f"Base table {base_table} has no sample CSV in {sample_dir}. "
            f"Available tables with CSV: {', '.join(sorted(counts.keys()))}",
        )

    base_count = counts[resolved_base]
    if base_count <= 0:
        raise ValueError(f"Base table {resolved_base} has zero rows in sample")

    factor = target_rows_for_base / base_count

    override: Dict[str, int] = {}
    for tid, c in counts.items():
        override[tid] = max(1, int(round(c * factor)))

    return override
