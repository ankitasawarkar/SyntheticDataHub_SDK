import re
from typing import List, Tuple
from .metadata_model import SchemaMeta, TableMeta, FieldMeta, RelationshipMeta


def _find_blocks(text: str, header_pattern: str) -> List[Tuple[str, str]]:
    """Find blocks like 'ENTITY Name { ... }' or 'RELATIONSHIP Name { ... }'."""
    blocks = []
    for m in re.finditer(header_pattern, text):
        name = m.group(1)
        start_brace = text.find('{', m.end() - 1)
        if start_brace == -1:
            continue
        depth = 0
        i = start_brace
        while i < len(text):
            ch = text[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    body = text[start_brace + 1 : i]
                    blocks.append((name, body))
                    break
            i += 1
    return blocks


def parse_edl(edl_path: str) -> SchemaMeta:
    with open(edl_path, "r") as f:
        text = f.read()

    schema = SchemaMeta()

    entity_blocks = _find_blocks(text, r"\bENTITY\s+(\w+)\s*{")
    rel_blocks = _find_blocks(text, r"\bRELATIONSHIP\s+(\w+)\s*{")

    for entity_name, body in entity_blocks:
        table = TableMeta(name=entity_name)

        attr_blocks = re.findall(r"ATTRIBUTE\s+(\w+)\s*{(.*?)}", body, re.S)
        for attr_name, attr_body in attr_blocks:
            type_match = re.search(r"TYPE\s*=\s*(\w+)", attr_body)
            length_match = re.search(r"LENGTH\s*=\s*(\d+)", attr_body)
            prec_match = re.search(r"PRECISION\s*=\s*(\d+)", attr_body)
            scale_match = re.search(r"SCALE\s*=\s*(\d+)", attr_body)
            req_match = re.search(r"REQUIRED\s*=\s*(TRUE|FALSE)", attr_body)
            allowed_match = re.search(r"ALLOWED_VALUES\s*=\s*\[(.*?)\]", attr_body, re.S)

            dtype = type_match.group(1) if type_match else "STRING"
            length = int(length_match.group(1)) if length_match else None
            prec = int(prec_match.group(1)) if prec_match else None
            scale = int(scale_match.group(1)) if scale_match else None
            required = req_match and req_match.group(1) == "TRUE"

            allowed_values = None
            if allowed_match:
                raw = allowed_match.group(1)
                allowed_values = [v.strip().strip('"') for v in raw.split(",")]

            field = FieldMeta(
                name=attr_name,
                type=dtype,
                length=length,
                precision=prec,
                scale=scale,
                required=required,
                allowed_values=allowed_values,
            )
            table.fields[attr_name] = field

        pk_match = re.search(r"PRIMARY KEY\s*\((.*?)\)", body)
        if pk_match:
            table.primary_key = pk_match.group(1).strip()

        schema.tables[entity_name] = table

    for rel_name, body in rel_blocks:
        parent = re.search(r"PARENT\s*=\s*(\w+)\((\w+)\)", body)
        child = re.search(r"CHILD\s*=\s*(\w+)\((\w+)\)", body)
        card = re.search(r"CARDINALITY\s*=\s*\"(.*?)\"", body)

        rel = RelationshipMeta(
            parent_table=parent.group(1),
            parent_key=parent.group(2),
            child_table=child.group(1),
            child_key=child.group(2),
            cardinality=card.group(1) if card else "UNKNOWN",
        )
        schema.relationships.append(rel)

    return schema
