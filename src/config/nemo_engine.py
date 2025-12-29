# nemo_engine.py

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from .nemo_client import NeMoClient
from .nemo_config_builder import (
    NeMoConfigBuilder,
    EntityMetadata,
    ForeignKeyMetadata,
)

logger = logging.getLogger(__name__)


@dataclass
class TableGenerationSpec:
    """
    How many rows to generate for each table.

    Example:
        TableGenerationSpec(
            entity_name="Customer",
            num_rows=1000
        )
    """
    entity_name: str
    num_rows: int


class NeMoEngine:
    """
    NeMo-backed synthetic data engine.

    Responsibility:
    - Take EDL-derived schema metadata
    - Respect dependency ordering (parent -> child)
    - Call NeMo per table with a config built from metadata
    - Feed parent PK values into child FK domains for referential integrity
    - Return synthetic data for loading into Postgres (or wherever)
    """

    def __init__(
        self,
        nemo_client: Optional[NeMoClient] = None,
        config_builder: Optional[NeMoConfigBuilder] = None,
    ) -> None:
        self.client = nemo_client or NeMoClient()
        self.config_builder = config_builder or NeMoConfigBuilder()

    def generate_dataset(
        self,
        entities_by_name: Mapping[str, EntityMetadata],
        dependency_order: List[str],
        table_specs: List[TableGenerationSpec],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate a full synthetic dataset across multiple tables.

        Parameters
        ----------
        entities_by_name:
            Mapping from entity name to metadata.
        dependency_order:
            List of entity names in parent-first order.
        table_specs:
            How many rows to generate per table.

        Returns
        -------
        Dict[str, List[Dict[str, Any]]]:
            Mapping from table/entity name -> list of synthetic rows.
        """
        table_spec_map: Dict[str, int] = {
            spec.entity_name: spec.num_rows for spec in table_specs
        }

        generated_data: Dict[str, List[Dict[str, Any]]] = {}
        # Cache of PK values per entity/column
        pk_values: Dict[str, Dict[str, List[Any]]] = {}

        for entity_name in dependency_order:
            entity = entities_by_name[entity_name]
            num_rows = table_spec_map.get(entity_name)
            if num_rows is None:
                logger.warning(
                    "No TableGenerationSpec found for entity=%s; skipping", entity_name
                )
                continue

            logger.info(
                "Generating entity=%s, rows=%s", entity_name, num_rows
            )

            # Prepare parent FK value domain for this entity
            fk_parent_values = self._collect_fk_parent_values(
                entity=entity,
                generated_data=generated_data,
                entities_by_name=entities_by_name,
                pk_values=pk_values,
            )

            # Build NeMo config
            nemo_config = self.config_builder.build_table_config(
                entity=entity,
                parent_key_values=fk_parent_values,
            )

            # Call NeMo
            rows = self.client.generate_table(
                table_name=entity_name,
                nemo_config=nemo_config,
                num_rows=num_rows,
            )

            # Save generated rows
            generated_data[entity_name] = rows

            # Extract PK values for children to use
            pk_values[entity_name] = self._extract_pk_values(entity, rows)

        return generated_data

    def _collect_fk_parent_values(
        self,
        entity: EntityMetadata,
        generated_data: Dict[str, List[Dict[str, Any]]],
        entities_by_name: Mapping[str, EntityMetadata],
        pk_values: Dict[str, Dict[str, List[Any]]],
    ) -> Dict[str, List[Any]]:
        """
        For the current entity, determine allowed values for FK columns
        based on already-generated parent tables.

        Returns mapping FK column name -> list of allowed values.
        """
        fk_value_domains: Dict[str, List[Any]] = {}

        for fk in entity.foreign_keys:
            parent_entity_name = fk.ref_entity
            parent_column_name = fk.ref_column
            fk_column_name = fk.column

            parent_pk_map = pk_values.get(parent_entity_name)
            if not parent_pk_map:
                # Parent not generated yet or has no PK values cached
                continue

            parent_values = parent_pk_map.get(parent_column_name)
            if not parent_values:
                continue

            fk_value_domains[fk_column_name] = parent_values

        return fk_value_domains

    @staticmethod
    def _extract_pk_values(
        entity: EntityMetadata,
        rows: List[Dict[str, Any]],
    ) -> Dict[str, List[Any]]:
        """
        Extract primary key column values from generated rows.

        Returns
        -------
        Dict[column_name, List[value]]
        """
        pk_map: Dict[str, List[Any]] = {col: [] for col in entity.primary_key}

        for row in rows:
            for col in entity.primary_key:
                if col in row:
                    pk_map[col].append(row[col])

        return pk_map