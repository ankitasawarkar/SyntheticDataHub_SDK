import psycopg2
from typing import Dict
import pandas as pd
from metadata_model import SchemaMeta

def validate_pk_fk(schema: SchemaMeta,
                   host="localhost",
                   port=5432,
                   db="finance_synth",
                   user="postgres",
                   password="postgres"):
    conn = psycopg2.connect(
        host=host, port=port, dbname=db, user=user, password=password
    )
    cur = conn.cursor()

    # PK uniqueness & non-null
    for tname, table in schema.tables.items():
        if not table.primary_key:
            continue
        pk = table.primary_key
        cur.execute(
            f'SELECT COUNT(*), COUNT(DISTINCT "{pk}"), '
            f'SUM(CASE WHEN "{pk}" IS NULL THEN 1 ELSE 0 END) '
            f'FROM "{tname}"'
        )
        total, distinct, nulls = cur.fetchone()
        if nulls > 0 or total != distinct:
            print(f"[PK ISSUE] {tname}.{pk}: total={total}, distinct={distinct}, nulls={nulls}")
        else:
            print(f"[PK OK] {tname}.{pk}")

    # Required fields + allowed values
    for tname, table in schema.tables.items():
        for fname, fmeta in table.fields.items():
            # Required (non-null) check
            if fmeta.required:
                cur.execute(
                    f'SELECT COUNT(*) FROM "{tname}" '
                    f'WHERE "{fname}" IS NULL'
                )
                nulls = cur.fetchone()[0]
                if nulls > 0:
                    print(f"[REQ ISSUE] {tname}.{fname}: {nulls} NULLs where required")

            # Allowed values membership check
            if fmeta.allowed_values:
                placeholders = ",".join(["%s"] * len(fmeta.allowed_values))
                query = (
                    f'SELECT COUNT(*) FROM "{tname}" '
                    f'WHERE "{fname}" IS NOT NULL '
                    f'AND "{fname}" NOT IN ({placeholders})'
                )
                cur.execute(query, fmeta.allowed_values)
                invalid_count = cur.fetchone()[0]
                if invalid_count > 0:
                    print(
                        f"[VALS ISSUE] {tname}.{fname}: "
                        f"{invalid_count} values not in {fmeta.allowed_values}"
                    )

            # Basic format checks for special logical types
            ftype = fmeta.type.upper()
            if ftype == "EMAIL":
                # Very simple email shape: something@something.something
                cur.execute(
                    f'SELECT COUNT(*) FROM "{tname}" '
                    f'WHERE "{fname}" IS NOT NULL '
                    f'AND "{fname}" NOT LIKE \'%@%.%\''
                )
                bad = cur.fetchone()[0]
                if bad > 0:
                    print(f"[FORMAT ISSUE] {tname}.{fname}: {bad} values fail basic email pattern")

            if ftype == "SSN":
                # US SSN pattern: NNN-NN-NNNN
                cur.execute(
                    f'SELECT COUNT(*) FROM "{tname}" '
                    f'WHERE "{fname}" IS NOT NULL '
                    f'AND "{fname}" !~ \'^[0-9]{{3}}-[0-9]{{2}}-[0-9]{{4}}$\''
                )
                bad = cur.fetchone()[0]
                if bad > 0:
                    print(f"[FORMAT ISSUE] {tname}.{fname}: {bad} values fail SSN pattern NNN-NN-NNNN")

    # FK consistency
    for rel in schema.relationships:
        q = f'''
        SELECT COUNT(*)
        FROM "{rel.child_table}" c
        LEFT JOIN "{rel.parent_table}" p
          ON c."{rel.child_key}" = p."{rel.parent_key}"
        WHERE c."{rel.child_key}" IS NOT NULL AND p."{rel.parent_key}" IS NULL;
        '''
        cur.execute(q)
        orphans = cur.fetchone()[0]
        if orphans > 0:
            print(f"[FK ISSUE] {rel.child_table}.{rel.child_key} -> {rel.parent_table}.{rel.parent_key}: {orphans} orphans")
        else:
            print(f"[FK OK] {rel.child_table}.{rel.child_key} -> {rel.parent_table}.{rel.parent_key}")

    cur.close()
    conn.close()


