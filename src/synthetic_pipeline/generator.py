from typing import Dict, Any, List, Optional
import random
from decimal import Decimal
import uuid

from faker import Faker


fake = Faker()


def _table_id(t: Dict[str, Any]) -> str:
    return f"{t['schema']}.{t['table']}"


def _generate_scalar_value(col: Dict[str, Any], stats: Optional[Dict[str, Any]] = None) -> Any:
    """Generate a single scalar value for a column using Faker + simple heuristics.

    Uses optional stats from profiling to stay within realistic ranges, and respects
    numeric precision/scale for numeric/decimal types.
    """
    name = col["name"].lower()
    data_type = (col["data_type"] or "").lower()
    udt_name = (col["udt_name"] or "").lower()
    max_len = col.get("max_length") or 64

    # Occasionally emit NULL for nullable columns
    if col.get("is_nullable") and random.random() < 0.05:
        return None

    # UUID columns: always generate a UUID, ignore stats
    if data_type == "uuid" or udt_name == "uuid":
        return str(uuid.uuid4())

    # If we have profiling stats, try to use them first, but only in a
    # type-consistent way so we don't violate column types.
    if stats:
        kind = stats.get("kind")

        if kind == "numeric" and (
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
            or udt_name in ("int2", "int4", "int8", "numeric", "float4", "float8")
        ):
            lo = stats.get("min")
            hi = stats.get("max")
            if lo is not None and hi is not None and lo <= hi:
                return fake.pyint(min_value=int(lo), max_value=int(hi))

        if kind == "datetime" and (
            data_type
            in (
                "date",
                "timestamp without time zone",
                "timestamp with time zone",
            )
            or "timestamp" in udt_name
            or udt_name == "date"
        ):
            return fake.date_time_between(start_date="-5y", end_date="now")

        if kind == "categorical":
            values = stats.get("values") or []
            if values:
                population = [v["value"] for v in values]
                weights = [v.get("freq", 1) for v in values]
                return random.choices(population, weights=weights, k=1)[0]

        if kind == "text" and (
            "character" in data_type
            or "text" in data_type
            or udt_name == "text"
        ):
            min_l = stats.get("min_length") or 1
            max_l = stats.get("max_length") or max_len
            if max_l < 1:
                max_l = max_len
            if min_l < 1:
                min_l = 1
            if max_l < min_l:
                max_l = min_l
            length = random.randint(min_l, max_l)
            requested = max(length, 5)
            txt = fake.text(max_nb_chars=requested)
            return txt[:length]

    # String-ish helpers for default path
    def _limited_text(n: int) -> str:
        requested = max(n, 5)
        txt = fake.text(max_nb_chars=requested)
        return txt[:n]

    # Name / email / phone based on column name
    if "email" in name:
        return fake.email()
    if "first_name" in name:
        return fake.first_name()
    if "last_name" in name:
        return fake.last_name()
    if "full_name" in name or name == "name":
        return fake.name()
    if "phone" in name or "mobile" in name:
        return fake.phone_number()
    if "city" in name:
        return fake.city()
    if "country" in name:
        return fake.country()
    if "postcode" in name or "zipcode" in name or "zip" == name:
        return fake.postcode()

    # Network / IP address types (e.g. PostgreSQL inet)
    # Only treat real inet-typed columns as IPs; do NOT rely on
    # the column name (to avoid catching names like "interest_rate").
    if data_type == "inet" or udt_name == "inet":
        # Prefer IPv4 for simplicity; inet accepts both v4 and v6.
        return fake.ipv4()

    # Date / time
    if "timestamp" in data_type or "timestamp" in udt_name:
        return fake.date_time_between(start_date="-5y", end_date="now")
    if data_type in ("date",) or udt_name in ("date",):
        return fake.date_between(start_date="-5y", end_date="today")

    # Boolean
    if data_type in ("boolean",) or udt_name in ("bool",):
        return fake.pybool()

    # Numeric integer types
    if data_type in ("integer", "bigint", "smallint") or udt_name in ("int2", "int4", "int8"):
        # Respect smallint range; use a larger range for int/bigint
        if data_type == "smallint" or udt_name == "int2":
            max_val = 32_767
        else:
            max_val = 1_000_000

        return fake.pyint(min_value=0, max_value=max_val)

    # Floating-point types (double precision, real)
    if data_type in ("double precision", "real") or udt_name in ("float4", "float8"):
        if any(k in name for k in ["amount", "price", "total", "balance"]):
            return fake.pyfloat(min_value=0, max_value=1_000_000)
        return fake.pyfloat(min_value=0, max_value=1_000_000)

    # Numeric/decimal with precision/scale respected
    if data_type in ("numeric", "decimal") or udt_name in ("numeric",):
        precision = col.get("numeric_precision")
        scale = col.get("numeric_scale")
        if not isinstance(precision, int) or precision <= 0:
            scale = scale if isinstance(scale, int) and scale >= 0 else 2
            return fake.pydecimal(left_digits=10, right_digits=scale, positive=True)
        if not isinstance(scale, int) or scale < 0:
            scale = 0
        if scale >= precision:
            return fake.pyint(min_value=0, max_value=10**precision - 1)
        left_digits = max(1, precision - scale)
        d = fake.pydecimal(left_digits=left_digits, right_digits=scale, positive=True)
        max_abs = Decimal(10) ** Decimal(precision - scale)
        if d >= max_abs:
            d = max_abs - (Decimal(1) / (Decimal(10) ** scale))
        return d

    # Text / varchar
    if any(t in data_type for t in ("character varying", "varchar", "character", "text")) or udt_name in (
        "text",
    ):
        n = max_len if isinstance(max_len, int) and max_len > 0 else 128
        if any(k in name for k in ["desc", "description", "comment"]):
            return _limited_text(min(n, 200))
        return _limited_text(n)

    # Fallback: generic string
    return _limited_text(min(max_len, 64) if isinstance(max_len, int) and max_len > 0 else 64)


