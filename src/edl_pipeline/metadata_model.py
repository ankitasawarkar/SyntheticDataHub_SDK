from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FieldMeta:
    name: str
    type: str
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    required: bool = False
    allowed_values: Optional[List[str]] = None


@dataclass
class TableMeta:
    name: str
    fields: Dict[str, FieldMeta] = field(default_factory=dict)
    primary_key: Optional[str] = None


@dataclass
class RelationshipMeta:
    parent_table: str
    parent_key: str
    child_table: str
    child_key: str
    cardinality: str


@dataclass
class SchemaMeta:
    tables: Dict[str, TableMeta] = field(default_factory=dict)
    relationships: List[RelationshipMeta] = field(default_factory=list)
