import click
import psycopg2
from edl_parser import parse_edl
from schema_loader import load_schema_to_postgres
from generator_config import schema_to_generator_config
from synthetic_generator import generate_synthetic_data, load_generator_config
from db_writer import write_to_postgres
from validation import validate_pk_fk

@click.group()
def cli():
    pass

@cli.command()
@click.option("--edl-path", default="edl/finance_schema.edl", help="Path to EDL schema file")
@click.option("--db-host", default="localhost", show_default=True)
@click.option("--db-port", default=5432, type=int, show_default=True)
@click.option("--db-name", default="finance_synth", show_default=True)
@click.option("--db-user", default="postgres", show_default=True)
@click.option("--db-password", default="postgres", show_default=True)
def init_schema(edl_path, db_host, db_port, db_name, db_user, db_password):
    schema = parse_edl(edl_path)
    load_schema_to_postgres(schema, host=db_host, port=db_port, db=db_name, user=db_user, password=db_password)
    click.echo("Schema loaded into Postgres")

@cli.command()
@click.option("--edl-path", default="edl/finance_schema.edl")
@click.option("--config-out", default="schema_config.json")
def build_config(edl_path, config_out):
    schema = parse_edl(edl_path)
    schema_to_generator_config(schema, config_out)
    click.echo(f"Generator config written to {config_out}")

@cli.command()
@click.option("--config-path", default="schema_config.json")
@click.option("--rows", default=1000, help="Rows per table")
@click.option("--db-host", default="localhost", show_default=True)
@click.option("--db-port", default=5432, type=int, show_default=True)
@click.option("--db-name", default="finance_synth", show_default=True)
@click.option("--db-user", default="postgres", show_default=True)
@click.option("--db-password", default="postgres", show_default=True)
@click.option("--append/--no-append", default=False, show_default=True, help="Append rows instead of full refresh")
def generate(config_path, rows, db_host, db_port, db_name, db_user, db_password, append):
    pk_offsets = None
    if append:
        cfg = load_generator_config(config_path)
        pk_offsets = _compute_pk_offsets(cfg, db_host, db_port, db_name, db_user, db_password)

    data = generate_synthetic_data(config_path, rows_per_table=rows, pk_offsets=pk_offsets)
    write_to_postgres(data, host=db_host, port=db_port, db=db_name, user=db_user, password=db_password, append=append)
    click.echo(f"Synthetic data generated and loaded into Postgres ({rows} rows/table)")

@cli.command()
@click.option("--edl-path", default="edl/finance_schema.edl")
@click.option("--db-host", default="localhost", show_default=True)
@click.option("--db-port", default=5432, type=int, show_default=True)
@click.option("--db-name", default="finance_synth", show_default=True)
@click.option("--db-user", default="postgres", show_default=True)
@click.option("--db-password", default="postgres", show_default=True)
def validate(edl_path, db_host, db_port, db_name, db_user, db_password):
    schema = parse_edl(edl_path)
    validate_pk_fk(schema, host=db_host, port=db_port, db=db_name, user=db_user, password=db_password)


@cli.command()
@click.option("--edl-path", default="edl/finance_schema.edl", show_default=True)
@click.option("--rows", default=1000, help="Rows per table", show_default=True)
@click.option("--config-out", default="artifacts/generator_config.json", show_default=True)
@click.option("--db-host", default="localhost", show_default=True)
@click.option("--db-port", default=5432, type=int, show_default=True)
@click.option("--db-name", default="finance_synth", show_default=True)
@click.option("--db-user", default="postgres", show_default=True)
@click.option("--db-password", default="postgres", show_default=True)
@click.option("--append/--no-append", default=False, show_default=True, help="Append rows instead of full refresh")
def pipeline(edl_path, rows, config_out, db_host, db_port, db_name, db_user, db_password, append):
    """Run end-to-end: load schema, build config, generate rows, write to DB, validate."""
    schema = parse_edl(edl_path)
    load_schema_to_postgres(schema, host=db_host, port=db_port, db=db_name, user=db_user, password=db_password)
    schema_to_generator_config(schema, config_out)

    pk_offsets = None
    if append:
        cfg = load_generator_config(config_out)
        pk_offsets = _compute_pk_offsets(cfg, db_host, db_port, db_name, db_user, db_password)

    data = generate_synthetic_data(config_out, rows_per_table=rows, pk_offsets=pk_offsets)
    write_to_postgres(data, host=db_host, port=db_port, db=db_name, user=db_user, password=db_password, append=append)
    validate_pk_fk(schema, host=db_host, port=db_port, db=db_name, user=db_user, password=db_password)
    click.echo(f"Pipeline complete with {rows} rows/table")


def _compute_pk_offsets(cfg, host, port, db, user, password):
    """Compute per-table PK offsets based on existing data in Postgres.

    This ensures that in append mode, new deterministic PKs continue from
    the current maximum instead of restarting at 1, avoiding conflicts.
    """
    tables_cfg = cfg.get("tables", {})
    offsets = {}

    if not tables_cfg:
        return offsets

    conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=password)
    cur = conn.cursor()

    for tname, tcfg in tables_cfg.items():
        pk = tcfg.get("primary_key")
        if not pk:
            continue

        cur.execute(f'SELECT MAX("{pk}") FROM "{tname}"')
        row = cur.fetchone()
        max_pk = row[0]
        if max_pk is None:
            offsets[tname] = 0
            continue

        # Extract trailing digits from the PK value, e.g. CUS_000123 -> 123
        s = str(max_pk)
        digits = ""
        for ch in reversed(s):
            if ch.isdigit():
                digits = ch + digits
            else:
                break

        offsets[tname] = int(digits) if digits else 0

    cur.close()
    conn.close()
    return offsets

if __name__ == "__main__":
    cli()