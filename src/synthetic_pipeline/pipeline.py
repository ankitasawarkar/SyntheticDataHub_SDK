from typing import Dict, Any, List, Optional

from .db import DBConfig, get_connection
from .schema import fetch_db_schema
from .profiling import profile_existing_data, profile_sample_data
from .ordering import truncate_all_synthetic_tables, plan_table_order
from .generator import generate_synthetic_dataset, _table_id
from .insert import insert_synthetic_dataset
from .validation import validate_referential_integrity
from .overrides import build_rows_per_table_override_from_sample
import time
import re


def _build_profiles(
    config: DBConfig,
    db_schema_list: List[Dict[str, Any]],
    use_existing_data_profile: bool = False,
    sample_dir: Optional[str] = None,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Build column profiles from existing DB data and/or sample CSVs.

    This wraps profile_existing_data and profile_sample_data so pipeline
    entrypoints have a single place to maintain profiling logic.
    """
    profiles: Dict[str, Dict[str, Dict[str, Any]]] = {}

    if use_existing_data_profile:
        existing_stats = profile_existing_data(config, db_schema_list)
        for tid, cols in existing_stats.items():
            profiles.setdefault(tid, {}).update(cols)

    if sample_dir is not None:
        sample_stats = profile_sample_data(db_schema_list, sample_dir=sample_dir)
        for tid, cols in sample_stats.items():
            profiles.setdefault(tid, {}).update(cols)

    return profiles


def _bootstrap_pk_counters_for_append(
    config: DBConfig,
    db_schema_list: List[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    """Inspect existing data to initialize PK counters for append mode.

    For each table and PK column, this looks at the current maximum value
    in the database and returns counters so the generator will continue
    from max+1, avoiding collisions when we do not truncate first.

    Supports:
    - Integer-like PKs (smallint / int / bigint)
    - Text/varchar PKs that end with a numeric suffix, e.g. COL_000123
    """
    pk_counters: Dict[str, Dict[str, int]] = {}

    with get_connection(config) as conn:
        cur = conn.cursor()
        for t in db_schema_list:
            tid = _table_id(t)
            table_pk: Dict[str, int] = {}

            pk_constraints = t["constraints"].get("primary_keys", [])
            if not pk_constraints:
                continue

            for pk in pk_constraints:
                for cname in pk.get("columns", []):
                    col_meta = next(
                        (c for c in t["columns"] if c["name"] == cname),
                        None,
                    )
                    if not col_meta:
                        continue

                    data_type = (col_meta.get("data_type") or "").lower()
                    udt_name = (col_meta.get("udt_name") or "").lower()
                    full_col = f'"{t["schema"]}"."{t["table"]}"."{cname}"'
                    sql = (
                        f"SELECT MAX({full_col}) AS max_val "
                        f"FROM \"{t['schema']}\".\"{t['table']}\""
                    )

                    try:
                        cur.execute(sql)
                        r = cur.fetchone() or {}
                    except Exception:
                        continue

                    max_val = r.get("max_val")
                    if max_val is None:
                        continue

                    # Integer-like PKs: use max_int directly.
                    if data_type in ("integer", "bigint", "smallint") or udt_name in (
                        "int2",
                        "int4",
                        "int8",
                    ):
                        try:
                            table_pk[cname] = int(max_val)
                        except (TypeError, ValueError):
                            pass
                        continue

                    # Text/varchar PKs: if they end with digits, treat the
                    # trailing number as a counter (e.g. COL_000123).
                    if (
                        "char" in data_type
                        or "text" in data_type
                        or udt_name == "text"
                    ):
                        m = re.search(r"(\d+)$", str(max_val))
                        if m:
                            try:
                                table_pk[cname] = int(m.group(1))
                            except ValueError:
                                pass

            if table_pk:
                pk_counters[tid] = table_pk

    return pk_counters

def run_synthetic_pipeline(
    config: DBConfig,
    rows_per_table: int = 100,
    rows_per_table_override: Optional[Dict[str, int]] = None,
    use_existing_data_profile: bool = False,
    sample_dir: Optional[str] = None,
    truncate_before_insert: bool = True,
    validate_fk: bool = True,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """High-level one-shot pipeline (non-batched).

    1. Discover schema.
    2. Optionally profile existing DB data and/or sample CSVs.
    3. Optionally truncate tables.
    4. Generate synthetic rows in memory.
    5. Insert into Postgres.
    6. Optionally validate FK integrity.
    """
    db_schema_list = fetch_db_schema(config)

    profiles = _build_profiles(
        config=config,
        db_schema_list=db_schema_list,
        use_existing_data_profile=use_existing_data_profile,
        sample_dir=sample_dir,
    )

    if truncate_before_insert:
        truncate_all_synthetic_tables(config, db_schema_list)

    synthetic_data = generate_synthetic_dataset(
        db_schema_list=db_schema_list,
        rows_per_table=rows_per_table,
        rows_per_table_override=rows_per_table_override,
        seed=seed,
        column_profiles=profiles or None,
    )

    insert_synthetic_dataset(config, db_schema_list, synthetic_data)

    fk_result = None
    if validate_fk:
        fk_result = validate_referential_integrity(config, db_schema_list)

    return {
        "schema": db_schema_list,
        "profiles": profiles,
        "synthetic_data": synthetic_data,
        "fk_violations": fk_result,
    }


def run_synthetic_pipeline_batched(
    config: DBConfig,
    target_rows_per_table: int = 100,
    rows_per_table_override: Optional[Dict[str, int]] = None,
    batch_size: int = 10_000,
    use_existing_data_profile: bool = False,
    sample_dir: Optional[str] = None,
    truncate_before_insert: bool = True,
    validate_fk: bool = True,
    seed: Optional[int] = None,
    base_table_for_override: Optional[str] = None,
    append_mode: bool = False,
) -> Dict[str, Any]:
    """Batched version of the pipeline: generates and inserts in chunks.

    Keeps only one batch of rows in memory at a time.
    """
    import random
    from faker import Faker

    if seed is not None:
        random.seed(seed)
        Faker.seed(seed)

    print("[pipeline] Discovering schema and planning FK-safe order...")
    db_schema_list = fetch_db_schema(config)
    ordered_tables = plan_table_order(db_schema_list)

    # Log the FK-safe table order once so it's clear which table is
    # treated as the root and how children follow their parents.
    ordered_ids = [
        _table_id(t) for t in ordered_tables
    ]
    print("[pipeline] FK-safe table order:", ", ".join(ordered_ids))

    profiles = _build_profiles(
        config=config,
        db_schema_list=db_schema_list,
        use_existing_data_profile=use_existing_data_profile,
        sample_dir=sample_dir,
    )

    # Optionally derive per-table row targets from sample CSVs if requested.
    if (
        sample_dir is not None
        and rows_per_table_override is None
        and base_table_for_override
    ):
        try:
            rows_per_table_override = build_rows_per_table_override_from_sample(
                db_schema_list=db_schema_list,
                sample_dir=sample_dir,
                base_table=base_table_for_override,
                target_rows_for_base=target_rows_per_table,
            )
            print(
                f"[pipeline] Using rows_per_table_override based on sample data (base_table={base_table_for_override})."
            )
        except Exception as exc:
            print(
                f"[pipeline] WARNING: failed to build rows_per_table_override from sample data: {exc}. "
                "Falling back to uniform target_rows_per_table."
            )

    if truncate_before_insert:
        print("[pipeline] Truncating all user tables (FK-safe order)...")
        truncate_all_synthetic_tables(config, db_schema_list)

    accumulated_counts: Dict[str, int] = {}
    parent_rows_cache: Dict[str, List[Dict[str, Any]]] = {}

    # In truncate mode we start PK counters from zero. In append mode we
    # inspect existing data and start counters at the current max so we
    # can safely append rows without clashing with existing PKs.
    if append_mode:
        pk_counters: Dict[str, Dict[str, int]] = _bootstrap_pk_counters_for_append(
            config, db_schema_list
        )
    else:
        pk_counters: Dict[str, Dict[str, int]] = {}

    # Track which columns must be unique (PK + UNIQUE constraints) per table,
    # and the set of values already used for those columns across all batches.
    unique_cols_map: Dict[str, set] = {}
    unique_tuple_constraints: Dict[str, List[Dict[str, Any]]] = {}
    for _t in db_schema_list:
        _tid = _table_id(_t)

        # Only enforce per-column uniqueness for *single-column* PK/UNIQUE
        # constraints. Composite keys are enforced via tuple constraints;
        # treating each column as unique would incorrectly over-constrain
        # things like date fields that are only unique in combination.
        _unique_cols: set = set()

        tuple_constraints: List[Dict[str, Any]] = []
        for _pk in _t["constraints"].get("primary_keys", []):
            cols = list(_pk.get("columns", []))
            if cols:
                tuple_constraints.append({"name": _pk.get("name") or "pk", "columns": cols})
                if len(cols) == 1:
                    _unique_cols.add(cols[0])
        for _uq in _t["constraints"].get("uniques", []):
            cols = list(_uq.get("columns", []))
            if cols:
                tuple_constraints.append({"name": _uq.get("name") or "uniq", "columns": cols})
                if len(cols) == 1:
                    _unique_cols.add(cols[0])

        unique_cols_map[_tid] = _unique_cols
        unique_tuple_constraints[_tid] = tuple_constraints

    used_unique_values: Dict[str, Dict[str, set]] = {}
    used_unique_tuples: Dict[str, Dict[str, set]] = {}

    # Precompute which parent columns are referenced by any FK so we can
    # build value -> rows indexes for fast lookup in the hot path. This
    # stays fully generic: it is driven only by FK metadata, not table
    # names.
    parent_index_cols: Dict[str, set] = {}
    for t in db_schema_list:
        for fk in t["constraints"].get("foreign_keys", []):
            parent_tid = f"{fk['references']['schema']}.{fk['references']['table']}"
            for parent_col in fk["references"]["columns"]:
                parent_index_cols.setdefault(parent_tid, set()).add(parent_col)

    # parent_tid -> parent_col -> value -> [parent_row, ...]
    parent_indexes: Dict[str, Dict[str, Dict[Any, List[Dict[str, Any]]]]] = {}

    from .generator import _generate_scalar_value

    import math
    from .insert import insert_synthetic_dataset as _insert

    print("[pipeline] Starting batched synthetic load...")

    for t in ordered_tables:
        tid = _table_id(t)
        cols = t["columns"]
        constraints = t["constraints"]

        pk_counters.setdefault(tid, {})
        used_unique_values.setdefault(tid, {})
        used_unique_tuples.setdefault(tid, {})
        table_unique_cols = unique_cols_map.get(tid, set())

        target_rows = (
            rows_per_table_override.get(tid, target_rows_per_table)
            if rows_per_table_override
            else target_rows_per_table
        )

        total_batches = max(1, math.ceil(target_rows / batch_size))

        print(f"[pipeline] Table {tid}: target_rows={target_rows}, batch_size={batch_size}, total_batches={total_batches}")

        accumulated_counts[tid] = 0

        for _ in range(total_batches):
            remaining = target_rows - accumulated_counts[tid]
            if remaining <= 0:
                break
            this_batch = min(batch_size, remaining)

            batch_rows: List[Dict[str, Any]] = []

            fk_constraints = constraints.get("foreign_keys", [])
            fk_child_cols = {c for fk in fk_constraints for c in fk["columns"]}
            pk_cols: List[str] = []
            for pk in constraints.get("primary_keys", []):
                pk_cols.extend(pk["columns"])

            for _ in range(this_batch):
                row: Dict[str, Any] = {}

                # Foreign keys
                #
                # Some tables have multiple FKs that share child columns
                # (for example, org_cd appearing in more than one composite
                # foreign key). If we naively assign FK values, a later FK
                # can overwrite a child column that was already populated
                # from a different parent, producing combinations that don't
                # actually exist in any parent table and causing FK
                # violations at insert time.
                #
                # To keep things generic and robust:
                # - If a child column already has a value, we filter the
                #   candidate parent rows so the referenced column matches
                #   that value.
                # - When applying an FK, we never overwrite an existing
                #   child column; we only fill missing ones.
                # - If no compatible parent exists for a given FK (i.e. no
                #   parent row matches the already-populated child values),
                #   we skip this synthetic row entirely instead of falling
                #   back to an invalid combination that would break FKs.
                valid_fk_combo = True
                for fk in fk_constraints:
                    parent_tid = f"{fk['references']['schema']}.{fk['references']['table']}"
                    parent_rows = parent_rows_cache.get(parent_tid) or []
                    if not parent_rows:
                        continue

                    # Use prebuilt parent_indexes whenever a child column
                    # is already set so we avoid scanning all parent rows.
                    table_indexes = parent_indexes.get(parent_tid, {})
                    candidates: Optional[List[Dict[str, Any]]] = None

                    for child_col, parent_col in zip(
                        fk["columns"], fk["references"]["columns"]
                    ):
                        if child_col in row:
                            val = row[child_col]
                            idx_for_col = table_indexes.get(parent_col)
                            if idx_for_col is not None:
                                # Fast path: direct dictionary lookup
                                c = idx_for_col.get(val, [])
                            else:
                                # Fallback: filter existing candidates (or all parents)
                                base = candidates if candidates is not None else parent_rows
                                c = [pr for pr in base if pr.get(parent_col) == val]

                            if not c:
                                candidates = []
                                break

                            candidates = c

                    # If no child column constrained this FK, fall back to
                    # using all parent rows as candidates.
                    if candidates is None:
                        candidates = parent_rows

                    if not candidates:
                        valid_fk_combo = False
                        break

                    parent_row = random.choice(candidates)

                    for child_col, parent_col in zip(
                        fk["columns"], fk["references"]["columns"]
                    ):
                        if child_col in row:
                            continue
                        row[child_col] = parent_row[parent_col]

                if not valid_fk_combo:
                    continue

                for col in cols:
                    cname = col["name"]
                    if cname in row:
                        continue

                    data_type = (col.get("data_type") or "").lower()
                    udt_name = (col.get("udt_name") or "").lower()

                    # Integer primary key columns: generate sequential IDs
                    # per table/column so we never hit duplicate PKs, even in
                    # batched mode. This is generic and does not depend on
                    # specific table names.
                    if cname in pk_cols and data_type in (
                        "integer",
                        "bigint",
                        "smallint",
                    ):
                        c = pk_counters[tid].get(cname, 0) + 1
                        pk_counters[tid][cname] = c
                        row[cname] = c
                        continue

                    # Text/varchar primary key columns: generate a deterministic
                    # pattern-based ID (e.g. BRANCH_ID_000001) instead of relying
                    # on Faker. This guarantees no duplicate PKs for text IDs like
                    # branch_id, customer_id, etc.
                    if cname in pk_cols and (
                        "char" in data_type
                        or "text" in data_type
                        or udt_name == "text"
                    ):
                        c = pk_counters[tid].get(cname, 0) + 1
                        pk_counters[tid][cname] = c
                        base = cname.upper()[:10] or "COL"
                        value = f"{base}_{c:06d}"
                        max_l = col.get("max_length")
                        if isinstance(max_l, int) and max_l > 0:
                            value = value[:max_l]
                        row[cname] = value
                        continue

                    # For FK columns, only use values copied from parents.
                    # If no parent was chosen (e.g. self-referential FK and
                    # this is the first batch), leave as NULL instead of
                    # generating a random UUID/integer that will violate the
                    # constraint.
                    if cname in fk_child_cols:
                        continue

                    # For PK/UNIQUE columns, do not use profiling stats (to
                    # avoid reusing categorical IDs); enforce uniqueness using
                    # in-memory tracking across all batches.
                    col_stats = None
                    if cname not in table_unique_cols:
                        col_stats = profiles.get(tid, {}).get(cname)

                    value = _generate_scalar_value(col, stats=col_stats)

                    if cname in table_unique_cols and cname not in pk_cols:
                        used_for_table = used_unique_values[tid].setdefault(cname, set())
                        attempts = 0
                        max_attempts = 10
                        while (value is None or value in used_for_table) and attempts < max_attempts:
                            value = _generate_scalar_value(col, stats=None)
                            attempts += 1

                        if value is None or value in used_for_table:
                            data_type = (col.get("data_type") or "").lower()
                            udt = (col.get("udt_name") or "").lower()
                            suffix = len(used_for_table) + 1
                            if data_type in ("integer", "bigint", "smallint") or udt in (
                                "int2",
                                "int4",
                                "int8",
                            ):
                                value = suffix
                            else:
                                base = cname.upper()[:10] or "COL"
                                value = f"{base}_{suffix:06d}"
                                max_l = col.get("max_length")
                                if isinstance(max_l, int) and max_l > 0:
                                    value = value[:max_l]

                        used_for_table.add(value)

                    row[cname] = value

                # Enforce composite uniqueness (PK and UNIQUE constraints
                # that span one or more columns) generically. This prevents
                # duplicate tuples like (org_cd, proj_cd, prsn_cd) for
                # ett_proj_team without hard-coding any table names.
                tuple_defs = unique_tuple_constraints.get(tid, [])
                if tuple_defs:
                    ok = True
                    for uc in tuple_defs:
                        cols_tuple = uc.get("columns", [])
                        key_name = uc.get("name") or ",".join(cols_tuple)
                        values = tuple(row.get(c) for c in cols_tuple)
                        # Only enforce when all columns are non-NULL
                        if any(v is None for v in values):
                            continue
                        used_for_uc = used_unique_tuples[tid].setdefault(key_name, set())
                        if values in used_for_uc:
                            ok = False
                            break
                    if not ok:
                        # Skip this row; it would violate a PK/UNIQUE tuple
                        # we've already emitted for this table.
                        continue
                    # Record tuples now that the row is accepted
                    for uc in tuple_defs:
                        cols_tuple = uc.get("columns", [])
                        key_name = uc.get("name") or ",".join(cols_tuple)
                        values = tuple(row.get(c) for c in cols_tuple)
                        if any(v is None for v in values):
                            continue
                        used_for_uc = used_unique_tuples[tid].setdefault(key_name, set())
                        used_for_uc.add(values)

                batch_rows.append(row)

            synthetic_data_single = {tid: batch_rows}
            _insert(config, [t], synthetic_data_single, batch_size=batch_size)
            accumulated_counts[tid] += len(batch_rows)

            parent_rows = parent_rows_cache.get(tid, []) + batch_rows
            parent_rows_cache[tid] = parent_rows

            # Rebuild value indexes for this parent table so subsequent
            # child tables can do O(1) lookups by referenced column value
            # instead of scanning all parent rows.
            index_cols = parent_index_cols.get(tid)
            if index_cols:
                table_index: Dict[str, Dict[Any, List[Dict[str, Any]]]] = {}
                for pr in parent_rows:
                    for col_name in index_cols:
                        val = pr.get(col_name)
                        table_index.setdefault(col_name, {}).setdefault(val, []).append(pr)
                parent_indexes[tid] = table_index

            print(
                f"[pipeline] Table {tid}: batch inserted {len(batch_rows)} rows, "
                f"cumulative={accumulated_counts[tid]}/{target_rows}"
            )

    fk_result = None
    if validate_fk:
        fk_result = validate_referential_integrity(config, db_schema_list)

    return {
        "schema": db_schema_list,
        "profiles": profiles,
        "row_counts": accumulated_counts,
        "fk_violations": fk_result,
    }


def main() -> None:
    """Convenience entrypoint to run the batched pipeline.

    Reads DB connection and basic options from environment variables, then
    calls run_synthetic_pipeline_batched.

    Environment variables (with defaults):
    - DB_HOST (default: "localhost")
    - DB_PORT (default: "5432")
    - DB_NAME (default: "postgres")
    - DB_USER (default: "postgres")
    - DB_PASSWORD (default: empty)
    - TARGET_ROWS_PER_TABLE (default: "1000")
    - BATCH_SIZE (default: "20000")
    - USE_EXISTING_DATA_PROFILE ("true"/"false", default: "false")
    - SAMPLE_DIR (path to folder with sample CSVs, optional)
    - APPEND_MODE ("true"/"false", default: "false")
    """
    import os

    # Try to load environment variables from a .env file if present
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        # If python-dotenv is not installed or .env is missing, just continue
        pass

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    dbname = os.getenv("DB_NAME", "inventory")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")

    target_rows_per_table = int(os.getenv("TARGET_ROWS_PER_TABLE", "100000"))
    batch_size = int(os.getenv("BATCH_SIZE", "20000"))

    use_existing_data_profile_env = os.getenv("USE_EXISTING_DATA_PROFILE", "false").lower()
    use_existing_data_profile = use_existing_data_profile_env in ("1", "true", "yes")

    validate_fk_env = os.getenv("VALIDATE_FK", "true").lower()
    validate_fk = validate_fk_env in ("1", "true", "yes")

    append_mode_env = os.getenv("APPEND_MODE", "false").lower()
    append_mode = append_mode_env in ("1", "true", "yes")

    sample_dir = os.getenv("SAMPLE_DIR") or None
    base_table_for_override = os.getenv("BASE_TABLE_FOR_SAMPLE_OVERRIDE") or None

    config = DBConfig(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )
    
    start_time = time.perf_counter()
    result = run_synthetic_pipeline_batched(
        config=config,
        target_rows_per_table=target_rows_per_table,
        rows_per_table_override=None,
        batch_size=batch_size,
        use_existing_data_profile=use_existing_data_profile,
        sample_dir=sample_dir,
        truncate_before_insert=not append_mode,
        validate_fk=validate_fk,
        seed=42,
        base_table_for_override=base_table_for_override,
        append_mode=append_mode,
    )

    print("Synthetic data generation completed.")
    print("Row counts per table:", result.get("row_counts"))
    print("FK violations:", result.get("fk_violations"))
    end_time = time.perf_counter()
    execution_time_seconds = end_time - start_time
    print(f"Pipeline execution time: {execution_time_seconds:.2f} seconds")

if __name__ == "__main__":
    main()
