from typing import Dict, Any, List
from collections import defaultdict

from .db import get_connection, DBConfig


def fetch_schema_metadata(config: DBConfig, include_system_schemas: bool = False) -> Dict[str, Dict[str, Any]]:
    """Fetch tables, columns, and constraints (PK, FK, UNIQUE) for the current database.

    Returns a dictionary keyed by "schema.table" with structure similar to the notebook
    helper, suitable for exploration/debugging.
    """
    excluded_schemas = ("pg_catalog", "information_schema")
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            # Columns
            column_query = """
            SELECT
                table_schema,
                table_name,
                column_name,
                ordinal_position,
                data_type,
                udt_name,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns
            WHERE (%(include_system)s OR table_schema NOT IN %(excluded_schemas)s)
            ORDER BY table_schema, table_name, ordinal_position;
            """
            cur.execute(
                column_query,
                {
                    "include_system": include_system_schemas,
                    "excluded_schemas": excluded_schemas,
                },
            )
            columns_rows = cur.fetchall()

            schema: Dict[str, Dict[str, Any]] = {}
            for col in columns_rows:
                key = f"{col['table_schema']}.{col['table_name']}"
                table_entry = schema.setdefault(
                    key,
                    {
                        "schema": col["table_schema"],
                        "table": col["table_name"],
                        "columns": {},
                        "primary_key": [],
                        "foreign_keys": [],
                        "unique_constraints": [],
                    },
                )
                table_entry["columns"][col["column_name"]] = {
                    "data_type": col["data_type"],
                    "udt_name": col["udt_name"],
                    "is_nullable": col["is_nullable"] == "YES",
                    "default": col["column_default"],
                    "max_length": col["character_maximum_length"],
                    "numeric_precision": col["numeric_precision"],
                    "numeric_scale": col["numeric_scale"],
                }

            # Primary keys
            pk_query = """
            SELECT
                tc.table_schema,
                tc.table_name,
                kc.column_name,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kc
              ON kc.table_schema = tc.table_schema
             AND kc.table_name = tc.table_name
             AND kc.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND (%(include_system)s OR tc.table_schema NOT IN %(excluded_schemas)s)
            ORDER BY tc.table_schema, tc.table_name, kc.ordinal_position;
            """
            cur.execute(
                pk_query,
                {
                    "include_system": include_system_schemas,
                    "excluded_schemas": excluded_schemas,
                },
            )
            for pk in cur.fetchall():
                key = f"{pk['table_schema']}.{pk['table_name']}"
                if key in schema:
                    schema[key]["primary_key"].append(pk["column_name"])

            # Foreign keys
            fk_query = """
            SELECT
                tc.table_schema,
                tc.table_name,
                kc.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kc
              ON kc.table_schema = tc.table_schema
             AND kc.table_name = tc.table_name
             AND kc.constraint_name = tc.constraint_name
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND (%(include_system)s OR tc.table_schema NOT IN %(excluded_schemas)s)
            ORDER BY tc.table_schema, tc.table_name, tc.constraint_name, kc.ordinal_position;
            """
            cur.execute(
                fk_query,
                {
                    "include_system": include_system_schemas,
                    "excluded_schemas": excluded_schemas,
                },
            )
            fk_map: Dict[tuple, Dict[str, Any]] = {}
            for fk in cur.fetchall():
                key = f"{fk['table_schema']}.{fk['table_name']}"
                if key not in schema:
                    continue
                fk_key = (key, fk["constraint_name"])
                entry = fk_map.setdefault(
                    fk_key,
                    {
                        "columns": [],
                        "referenced_table": f"{fk['foreign_table_schema']}.{fk['foreign_table_name']}",
                        "referenced_columns": [],
                        "constraint_name": fk["constraint_name"],
                    },
                )
                entry["columns"].append(fk["column_name"])
                entry["referenced_columns"].append(fk["foreign_column_name"])

            for (table_key, _), fk_entry in fk_map.items():
                schema[table_key]["foreign_keys"].append(fk_entry)

            # Unique constraints (excluding PKs which are captured separately)
            unique_query = """
            SELECT
                tc.table_schema,
                tc.table_name,
                kc.column_name,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kc
              ON kc.table_schema = tc.table_schema
             AND kc.table_name = tc.table_name
             AND kc.constraint_name = tc.constraint_name
            WHERE tc.constraint_type IN ('UNIQUE')
              AND (%(include_system)s OR tc.table_schema NOT IN %(excluded_schemas)s)
            ORDER BY tc.table_schema, tc.table_name, tc.constraint_name, kc.ordinal_position;
            """
            cur.execute(
                unique_query,
                {
                    "include_system": include_system_schemas,
                    "excluded_schemas": excluded_schemas,
                },
            )
            uniq_map: Dict[tuple, Dict[str, Any]] = {}
            for uq in cur.fetchall():
                key = f"{uq['table_schema']}.{uq['table_name']}"
                if key not in schema:
                    continue
                uq_key = (key, uq["constraint_name"])
                entry = uniq_map.setdefault(
                    uq_key,
                    {
                        "columns": [],
                        "constraint_name": uq["constraint_name"],
                    },
                )
                entry["columns"].append(uq["column_name"])

            for (table_key, _), uq_entry in uniq_map.items():
                schema[table_key]["unique_constraints"].append(uq_entry)

    return schema


