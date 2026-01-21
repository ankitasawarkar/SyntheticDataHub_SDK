from typing import Dict, Any, List
from pathlib import Path

import pandas as pd

from .db import get_connection, DBConfig
from .generator import _table_id


def profile_existing_data(
    config: DBConfig,
    db_schema_list: List[Dict[str, Any]],
    max_categories: int = 50,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Profile existing data per column using live database rows.

    Returns profiles["schema.table"]["column_name"] with simple stats:
      - numeric: min, max
      - datetime: min, max
      - categorical: up to max_categories distinct values + frequencies
      - text: min_length, max_length
    """
    profiles: Dict[str, Dict[str, Dict[str, Any]]] = {}
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            for t in db_schema_list:
                tid = _table_id(t)
                table_profiles: Dict[str, Dict[str, Any]] = {}
                profiles[tid] = table_profiles

                for col in t["columns"]:
                    col_name = col["name"]
                    data_type = (col["data_type"] or "").lower()
                    udt_name = (col["udt_name"] or "").lower()
                    full_col = f'"{t["schema"]}"."{t["table"]}"."{col_name}"'

                    # Numeric (integer, numeric, floats)
                    if (
                        data_type
                        in (
                            "integer",
                            "bigint",
                            "smallint",
                            "numeric",
                            "decimal",
                            "double precision",
                            "real",
                        )
                        or udt_name
                        in ("int2", "int4", "int8", "numeric", "float4", "float8")
                    ):
                        sql = (
                            f"SELECT MIN({full_col}) AS min_val, MAX({full_col}) AS max_val "
                            f"FROM \"{t['schema']}\".\"{t['table']}\""
                        )
                        cur.execute(sql)
                        r = cur.fetchone() or {}
                        if r.get("min_val") is not None or r.get("max_val") is not None:
                            table_profiles[col_name] = {
                                "kind": "numeric",
                                "min": r.get("min_val"),
                                "max": r.get("max_val"),
                            }
                        continue

                    # Date / timestamp
                    if (
                        data_type
                        in (
                            "date",
                            "timestamp without time zone",
                            "timestamp with time zone",
                        )
                        or "timestamp" in udt_name
                        or udt_name == "date"
                    ):
                        sql = (
                            f"SELECT MIN({full_col}) AS min_val, MAX({full_col}) AS max_val "
                            f"FROM \"{t['schema']}\".\"{t['table']}\""
                        )
                        cur.execute(sql)
                        r = cur.fetchone() or {}
                        if r.get("min_val") is not None or r.get("max_val") is not None:
                            table_profiles[col_name] = {
                                "kind": "datetime",
                                "min": r.get("min_val"),
                                "max": r.get("max_val"),
                            }
                        continue

                    # Text-like
                    if any(x in data_type for x in ["character", "text"]) or udt_name in (
                        "text",
                    ):
                        # Distinct count first
                        sql = (
                            f"SELECT COUNT(DISTINCT {full_col}) AS ndist "
                            f"FROM \"{t['schema']}\".\"{t['table']}\""
                        )
                        cur.execute(sql)
                        r = cur.fetchone() or {}
                        ndist = r.get("ndist") or 0
                        if ndist and ndist <= max_categories:
                            # Capture distinct values with frequencies
                            sql = (
                                f"SELECT {full_col} AS value, COUNT(*) AS freq "
                                f"FROM \"{t['schema']}\".\"{t['table']}\" "
                                f"GROUP BY {full_col} ORDER BY freq DESC LIMIT {max_categories}"
                            )
                            cur.execute(sql)
                            values = []
                            for row in cur.fetchall() or []:
                                values.append(
                                    {
                                        "value": row.get("value"),
                                        "freq": row.get("freq"),
                                    }
                                )
                            if values:
                                table_profiles[col_name] = {
                                    "kind": "categorical",
                                    "values": values,
                                }
                                continue
                        # Fallback: length distribution
                        sql = (
                            f"SELECT MIN(LENGTH({full_col})) AS min_len, MAX(LENGTH({full_col})) AS max_len "
                            f"FROM \"{t['schema']}\".\"{t['table']}\""
                        )
                        cur.execute(sql)
                        r = cur.fetchone() or {}
                        if r.get("min_len") is not None or r.get("max_len") is not None:
                            table_profiles[col_name] = {
                                "kind": "text",
                                "min_length": r.get("min_len"),
                                "max_length": r.get("max_len"),
                            }

    return profiles


def profile_sample_data(
    db_schema_list: List[Dict[str, Any]],
    sample_dir: str = "sample_data",
    max_categories: int = 50,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Profile sample CSV data per column in a generic, schema-driven way.

    Reads <table>.csv files from sample_dir and returns the same stats structure
    used by profile_existing_data(), so generators can reuse it unchanged.
    """
    base = Path(sample_dir)
    if not base.exists():
        return {}

    # Map lower-case table name -> CSV path
    csv_by_table: Dict[str, Path] = {p.stem.lower(): p for p in base.glob("*.csv")}
    if not csv_by_table:
        return {}

    profiles: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for t in db_schema_list:
        tid = _table_id(t)
        table_profiles: Dict[str, Dict[str, Any]] = {}
        profiles[tid] = table_profiles

        tbl_lower = t["table"].lower()
        csv_path = csv_by_table.get(tbl_lower)
        if not csv_path:
            continue

        try:
            df = pd.read_csv(csv_path)
        except Exception:
            continue

        # If CSV was exported without a header, the first data row will
        # appear as column names. Detect this generically by checking
        # whether any real column names from the schema are present; if
        # none are, and the column counts match, re-read without header
        # and assign names from the schema.
        schema_col_names = [c["name"] for c in t["columns"]]
        if not any(name in df.columns for name in schema_col_names):
            try:
                df_no_header = pd.read_csv(csv_path, header=None)
                if df_no_header.shape[1] == len(schema_col_names):
                    df_no_header.columns = schema_col_names
                    df = df_no_header
            except Exception:
                # If this heuristic fails, fall back to the original df
                pass

        for col in t["columns"]:
            col_name = col["name"]
            if col_name not in df.columns:
                continue
            series = df[col_name].dropna()
            if series.empty:
                continue

            data_type = (col["data_type"] or "").lower()
            udt_name = (col["udt_name"] or "").lower()

            # Numeric
            if (
                data_type
                in (
                    "integer",
                    "bigint",
                    "smallint",
                    "numeric",
                    "decimal",
                    "double precision",
                    "real",
                )
                or udt_name
                in ("int2", "int4", "int8", "numeric", "float4", "float8")
            ):
                s_num = pd.to_numeric(series, errors="coerce").dropna()
                if not s_num.empty:
                    table_profiles[col_name] = {
                        "kind": "numeric",
                        "min": float(s_num.min()),
                        "max": float(s_num.max()),
                    }
                continue

            # Date / timestamp
            if (
                data_type
                in (
                    "date",
                    "timestamp without time zone",
                    "timestamp with time zone",
                )
                or "timestamp" in udt_name
                or udt_name == "date"
            ):
                s_dt = pd.to_datetime(series, errors="coerce").dropna()
                if not s_dt.empty:
                    table_profiles[col_name] = {
                        "kind": "datetime",
                        "min": s_dt.min().isoformat(),
                        "max": s_dt.max().isoformat(),
                    }
                continue

            # Text-like
            s_str = series.astype(str)
            ndist = s_str.nunique(dropna=True)
            if ndist and ndist <= max_categories:
                vc = s_str.value_counts()
                values = []
                for v, freq in vc.items():
                    values.append({"value": v, "freq": int(freq)})
                if values:
                    table_profiles[col_name] = {
                        "kind": "categorical",
                        "values": values,
                    }
                    continue
            lengths = s_str.str.len().dropna()
            if not lengths.empty:
                table_profiles[col_name] = {
                    "kind": "text",
                    "min_length": int(lengths.min()),
                    "max_length": int(lengths.max()),
                }

    return profiles