def validate_in_memory(schema: SchemaMeta, data: Dict[str, pd.DataFrame]):
    """
    Validate generated DataFrames against the schema without a database.
    Checks:
      - Primary key non-null and uniqueness
      - Required fields are non-null
      - Allowed values membership
      - Foreign key referential integrity (for non-null child keys)
    Prints issues and OK statuses similarly to DB validation.
    """
    # Table-level checks
    for tname, table in schema.tables.items():
        if tname not in data:
            print(f"[DATA MISSING] No dataframe for table {tname}")
            continue
        df = data[tname]

        # PK checks
        if table.primary_key:
            pk = table.primary_key
            if pk not in df.columns:
                print(f"[PK ISSUE] {tname}.{pk}: column missing in data")
            else:
                nulls = int(df[pk].isna().sum())
                distinct = df[pk].nunique(dropna=True)
                total = len(df)
                if nulls > 0 or distinct != total:
                    print(f"[PK ISSUE] {tname}.{pk}: total={total}, distinct={distinct}, nulls={nulls}")
                else:
                    print(f"[PK OK] {tname}.{pk}")

        # Required + allowed values checks
        for fname, fmeta in table.fields.items():
            if fname not in df.columns:
                print(f"[FIELD MISSING] {tname}.{fname}")
                continue
            s = df[fname]
            if fmeta.required:
                req_nulls = int(s.isna().sum())
                if req_nulls > 0:
                    print(f"[REQ ISSUE] {tname}.{fname}: {req_nulls} NULLs where required")
            if fmeta.allowed_values:
                invalid = s.dropna()[~s.dropna().isin(fmeta.allowed_values)]
                if not invalid.empty:
                    print(f"[VALS ISSUE] {tname}.{fname}: {len(invalid)} values not in {fmeta.allowed_values}")

            # Simple in-memory format checks for logical types
            ftype = fmeta.type.upper()
            if ftype == "EMAIL":
                non_null = s.dropna().astype(str)
                bad = non_null[~non_null.str.contains(r".+@.+\..+", regex=True)]
                if not bad.empty:
                    print(f"[FORMAT ISSUE] {tname}.{fname}: {len(bad)} values fail basic email pattern")

            if ftype == "SSN":
                non_null = s.dropna().astype(str)
                bad = non_null[~non_null.str.fullmatch(r"\d{3}-\d{2}-\d{4}")]
                if not bad.empty:
                    print(f"[FORMAT ISSUE] {tname}.{fname}: {len(bad)} values fail SSN pattern NNN-NN-NNNN")

    # Relationship checks
    for rel in schema.relationships:
        child_df = data.get(rel.child_table)
        parent_df = data.get(rel.parent_table)
        if child_df is None or parent_df is None:
            print(f"[FK SKIP] {rel.child_table}.{rel.child_key} -> {rel.parent_table}.{rel.parent_key}: missing data")
            continue
        if rel.child_key not in child_df.columns or rel.parent_key not in parent_df.columns:
            print(f"[FK SKIP] {rel.child_table}.{rel.child_key} -> {rel.parent_table}.{rel.parent_key}: column missing")
            continue

        child_vals = set(child_df[rel.child_key].dropna().tolist())
        parent_vals = set(parent_df[rel.parent_key].dropna().tolist())
        orphans = child_vals - parent_vals
        if orphans:
            # Count occurrences of orphan values in child
            orphan_count = int(child_df[rel.child_key].isin(orphans).sum())
            print(f"[FK ISSUE] {rel.child_table}.{rel.child_key} -> {rel.parent_table}.{rel.parent_key}: {orphan_count} orphans")
        else:
            print(f"[FK OK] {rel.child_table}.{rel.child_key} -> {rel.parent_table}.{rel.parent_key}")