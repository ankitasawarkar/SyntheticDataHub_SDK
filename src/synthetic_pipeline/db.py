import os
from dataclasses import dataclass
from typing import Optional, Dict
from contextlib import contextmanager

from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from dotenv import load_dotenv


# Load variables from a .env file once at import time (if present).
load_dotenv()


@dataclass
class DBConfig:
    """Basic Postgres-style settings, mainly for fallback.

    In normal use you just set DB_CONFIG in .env to any SQLAlchemy URL
    and call get_connection() with no arguments. DBConfig only matters
    if DB_CONFIG is missing.
    """

    host: str = "localhost"
    port: int = 5432
    dbname: str = "jdf"
    user: str = "postgres"
    password: str = "postgres"


def _resolve_url(config: Optional[DBConfig] = None) -> str:
    """Resolve a SQLAlchemy URL from env or DBConfig.

    Priority:
    1) DB_CONFIG from environment / .env (generic, any database)
    2) Build a Postgres URL from DBConfig (fallback for existing code)
    """

    env_url = os.getenv("DB_CONFIG")
    if env_url:
        # be tolerant of accidental surrounding quotes in .env
        return env_url.strip().strip('"').strip("'")

    cfg = config or DBConfig()
    return (
        f"postgresql+psycopg2://{cfg.user}:{cfg.password}"
        f"@{cfg.host}:{cfg.port}/{cfg.dbname}"
    )


_ENGINE_CACHE: Dict[str, Engine] = {}


def _get_engine(url: str) -> Engine:
    """Return a cached SQLAlchemy Engine for the given URL.

    This avoids creating a new Engine (and underlying connection pool)
    for every get_connection() call and helps keep the number of
    concurrent DB connections under control.
    """

    engine = _ENGINE_CACHE.get(url)
    if engine is None:
        engine = create_engine(url)
        _ENGINE_CACHE[url] = engine
    return engine


@contextmanager
def get_connection(config: Optional[DBConfig] = None):
        """Yield a DBAPI connection created via SQLAlchemy.

        Usage everywhere in the pipeline is:

                with get_connection(cfg) as conn:
                        cur = conn.cursor()

        - Generic: set DB_CONFIG to any SQLAlchemy URL (including Databricks) and
            call get_connection() with no arguments.
        - Fallback: if DB_CONFIG is not set, uses DBConfig to build a Postgres URL.
        """

        url = _resolve_url(config)
        engine = _get_engine(url)
        raw_conn = engine.raw_connection()

        # For psycopg2/Postgres URLs, wrap the connection so that
        # conn.cursor() returns a RealDictCursor, which the rest of the
        # pipeline expects (row["col_name"] access).
        if url.startswith("postgresql+psycopg2://"):
            class _RealDictConnection:
                def __init__(self, conn):
                    self._conn = conn

                def cursor(self, *args, **kwargs):
                    kwargs.setdefault("cursor_factory", RealDictCursor)
                    return self._conn.cursor(*args, **kwargs)

                def __getattr__(self, name):  # delegate commit, rollback, etc.
                    return getattr(self._conn, name)

            conn = _RealDictConnection(raw_conn)
        else:
            conn = raw_conn

        try:
            yield conn
        finally:
            raw_conn.close()


def test_sqlalchemy_connection(config: Optional[DBConfig] = None) -> None:
    """Quick health check: uses get_connection() and runs SELECT 1."""

    with get_connection(config) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        rows = cur.fetchall()
        print("SQLAlchemy connection OK, test result:", rows)


if __name__ == "__main__":
    test_sqlalchemy_connection()