def generate_synthetic_dataset(
    db_schema_list: List[Dict[str, Any]],
    rows_per_table: int = 100,
    rows_per_table_override: Optional[Dict[str, int]] = None,
    seed: Optional[int] = None,
    column_profiles: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Generate synthetic rows in memory for all tables in db_schema_list.

    - Uses FK metadata so child rows always reference valid parent rows.
    - Generates integer PKs when possible.
    - Enforces uniqueness for PK and UNIQUE columns.
    """
    from .ordering import plan_table_order

    if seed is not None:
        random.seed(seed)
        Faker.seed(seed)

    ordered_tables = plan_table_order(db_schema_list)
    generated: Dict[str, List[Dict[str, Any]]] = {}
    pk_counters: Dict[str, Dict[str, int]] = {}

    pk_cols_map: Dict[str, List[str]] = {}
    fk_map: Dict[str, List[Dict[str, Any]]] = {}
    cols_map: Dict[str, List[Dict[str, Any]]] = {}
    unique_cols_map: Dict[str, set] = {}
    unique_tuple_constraints: Dict[str, List[Dict[str, Any]]] = {}

    for t in db_schema_list:
        tid = _table_id(t)
        pk_cols: List[str] = []
        for pk in t["constraints"].get("primary_keys", []):
            pk_cols.extend(pk["columns"])
        pk_cols_map[tid] = pk_cols
        fk_map[tid] = t["constraints"].get("foreign_keys", [])
        cols_map[tid] = t["columns"]

        # Only enforce per-column uniqueness for *single-column* PK/UNIQUE
        # constraints. Composite keys are enforced via tuple constraints
        # below; their individual columns (e.g. clock_dt) do not need
        # independent scalar uniqueness, which avoids over-constraining
        # date/time columns and similar.
        unique_cols: set = set()

        tuple_constraints: List[Dict[str, Any]] = []
        for pk in t["constraints"].get("primary_keys", []):
            cols_pk = list(pk.get("columns", []))
            if cols_pk:
                tuple_constraints.append({"name": pk.get("name") or "pk", "columns": cols_pk})
                if len(cols_pk) == 1:
                    unique_cols.add(cols_pk[0])
        for uq in t["constraints"].get("uniques", []):
            cols_uq = list(uq.get("columns", []))
            if cols_uq:
                tuple_constraints.append({"name": uq.get("name") or "uniq", "columns": cols_uq})
                if len(cols_uq) == 1:
                    unique_cols.add(cols_uq[0])

        unique_cols_map[tid] = unique_cols
        unique_tuple_constraints[tid] = tuple_constraints

    used_unique_values: Dict[str, Dict[str, set]] = {}
    used_unique_tuples: Dict[str, Dict[str, set]] = {}

    for t in ordered_tables:
        tid = _table_id(t)
        table_rows: List[Dict[str, Any]] = []
        generated[tid] = table_rows
        pk_counters.setdefault(tid, {})
        used_unique_values.setdefault(tid, {})
        used_unique_tuples.setdefault(tid, {})
        table_unique_cols = unique_cols_map.get(tid, set())

        n_rows = rows_per_table
        if rows_per_table_override and tid in rows_per_table_override:
            n_rows = rows_per_table_override[tid]

        table_pk_cols = pk_cols_map.get(tid, [])
        table_fk_constraints = fk_map.get(tid, [])
        table_cols = cols_map[tid]

        for _ in range(n_rows):
            row: Dict[str, Any] = {}

            # Foreign keys
            #
            # IMPORTANT: Some tables have multiple FKs that share columns
            # (e.g. org_cd participates in more than one composite FK).
            # We must avoid overwriting an already-populated child column
            # with a conflicting value from a different parent table.
            #
            # Strategy:
            # - When a child column is already set, filter parent candidates
            #   so the referenced column matches that value.
            # - When applying the FK, never overwrite an existing child
            #   column; only fill missing ones.
            # - If no parent row is compatible with existing child values
            #   for a given FK, we skip this synthetic row entirely rather
            #   than emitting an FK-violating combination.
            valid_fk_combo = True
            for fk in table_fk_constraints:
                parent_tid = f"{fk['references']['schema']}.{fk['references']['table']}"
                parent_rows = generated.get(parent_tid) or []
                if not parent_rows:
                    continue

                candidates = parent_rows
                for child_col, parent_col in zip(
                    fk["columns"], fk["references"]["columns"]
                ):
                    if child_col in row:
                        candidates = [
                            pr for pr in candidates if pr.get(parent_col) == row[child_col]
                        ]
                        if not candidates:
                            break

                if not candidates:
                    # No consistent parent exists for this FK given the
                    # already-populated child values. Skip this row and
                    # try generating another one instead of falling back
                    # to an arbitrary (and invalid) combination.
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

            for col in table_cols:
                cname = col["name"]
                if cname in row:
                    continue

                data_type = (col.get("data_type") or "").lower()
                udt_name = (col.get("udt_name") or "").lower()

                # Integer primary-key columns: assign deterministic sequential IDs
                # per table/column. This guarantees uniqueness for integer PKs.
                if cname in table_pk_cols and data_type in (
                    "integer",
                    "bigint",
                    "smallint",
                ):
                    c = pk_counters[tid].get(cname, 0) + 1
                    pk_counters[tid][cname] = c
                    row[cname] = c
                    continue

                # Text/varchar primary-key columns: generate a deterministic
                # pattern-based ID instead of free-text Faker output. This avoids
                # rare PK collisions such as "Purpose brother." for columns like
                # branch_id, customer_id, etc.
                if cname in table_pk_cols and (
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

                col_stats = None
                if column_profiles and tid in column_profiles and cname not in table_unique_cols:
                    col_stats = column_profiles[tid].get(cname)

                value = _generate_scalar_value(col, stats=col_stats)

                if cname in table_unique_cols and cname not in table_pk_cols:
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

            # Enforce composite uniqueness (PK and UNIQUE constraints) so
            # that tuples like (org_cd, proj_cd, prsn_cd) remain unique
            # across the in-memory dataset.
            tuple_defs = unique_tuple_constraints.get(tid, [])
            if tuple_defs:
                ok = True
                for uc in tuple_defs:
                    cols_tuple = uc.get("columns", [])
                    key_name = uc.get("name") or ",".join(cols_tuple)
                    vals = tuple(row.get(c) for c in cols_tuple)
                    if any(v is None for v in vals):
                        continue
                    used_for_uc = used_unique_tuples[tid].setdefault(key_name, set())
                    if vals in used_for_uc:
                        ok = False
                        break
                if not ok:
                    continue
                for uc in tuple_defs:
                    cols_tuple = uc.get("columns", [])
                    key_name = uc.get("name") or ",".join(cols_tuple)
                    vals = tuple(row.get(c) for c in cols_tuple)
                    if any(v is None for v in vals):
                        continue
                    used_for_uc = used_unique_tuples[tid].setdefault(key_name, set())
                    used_for_uc.add(vals)

            table_rows.append(row)

    return generated
