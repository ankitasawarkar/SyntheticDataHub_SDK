from __future__ import annotations

from typing import Dict

import click
import pandas as pd

from edl_pipeline.edl_parser import parse_edl
from edl_pipeline.schema_loader import load_schema_to_postgres
from edl_pipeline.generator_config import schema_to_generator_config
from edl_pipeline.synthetic_generator import generate_synthetic_data, load_generator_config
from edl_pipeline.validation import validate_pk_fk
from pipeline_utils import compute_pk_offsets
from db_writer import write_to_postgres
from config.nemo_engine import NeMoEngine, TableGenerationSpec
from nemo_pipeline.edl_adapter import build_nemo_metadata

from .base import Pipeline
from . import register_pipeline


class EdlPipeline(Pipeline):
    name = "edl_pipeline"

    def prepare_schema(self, **kw) -> None:
        edl_path: str = kw.get("edl_path", "edl/edl_schema.edl")
        db_host: str = kw["db_host"]
        db_port: int = kw["db_port"]
        db_name: str = kw["db_name"]
        db_user: str = kw["db_user"]
        db_password: str = kw["db_password"]
        config_out: str = kw.get("config_out", "artifacts/generator_config.json")

        schema = parse_edl(edl_path)
        load_schema_to_postgres(
            schema,
            host=db_host,
            port=db_port,
            db=db_name,
            user=db_user,
            password=db_password,
        )
        schema_to_generator_config(schema, config_out)

        # Stash schema path for validate step
        kw["_edl_path"] = edl_path

    def generate_data(self, **kw) -> Dict[str, pd.DataFrame]:
        rows: int = kw.get("rows", 1000)
        db_host: str = kw["db_host"]
        db_port: int = kw["db_port"]
        db_name: str = kw["db_name"]
        db_user: str = kw["db_user"]
        db_password: str = kw["db_password"]
        append: bool = kw.get("append", False)
        config_out: str = kw.get("config_out", "artifacts/generator_config.json")

        pk_offsets = None
        if append:
            cfg = load_generator_config(config_out)
            pk_offsets = compute_pk_offsets(cfg, db_host, db_port, db_name, db_user, db_password)

        data = generate_synthetic_data(config_out, rows_per_table=rows, pk_offsets=pk_offsets)
        return data

    def load_data(self, data: Dict[str, pd.DataFrame], **kw) -> None:
        db_host: str = kw["db_host"]
        db_port: int = kw["db_port"]
        db_name: str = kw["db_name"]
        db_user: str = kw["db_user"]
        db_password: str = kw["db_password"]
        append: bool = kw.get("append", False)

        write_to_postgres(
            data,
            host=db_host,
            port=db_port,
            db=db_name,
            user=db_user,
            password=db_password,
            append=append,
        )

    def validate(self, **kw) -> None:
        edl_path: str = kw.get("edl_path", "edl/edl_schema.edl")
        db_host: str = kw["db_host"]
        db_port: int = kw["db_port"]
        db_name: str = kw["db_name"]
        db_user: str = kw["db_user"]
        db_password: str = kw["db_password"]
        rows: int = kw.get("rows", 1000)

        schema = parse_edl(edl_path)
        validate_pk_fk(schema, host=db_host, port=db_port, db=db_name, user=db_user, password=db_password)
        click.echo(f"EDL pipeline complete with {rows} rows/table")


class NemoEdlPipeline(Pipeline):
    """EDL pipeline variant that uses NeMo Data Designer for generation."""

    name = "edl_nemo"

    def prepare_schema(self, **kw) -> None:
        # Reuse the same schema preparation as the standard EDL pipeline.
        edl_path: str = kw.get("edl_path", "edl/edl_schema.edl")
        db_host: str = kw["db_host"]
        db_port: int = kw["db_port"]
        db_name: str = kw["db_name"]
        db_user: str = kw["db_user"]
        db_password: str = kw["db_password"]

        schema = parse_edl(edl_path)
        load_schema_to_postgres(
            schema,
            host=db_host,
            port=db_port,
            db=db_name,
            user=db_user,
            password=db_password,
        )

    def generate_data(self, **kw) -> Dict[str, pd.DataFrame]:
        edl_path: str = kw.get("edl_path", "edl/edl_schema.edl")

        # Parse EDL and build NeMo-compatible metadata
        schema = parse_edl(edl_path)
        entities_by_name, dependency_order = build_nemo_metadata(schema)

        # Table generation specs for the finance EDL schema
        specs = [
            TableGenerationSpec("Customer", 1000),
            TableGenerationSpec("Branch", 50),
            TableGenerationSpec("Account", 5000),
            TableGenerationSpec("Card", 8000),
            TableGenerationSpec("Merchant", 500),
            TableGenerationSpec("Transaction", 50000),
            TableGenerationSpec("Loan", 1000),
            TableGenerationSpec("LoanPayment", 10000),
        ]

        engine = NeMoEngine()
        data_by_table = engine.generate_dataset(
            entities_by_name=entities_by_name,
            dependency_order=dependency_order,
            table_specs=specs,
        )

        # Convert list-of-dicts into DataFrames for downstream loaders
        dataframes: Dict[str, pd.DataFrame] = {}
        for table_name, rows in data_by_table.items():
            dataframes[table_name] = pd.DataFrame(rows)

        return dataframes

    def load_data(self, data: Dict[str, pd.DataFrame], **kw) -> None:
        db_host: str = kw["db_host"]
        db_port: int = kw["db_port"]
        db_name: str = kw["db_name"]
        db_user: str = kw["db_user"]
        db_password: str = kw["db_password"]
        append: bool = kw.get("append", False)

        write_to_postgres(
            data,
            host=db_host,
            port=db_port,
            db=db_name,
            user=db_user,
            password=db_password,
            append=append,
        )

    def validate(self, **kw) -> None:
        edl_path: str = kw.get("edl_path", "edl/edl_schema.edl")
        db_host: str = kw["db_host"]
        db_port: int = kw["db_port"]
        db_name: str = kw["db_name"]
        db_user: str = kw["db_user"]
        db_password: str = kw["db_password"]
        rows: int = kw.get("rows", 1000)

        schema = parse_edl(edl_path)
        validate_pk_fk(schema, host=db_host, port=db_port, db=db_name, user=db_user, password=db_password)
        click.echo(f"EDL NeMo pipeline complete with fixed NeMo row targets; nominal scale={rows}")


register_pipeline(EdlPipeline())
register_pipeline(NemoEdlPipeline())