def fetch_db_schema(config: DBConfig) -> List[Dict[str, Any]]:
    """Return schema metadata for all non-system tables in the database.

    Matches the structure used by the notebook's db_schema: a list of tables,
    each with "schema", "table", "columns", and "constraints".
    """
    tables: Dict[tuple, Dict[str, Any]] = {}

    with get_connection(config) as conn:
        with conn.cursor() as cur:
            # Columns
            cur.execute(
                """
                SELECT
                    table_schema,
                    table_name,
                    column_name,
                    ordinal_position,
                    data_type,
                    udt_name,
                    is_nullable,
                    column_default,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND table_schema NOT LIKE 'pg_toast%'
                ORDER BY table_schema, table_name, ordinal_position
                """
            )
            for row in cur.fetchall():
                key = (row["table_schema"], row["table_name"])
                if key not in tables:
                    tables[key] = {
                        "schema": row["table_schema"],
                        "table": row["table_name"],
                        "columns": [],
                        "constraints": {
                            "primary_keys": [],
                            "foreign_keys": [],
                            "uniques": [],
                            "checks": [],
                        },
                    }
                tables[key]["columns"].append(
                    {
                        "name": row["column_name"],
                        "data_type": row["data_type"],
                        "udt_name": row["udt_name"],
                        "is_nullable": row["is_nullable"] == "YES",
                        "default": row["column_default"],
                        "max_length": row["character_maximum_length"],
                        "numeric_precision": row["numeric_precision"],
                        "numeric_scale": row["numeric_scale"],
                        "ordinal_position": row["ordinal_position"],
                    }
                )

            # Primary keys
            cur.execute(
                """
                SELECT
                    kcu.table_schema,
                    kcu.table_name,
                    tco.constraint_name,
                    kcu.column_name
                FROM information_schema.table_constraints tco
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tco.constraint_name
                 AND kcu.constraint_schema = tco.constraint_schema
                WHERE tco.constraint_type = 'PRIMARY KEY'
                ORDER BY kcu.table_schema, kcu.table_name, tco.constraint_name, kcu.ordinal_position
                """
            )
            pk_map: Dict[tuple, Dict[str, Any]] = defaultdict(lambda: {"name": None, "columns": []})
            for row in cur.fetchall():
                key = (row["table_schema"], row["table_name"], row["constraint_name"])
                pk = pk_map[key]
                pk["name"] = row["constraint_name"]
                pk["columns"].append(row["column_name"])
            for (schema, table, _), pk in pk_map.items():
                tkey = (schema, table)
                if tkey in tables:
                    tables[tkey]["constraints"]["primary_keys"].append(pk)

            # Foreign keys
            #
            # NOTE: For multi-column FKs, we must carefully align each
            # referencing column with its corresponding referenced column.
            # The naive join against constraint_column_usage can mix up
            # column order and produce incorrect mappings like
            # (child.org_cd -> parent.proj_cd, child.proj_cd -> parent.org_cd).
            #
            # This query follows the pattern recommended in Postgres docs:
            # it joins through information_schema.referential_constraints and
            # uses position_in_unique_constraint / ordinal_position to pair
            # columns correctly.
            cur.execute(
                """
                SELECT
                    tc.constraint_name,
                    kcu.table_schema,
                    kcu.table_name,
                    kcu.column_name,
                    ccu.table_schema AS foreign_table_schema,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                 AND tc.constraint_schema = kcu.constraint_schema
                JOIN information_schema.referential_constraints AS rc
                    ON rc.constraint_name = tc.constraint_name
                 AND rc.constraint_schema = tc.constraint_schema
                JOIN information_schema.key_column_usage AS ccu
                    ON ccu.constraint_name = rc.unique_constraint_name
                 AND ccu.constraint_schema = rc.unique_constraint_schema
                 AND ccu.ordinal_position = kcu.position_in_unique_constraint
                WHERE tc.constraint_type = 'FOREIGN KEY'
                ORDER BY kcu.table_schema, kcu.table_name, tc.constraint_name, kcu.ordinal_position
                """
            )
            fk_map: Dict[tuple, Dict[str, Any]] = defaultdict(
                lambda: {
                    "name": None,
                    "columns": [],
                    "references": {"schema": None, "table": None, "columns": []},
                }
            )
            for row in cur.fetchall():
                key = (row["table_schema"], row["table_name"], row["constraint_name"])
                fk = fk_map[key]
                fk["name"] = row["constraint_name"]
                fk["columns"].append(row["column_name"])
                fk["references"]["schema"] = row["foreign_table_schema"]
                fk["references"]["table"] = row["foreign_table_name"]
                fk["references"]["columns"].append(row["foreign_column_name"])
            for (schema, table, _), fk in fk_map.items():
                tkey = (schema, table)
                if tkey in tables:
                    tables[tkey]["constraints"]["foreign_keys"].append(fk)

            # Unique constraints
            cur.execute(
                """
                SELECT
                    kcu.table_schema,
                    kcu.table_name,
                    tco.constraint_name,
                    kcu.column_name
                FROM information_schema.table_constraints tco
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tco.constraint_name
                 AND kcu.constraint_schema = tco.constraint_schema
                WHERE tco.constraint_type = 'UNIQUE'
                ORDER BY kcu.table_schema, kcu.table_name, tco.constraint_name, kcu.ordinal_position
                """
            )
            uniq_map: Dict[tuple, Dict[str, Any]] = defaultdict(lambda: {"name": None, "columns": []})
            for row in cur.fetchall():
                key = (row["table_schema"], row["table_name"], row["constraint_name"])
                uq = uniq_map[key]
                uq["name"] = row["constraint_name"]
                uq["columns"].append(row["column_name"])
            for (schema, table, _), uq in uniq_map.items():
                tkey = (schema, table)
                if tkey in tables:
                    tables[tkey]["constraints"]["uniques"].append(uq)

            # Check constraints
            cur.execute(
                """
                SELECT
                    tc.table_schema,
                    tc.table_name,
                    tc.constraint_name,
                    cc.check_clause
                FROM information_schema.table_constraints tc
                JOIN information_schema.check_constraints cc
                  ON tc.constraint_name = cc.constraint_name
                 AND tc.constraint_schema = cc.constraint_schema
                WHERE tc.constraint_type = 'CHECK'
                ORDER BY tc.table_schema, tc.table_name, tc.constraint_name
                """
            )
            for row in cur.fetchall():
                key = (row["table_schema"], row["table_name"])
                if key in tables:
                    tables[key]["constraints"]["checks"].append(
                        {
                            "name": row["constraint_name"],
                            "clause": row["check_clause"],
                        }
                    )

    return [tables[key] for key in sorted(tables.keys())]
