import json
from pathlib import Path
from metadata_model import SchemaMeta

def schema_to_generator_config(schema: SchemaMeta, out_path: str):
    cfg = {
        "tables": {},
        "relationships": []
    }

    for name, table in schema.tables.items():
        cfg["tables"][name] = {
            "primary_key": table.primary_key,
            "fields": {
                fname: {
                    "type": fmeta.type,
                    "required": fmeta.required,
                    "allowed_values": fmeta.allowed_values,
                    "length": fmeta.length,
                    "precision": fmeta.precision,
                    "scale": fmeta.scale
                }
                for fname, fmeta in table.fields.items()
            }
        }

    for rel in schema.relationships:
        cfg["relationships"].append({
            "parent_table": rel.parent_table,
            "parent_key": rel.parent_key,
            "child_table": rel.child_table,
            "child_key": rel.child_key
        })

    # Ensure parent directory exists (e.g., artifacts/)
    p = Path(out_path)
    if p.parent:
        p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        json.dump(cfg, f, indent=2)