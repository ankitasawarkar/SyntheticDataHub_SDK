# nemo_config_builder.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ---- Assumed metadata structures ----
# Replace these with imports from your SDK

@dataclass
class AttributeMetadata:
    name: str
    type: str  # e.g. "STRING", "INT", "DECIMAL", "DATE", "TIMESTAMP", "EMAIL", "SSN", "DOUBLE"
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    required: bool = False
    allowed_values: Optional[List[str]] = None


@dataclass
class ForeignKeyMetadata:
    column: str
    ref_entity: str
    ref_column: str
    # You might have more fields (on_delete, etc.)


@dataclass
class EntityMetadata:
    name: str
    description: Optional[str]
    attributes: List[AttributeMetadata]
    primary_key: List[str]
    foreign_keys: List[ForeignKeyMetadata]


class NeMoConfigBuilder:
    """
    Converts internal EDL/metadata structures into NeMo Data Designer-compatible configs.

    This is the only place that "knows" about NeMo's config shape.
    """

    def __init__(self) -> None:
        # If NeMo offers presets/models, you can inject them here later.
        pass

    def build_table_config(
        self,
        entity: EntityMetadata,
        parent_key_values: Optional[Dict[str, List[Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Build NeMo config for a single table/entity.

        Parameters
        ----------
        entity:
            EDL-derived metadata for the table.
        parent_key_values:
            Mapping of FK column -> list of allowed values derived from parent tables.
            Example: {"customer_id": ["c1", "c2", ...]}

        Returns
        -------
        Dict[str, Any]:
            NeMo-specific configuration for generating this table.
        """
        columns: List[Dict[str, Any]] = []

        for attr in entity.attributes:
            col_config = self._build_column_config(attr, entity, parent_key_values)
            columns.append(col_config)

        config: Dict[str, Any] = {
            "description": entity.description or entity.name,
            "columns": columns,
            # Optional: you can include modeling hints or LLM parameters here
            # "model": {...}
        }

        return config

    def _build_column_config(
        self,
        attr: AttributeMetadata,
        entity: EntityMetadata,
        parent_key_values: Optional[Dict[str, List[Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Build NeMo column configuration from an attribute.
        """
        # Base type mapping
        nemo_type = self._map_type(attr)

        # Base column config
        column: Dict[str, Any] = {
            "name": attr.name,
            "type": nemo_type,
            "nullable": not attr.required,
        }

        # Attach domain-specific constraints
        if attr.allowed_values:
            column["domain"] = {
                "type": "categorical",
                "values": attr.allowed_values,
            }

        # Email / SSN / card-like patterns can get regex/pattern constraints
        if attr.type.upper() == "EMAIL":
            column["pattern"] = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

        if attr.type.upper() == "SSN":
            # US SSN pattern (dummy, you can change)
            column["pattern"] = r"^\d{3}-\d{2}-\d{4}$"

        # FK columns: restrict values to parent_key_values if provided
        if parent_key_values and attr.name in parent_key_values:
            column["domain"] = {
                "type": "categorical",
                "values": parent_key_values[attr.name],
            }

        # PK columns: you might want special generators for IDs
        if attr.name in entity.primary_key:
            column.setdefault("generator", "uuid")

        # Length, precision, scale hints
        if attr.length is not None:
            column.setdefault("max_length", attr.length)

        if attr.precision is not None:
            column.setdefault("precision", attr.precision)
        if attr.scale is not None:
            column.setdefault("scale", attr.scale)

        return column

    def _map_type(self, attr: AttributeMetadata) -> str:
        """
        Map EDL types to NeMo primitive types.
        Adapt this to match the actual NeMo Data Designer schema.
        """
        t = attr.type.upper()

        if t in {"STRING", "EMAIL", "SSN"}:
            return "string"
        if t in {"INT"}:
            return "integer"
        if t in {"DECIMAL", "DOUBLE"}:
            return "float"
        if t == "DATE":
            return "date"
        if t == "TIMESTAMP":
            return "datetime"

        # Default fallback
        return "string"