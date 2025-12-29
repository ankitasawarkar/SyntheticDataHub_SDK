import click

from edl_pipeline.edl_parser import parse_edl
from edl_pipeline.schema_loader import load_schema_to_postgres
from edl_pipeline.generator_config import schema_to_generator_config
from edl_pipeline.synthetic_generator import generate_synthetic_data, load_generator_config
from db_writer import write_to_postgres
from edl_pipeline.validation import validate_pk_fk

from pipeline_utils import compute_pk_offsets
from pipelines import run_pipeline, get_pipeline_names
import pipelines.edl_pipeline  # noqa: F401 ensures registration of EDL pipeline
import pipelines.rds_pipeline  # noqa: F401 ensures registration of RDS pipeline

@click.group()
def cli():
    pass

@cli.command()
@click.option("--edl-path", default="edl/edl_schema.edl", help="Path to EDL schema file")
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
@click.option("--edl-path", default="edl/edl_schema.edl")
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
        pk_offsets = compute_pk_offsets(cfg, db_host, db_port, db_name, db_user, db_password)

    data = generate_synthetic_data(config_path, rows_per_table=rows, pk_offsets=pk_offsets)
    write_to_postgres(data, host=db_host, port=db_port, db=db_name, user=db_user, password=db_password, append=append)
    click.echo(f"Synthetic data generated and loaded into Postgres ({rows} rows/table)")

@cli.command()
@click.option("--edl-path", default="edl/edl_schema.edl")
@click.option("--db-host", default="localhost", show_default=True)
@click.option("--db-port", default=5432, type=int, show_default=True)
@click.option("--db-name", default="finance_synth", show_default=True)
@click.option("--db-user", default="postgres", show_default=True)
@click.option("--db-password", default="postgres", show_default=True)
def validate(edl_path, db_host, db_port, db_name, db_user, db_password):
    schema = parse_edl(edl_path)
    validate_pk_fk(schema, host=db_host, port=db_port, db=db_name, user=db_user, password=db_password)


@cli.command()
@click.option("--edl-path", default="edl/edl_schema.edl", show_default=True)
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
    # Backwards-compatible wrapper around the generic EDL pipeline
    run_pipeline(
        "edl_pipeline",
        rows=rows,
        edl_path=edl_path,
        config_out=config_out,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        append=append,
    )


@cli.command(name="pipeline-rds")
@click.option("--rows", default=1000, help="Scale factor for RDS schema data", show_default=True)
@click.option("--sql-path", default="artifacts/rds_schema.sql", show_default=True,
              help="Path to RDS schema SQL file")
@click.option("--db-host", default="localhost", show_default=True)
@click.option("--db-port", default=5432, type=int, show_default=True)
@click.option("--db-name", default="finance_synth", show_default=True)
@click.option("--db-user", default="postgres", show_default=True)
@click.option("--db-password", default="postgres", show_default=True)
@click.option("--append/--no-append", default=False, show_default=True,
              help="Append rows instead of full refresh for RDS schema")
def pipeline_rds(rows, sql_path, db_host, db_port, db_name, db_user, db_password, append):
    """Run end-to-end pipeline for the RDS-style schema.

    This is a thin wrapper around the generic "rds_pipeline" implementation
    in the pipelines package.
    """

    run_pipeline(
        "rds_pipeline",
        rows=rows,
        sql_path=sql_path,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        append=append,
    )


@cli.command(name="run-pipeline")
@click.option("--schema", "schema_name", type=click.Choice(get_pipeline_names()), required=True,
              help="Which registered pipeline to run (e.g. edl_pipeline, rds_pipeline)")
@click.option("--rows", default=1000, show_default=True, help="Rows/scale parameter for the selected pipeline")
@click.option("--edl-path", default="edl/edl_schema.edl", show_default=True,
              help="EDL schema path (used by edl_pipeline)")
@click.option("--config-out", default="artifacts/generator_config.json", show_default=True,
              help="Generator config path (used by edl_pipeline)")
@click.option("--sql-path", default="artifacts/rds_schema.sql", show_default=True,
              help="SQL DDL path (used by rds_pipeline)")
@click.option("--db-host", default="localhost", show_default=True)
@click.option("--db-port", default=5432, type=int, show_default=True)
@click.option("--db-name", default="finance_synth", show_default=True)
@click.option("--db-user", default="postgres", show_default=True)
@click.option("--db-password", default="postgres", show_default=True)
@click.option("--append/--no-append", default=False, show_default=True,
              help="Append rows instead of full refresh (used by edl_pipeline)")
def run_pipeline_cmd(schema_name, rows, edl_path, config_out, sql_path,
                     db_host, db_port, db_name, db_user, db_password, append):
    """Run any registered pipeline by schema name.

    This provides a single generic entry point; schema-specific pipelines
    decide which of the provided options they actually use.
    """

    run_pipeline(
        schema_name,
        rows=rows,
        edl_path=edl_path,
        config_out=config_out,
        sql_path=sql_path,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        append=append,
    )

if __name__ == "__main__":
    cli()