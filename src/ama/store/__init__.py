"""
Storage. One interface, two backends:

    SQLite + sqlite-vec (default)   AMA_DATABASE_URL blank -> $AMA_HOME/ama.db, nothing to install
    Postgres + pgvector             AMA_DATABASE_URL=postgresql://user:pass@host:5432/db

The Postgres backend works on an existing AMA 2.x database (table `dilemmas`) and adds what it needs.
If Postgres is configured but unreachable, AMA stops with a clear error rather than silently switching:
two databases would split the knowledge base.
"""
from __future__ import annotations

from ..config import get_settings
from .base import Store

_store: Store | None = None


def get_store(reload: bool = False) -> Store:
    global _store
    if _store is None or reload:
        url = get_settings().effective_database_url
        if url.startswith("sqlite"):
            from .sqlite import SQLiteStore
            _store = SQLiteStore(url.split("sqlite:///", 1)[1])
        elif url.startswith(("postgres://", "postgresql://")):
            from .postgres import PostgresStore
            _store = PostgresStore(url)
        else:
            raise RuntimeError(f"Unsupported AMA_DATABASE_URL: {url.split(':', 1)[0]}://…")
        _store.init()
    return _store
