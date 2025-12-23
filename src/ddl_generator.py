from metadata_model import SchemaMeta, FieldMeta
from typing import Dict

def map_type(field: FieldMeta) -> str:
    t = field.type.upper()
    if t in ("STRING", "EMAIL", "SSN"):
        length = field.length or 255
        return f"VARCHAR({length})"
    if t == "DATE":
        return "DATE"
    if t == "TIMESTAMP":
        return "TIMESTAMP"
    if t in ("INT", "INTEGER"):
        return "INTEGER"
    if t == "BIGINT":
        return "BIGINT"
    if t == "BOOLEAN":
        return "BOOLEAN"
    if t in ("DOUBLE", "FLOAT", "REAL"):
        return "DOUBLE PRECISION"
    if t == "DECIMAL":
        prec = field.precision or 18
        scale = field.scale or 2
        return f"DECIMAL({prec},{scale})"
    # default
    return "TEXT"

def generate_ddl(schema: SchemaMeta) -> Dict[str, str]:
    ddls = {}
    for table_name, table in schema.tables.items():
        cols_sql = []
        for field in table.fields.values():
            col_def = f'"{field.name}" {map_type(field)}'
            if field.required:
                col_def += " NOT NULL"
            cols_sql.append(col_def)

        if table.primary_key:
            cols_sql.append(f'PRIMARY KEY ("{table.primary_key}")')

        table_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n  ' + ",\n  ".join(cols_sql) + "\n);"
        ddls[table_name] = table_sql
    return ddls

def generate_fk_constraints(schema: SchemaMeta) -> Dict[str, str]:
    fk_ddls = {}
    for rel in schema.relationships:
        name = f"fk_{rel.child_table.lower()}_{rel.child_key.lower()}"
        sql = (
            f'ALTER TABLE "{rel.child_table}" '
            f'ADD CONSTRAINT {name} FOREIGN KEY ("{rel.child_key}") '
            f'REFERENCES "{rel.parent_table}"("{rel.parent_key}");'
        )
        fk_ddls[name] = sql
    return fk_ddls