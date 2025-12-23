import json
from typing import Dict, Optional
import pandas as pd
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker()

def load_generator_config(path: str) -> Dict:
    with open(path, "r") as f:
        return json.load(f)

def generate_table_rows(table_name: str, table_cfg: Dict, n: int,
                        parents_data: Dict[str, pd.DataFrame],
                        pk_offset: int = 0) -> pd.DataFrame:
    rows = []
    pk = table_cfg["primary_key"]
    fields = table_cfg["fields"]

    for i in range(n):
        row = {}
        for fname, meta in fields.items():
            ftype = meta["type"].upper()
            allowed = meta.get("allowed_values")
            length = meta.get("length")
            precision = meta.get("precision")
            scale = meta.get("scale")
            if fname == pk:
                # deterministic PK, with optional offset for append mode
                row[fname] = f"{table_name[:3].upper()}_{pk_offset + i + 1:06d}"
            elif ftype == "EMAIL":
                row[fname] = fake.email()
            elif ftype == "SSN":
                # US-style Social Security Number pattern
                row[fname] = fake.ssn()
            elif ftype in ("INT", "INTEGER", "BIGINT"):
                if table_name == "Customer" and fname == "marketing_opt_in":
                    # 0 = opt-out, 1 = opt-in
                    row[fname] = random.choice([0, 1])
                else:
                    row[fname] = random.randint(0, 1_000_000)
            elif ftype == "BOOLEAN":
                row[fname] = random.choice([True, False])
            elif ftype in ("DOUBLE", "FLOAT", "REAL"):
                row[fname] = round(random.uniform(0, 1000), 6)
            elif allowed:
                row[fname] = random.choice(allowed)
            elif ftype == "STRING":
                # Respect max length when provided
                if isinstance(length, int) and length > 0:
                    # generate random ascii string up to the length
                    row[fname] = fake.pystr(min_chars=1, max_chars=length)
                else:
                    row[fname] = fake.word()
            elif ftype == "DATE":
                row[fname] = fake.date_between(start_date="-10y", end_date="today")
            elif ftype == "TIMESTAMP":
                dt = fake.date_time_between(start_date="-2y", end_date="now")
                row[fname] = dt
            elif ftype == "DECIMAL":
                # Respect precision/scale but keep amounts in realistic ranges.
                p = precision if isinstance(precision, int) and precision > 0 else 18
                s = scale if isinstance(scale, int) and 0 <= scale < p else 2

                # Domain-specific ranges for finance amounts
                if table_name == "Loan" and fname == "principal_amount":
                    # Loan principal between 1k and 5M
                    value = random.uniform(1_000, 5_000_000)
                elif table_name == "LoanPayment" and fname == "amount":
                    # Loan payment between 100 and 50k
                    value = random.uniform(100, 50_000)
                elif table_name == "Transaction" and fname == "amount":
                    # Transaction amount between 1 and 10k
                    value = random.uniform(1, 10_000)
                else:
                    # Generic fallback based on precision
                    max_int_part = min(10 ** (p - s) - 1, 1_000_000_000)
                    value = random.uniform(0, max_int_part)

                row[fname] = round(value, s)
            else:
                row[fname] = fake.word()
        rows.append(row)

    df = pd.DataFrame(rows)
    return df

def apply_relationships(cfg: Dict,
                        data: Dict[str, pd.DataFrame],
                        rows_per_child: int):
    rels = cfg["relationships"]
    for rel in rels:
        parent = rel["parent_table"]
        child = rel["child_table"]
        parent_key = rel["parent_key"]
        child_key = rel["child_key"]

        parent_df = data[parent]
        child_df = data.get(child)
        if child_df is None or parent_df.empty:
            continue

        parent_ids = parent_df[parent_key].tolist()
        # assign FKs randomly
        child_df[child_key] = [
            random.choice(parent_ids) for _ in range(len(child_df))
        ]
        data[child] = child_df

def generate_synthetic_data(cfg_path: str,
                            rows_per_table: int = 100,
                            pk_offsets: Optional[Dict[str, int]] = None
                            ) -> Dict[str, pd.DataFrame]:
    cfg = load_generator_config(cfg_path)
    tables_cfg = cfg["tables"]

    # naive order: generate all tables first, then fix FKs by relationships
    data = {}
    for tname, tcfg in tables_cfg.items():
        offset = 0
        if pk_offsets and tname in pk_offsets:
            offset = pk_offsets[tname]
        data[tname] = generate_table_rows(tname, tcfg, rows_per_table, data, pk_offset=offset)

    apply_relationships(cfg, data, rows_per_table)
    return data