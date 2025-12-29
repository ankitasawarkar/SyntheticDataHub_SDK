from __future__ import annotations

import time
from typing import Dict

import click
import pandas as pd
import psycopg2
from psycopg2 import OperationalError

from rds_pipeline.generator_rds import generate_synthetic_demo_data
from db_writer import write_to_postgres

from .base import Pipeline
from . import register_pipeline


class RdsPipeline(Pipeline):
    name = "rds_pipeline"
    schema_name = "rds_schema"

    def prepare_schema(self, **kw) -> None:
        rows: int = kw.get("rows", 1000)
        sql_path: str = kw.get("sql_path", "artifacts/rds_schema.sql")
        append: bool = kw.get("append", False)
        db_host: str = kw["db_host"]
        db_port: int = kw["db_port"]
        db_name: str = kw["db_name"]
        db_user: str = kw["db_user"]
        db_password: str = kw["db_password"]

        max_attempts = 10
        delay_seconds = 3
        for attempt in range(1, max_attempts + 1):
            try:
                click.echo(f"[{self.name}] Connecting to Postgres (attempt {attempt}/{max_attempts})...")
                conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password)
                break
            except OperationalError as exc:
                if attempt == max_attempts:
                    click.echo(f"[{self.name}] Failed to connect to Postgres after multiple attempts.")
                    raise
                click.echo(f"[{self.name}] Postgres not ready yet: {exc}. Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)

        conn.autocommit = True
        cur = conn.cursor()

        if append:
            click.echo(f"[{self.name}] Append mode: leaving existing schema '{self.schema_name}' as-is.")
            cur.close()
            conn.close()
            return

        click.echo(f"Recreating schema '{self.schema_name}' in database '{db_name}' from {sql_path}...")
        cur.execute(f"DROP SCHEMA IF EXISTS {self.schema_name} CASCADE;")

        with open(sql_path, "r", encoding="utf-8") as f:
            ddl_sql = f.read()

        cur.execute(ddl_sql)
        cur.close()
        conn.close()

    def generate_data(self, **kw) -> Dict[str, pd.DataFrame]:
        rows: int = kw.get("rows", 1000)
        append: bool = kw.get("append", False)

        id_offsets: Dict[str, int] | None = None
        if append:
            db_host: str = kw["db_host"]
            db_port: int = kw["db_port"]
            db_name: str = kw["db_name"]
            db_user: str = kw["db_user"]
            db_password: str = kw["db_password"]
            id_offsets = self._compute_id_offsets(db_host, db_port, db_name, db_user, db_password)

        data = generate_synthetic_demo_data(scale=rows, id_offsets=id_offsets)
        return data

    def load_data(self, data: Dict[str, pd.DataFrame], **kw) -> None:
        db_host: str = kw["db_host"]
        db_port: int = kw["db_port"]
        db_name: str = kw["db_name"]
        db_user: str = kw["db_user"]
        db_password: str = kw["db_password"]
        append: bool = kw.get("append", False)

        # In append mode, avoid re-writing static reference tables that
        # would violate primary/unique key constraints.
        if append:
            skip_tables = {"country", "state_province", "contact_type", "department"}
            data_to_write = {name: df for name, df in data.items() if name not in skip_tables}
        else:
            data_to_write = data

        write_to_postgres(
            data_to_write,
            host=db_host,
            port=db_port,
            db=db_name,
            user=db_user,
            password=db_password,
            append=append,
            schema=self.schema_name,
        )

    def _compute_id_offsets(self, db_host: str, db_port: int, db_name: str, db_user: str, db_password: str) -> Dict[str, int]:
        """Compute starting ID offsets for append mode.

        For each numeric primary key column we care about, look at the
        current maximum value in the database and start new IDs after it.
        """

        conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password)
        cur = conn.cursor()

        def max_plus_one(table: str, column: str) -> int:
            cur.execute(
                f'SELECT COALESCE(MAX("{column}"), 0) FROM "{self.schema_name}"."{table}"'
            )
            value = cur.fetchone()[0] or 0
            return int(value) + 1

        offsets: Dict[str, int] = {}
        offsets["address_id"] = max_plus_one("address", "address_id")
        offsets["email_id"] = max_plus_one("email_address", "email_id")
        offsets["phone_id"] = max_plus_one("phone_number", "phone_id")
        offsets["employee_id"] = max_plus_one("employee", "employee_id")
        offsets["project_id"] = max_plus_one("project", "project_id")
        offsets["product_id"] = max_plus_one("product", "product_id")
        offsets["customer_id"] = max_plus_one("customer", "customer_id")
        offsets["order_id"] = max_plus_one("order_header", "order_id")
        offsets["payment_id"] = max_plus_one("payment", "payment_id")
        offsets["audit_id"] = max_plus_one("audit_log", "audit_id")
        offsets["document_id"] = max_plus_one("document_store", "document_id")

        cur.close()
        conn.close()
        return offsets

    def validate(self, **kw) -> None:
        """Run basic integrity / sanity checks for the synthetic_demo schema.

        The DDL already enforces most constraints, but these queries provide
        an explicit validation report similar in spirit to the EDL pipeline
        checks (PK/FK and key relationships).
        """

        rows: int = kw.get("rows", 1000)
        db_host: str = kw["db_host"]
        db_port: int = kw["db_port"]
        db_name: str = kw["db_name"]
        db_user: str = kw["db_user"]
        db_password: str = kw["db_password"]

        conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_password)
        cur = conn.cursor()

        schema = self.schema_name

        def fk_check(child_table: str, child_col: str, parent_table: str, parent_col: str) -> None:
            query = f'''
                SELECT COUNT(*)
                FROM "{schema}"."{child_table}" c
                LEFT JOIN "{schema}"."{parent_table}" p
                  ON c."{child_col}" = p."{parent_col}"
                WHERE c."{child_col}" IS NOT NULL
                  AND p."{parent_col}" IS NULL;
            '''
            cur.execute(query)
            orphans = cur.fetchone()[0]
            if orphans > 0:
                click.echo(
                    f"[FK ISSUE] {schema}.{child_table}.{child_col} -> {schema}.{parent_table}.{parent_col}: {orphans} orphans"
                )
            else:
                click.echo(
                    f"[FK OK] {schema}.{child_table}.{child_col} -> {schema}.{parent_table}.{parent_col}"
                )

        try:
            click.echo(f"[validation] Row counts for core tables in schema '{schema}'")
            core_tables = [
                "country",
                "state_province",
                "party",
                "person",
                "organization",
                "address",
                "email_address",
                "phone_number",
                "department",
                "employee",
                "project",
                "product",
                "customer",
                "order_header",
                "order_line",
                "payment",
            ]
            for tname in core_tables:
                cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{tname}"')
                count = cur.fetchone()[0]
                click.echo(f"[ROWS] {schema}.{tname}: {count}")

            click.echo("[validation] Foreign key consistency checks")
            fk_pairs = [
                ("state_province", "country_code", "country", "country_code"),
                ("address", "country_code", "country", "country_code"),
                ("address", "state_id", "state_province", "state_id"),
                ("address", "party_id", "party", "party_id"),
                ("email_address", "party_id", "party", "party_id"),
                ("phone_number", "party_id", "party", "party_id"),
                ("email_address", "contact_type_code", "contact_type", "contact_type_code"),
                ("phone_number", "contact_type_code", "contact_type", "contact_type_code"),
                ("user_account", "party_id", "party", "party_id"),
                ("department", "manager_party_id", "party", "party_id"),
                ("employee", "party_id", "party", "party_id"),
                ("employee", "department_id", "department", "department_id"),
                ("project", "owning_department", "department", "department_id"),
                ("employee_project", "employee_id", "employee", "employee_id"),
                ("employee_project", "project_id", "project", "project_id"),
                ("customer", "party_id", "party", "party_id"),
                ("order_header", "customer_id", "customer", "customer_id"),
                ("order_header", "billing_address_id", "address", "address_id"),
                ("order_header", "shipping_address_id", "address", "address_id"),
                ("order_line", "order_id", "order_header", "order_id"),
                ("order_line", "product_id", "product", "product_id"),
                ("payment", "order_id", "order_header", "order_id"),
                ("audit_log", "performed_by", "user_account", "user_id"),
                ("document_store", "owner_party_id", "party", "party_id"),
            ]
            for child_table, child_col, parent_table, parent_col in fk_pairs:
                fk_check(child_table, child_col, parent_table, parent_col)

            click.echo("[validation] Order totals vs. line totals")
            cur.execute(
                f'''
                SELECT COUNT(*)
                FROM "{schema}"."order_header" oh
                LEFT JOIN (
                    SELECT order_id, SUM(line_total) AS line_sum
                    FROM "{schema}"."order_line"
                    GROUP BY order_id
                ) l ON oh.order_id = l.order_id
                WHERE ABS(COALESCE(l.line_sum, 0) - oh.order_total) > 0.01;
                '''
            )
            mismatches = cur.fetchone()[0]
            if mismatches > 0:
                click.echo(f"[ORDER ISSUE] {mismatches} orders where order_total != sum(order_line.line_total)")
            else:
                click.echo("[ORDER OK] All order_header.order_total match summed order_line.line_total (within 0.01)")

            click.echo(f"RDS pipeline ({self.schema_name}) validation complete with scale={rows}")
        finally:
            cur.close()
            conn.close()


register_pipeline(RdsPipeline())
