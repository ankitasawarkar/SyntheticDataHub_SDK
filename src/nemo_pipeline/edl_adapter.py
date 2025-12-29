from __future__ import annotations

from collections import deque
from typing import Dict, List, Tuple

from edl_pipeline.metadata_model import SchemaMeta, TableMeta, FieldMeta, RelationshipMeta
from config.nemo_config_builder import AttributeMetadata, EntityMetadata, ForeignKeyMetadata


def schema_to_nemo_entities(schema: SchemaMeta) -> Dict[str, EntityMetadata]:
    """Convert EDL SchemaMeta into NeMo EntityMetadata mapping."""
    entities: Dict[str, EntityMetadata] = {}

    for table_name, table in schema.tables.items():
        attributes: List[AttributeMetadata] = []
        for field_name, field in table.fields.items():
            attr = AttributeMetadata(
                name=field_name,
                type=field.type,
                length=field.length,
                precision=field.precision,
                scale=field.scale,
                required=field.required,
                allowed_values=field.allowed_values,
            )
            attributes.append(attr)

        primary_key: List[str] = []
        if table.primary_key:
            primary_key.append(table.primary_key)

        foreign_keys: List[ForeignKeyMetadata] = []
        for rel in schema.relationships:
            if rel.child_table == table_name:
                fk = ForeignKeyMetadata(
                    column=rel.child_key,
                    ref_entity=rel.parent_table,
                    ref_column=rel.parent_key,
                )
                foreign_keys.append(fk)

        entity = EntityMetadata(
            name=table_name,
            description=None,
            attributes=attributes,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
        )
        entities[table_name] = entity

    return entities


def compute_dependency_order(schema: SchemaMeta) -> List[str]:
    """Compute parent-first dependency order based on relationships.

    Uses a simple topological sort over parent->child edges.
    """
    graph: Dict[str, List[str]] = {name: [] for name in schema.tables.keys()}
    indegree: Dict[str, int] = {name: 0 for name in schema.tables.keys()}

    for rel in schema.relationships:
        parent = rel.parent_table
        child = rel.child_table
        if parent not in graph or child not in graph:
            continue
        graph[parent].append(child)
        indegree[child] += 1

    queue: deque[str] = deque(name for name, deg in indegree.items() if deg == 0)
    order: List[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph.get(node, []):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    # Fallback: ensure all tables appear at least once in a stable order.
    for name in schema.tables.keys():
        if name not in order:
            order.append(name)

    return order


def build_nemo_metadata(schema: SchemaMeta) -> Tuple[Dict[str, EntityMetadata], List[str]]:
    """Build NeMo-compatible metadata and dependency order from EDL schema."""
    entities = schema_to_nemo_entities(schema)
    order = compute_dependency_order(schema)
    return entities, order
