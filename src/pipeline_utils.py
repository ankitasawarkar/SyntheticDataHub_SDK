from __future__ import annotations

from typing import Dict

import psycopg2


def compute_pk_offsets(cfg: Dict, host: str, port: int, db: str, user: str, password: str) -> Dict[str, int]:
    """Compute per-table PK offsets based on existing data in Postgres.

    This ensures that in append mode, new deterministic PKs continue from
    the current maximum instead of restarting at 1, avoiding conflicts.
    """

    tables_cfg = cfg.get("tables", {})
    offsets: Dict[str, int] = {}

    if not tables_cfg:
        return offsets

    conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=password)
    cur = conn.cursor()

    try:
        for tname, tcfg in tables_cfg.items():
            pk = tcfg.get("primary_key")
            if not pk:
                continue

            cur.execute(f'SELECT MAX("{pk}") FROM "{tname}"')
            row = cur.fetchone()
            max_pk = row[0]
            if max_pk is None:
                offsets[tname] = 0
                continue

            # Extract trailing digits from the PK value, e.g. CUS_000123 -> 123
            s = str(max_pk)
            digits = ""
            for ch in reversed(s):
                if ch.isdigit():
                    digits = ch + digits
                else:
                    break

            offsets[tname] = int(digits) if digits else 0
    finally:
        cur.close()
        conn.close()

    return offsets
