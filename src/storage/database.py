"""SQLite database layer with tenant-aware schema (ARCHITECTURE.md Appendix B)."""

import sqlite3
from pathlib import Path
from typing import Optional
from src.config import DATABASE_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS evidence_records (
    record_id       TEXT PRIMARY KEY,
    schema_version  TEXT NOT NULL DEFAULT '1.0.0',
    org_id          TEXT NOT NULL,
    client_id       TEXT,
    agent           TEXT NOT NULL DEFAULT 'returns-manager@1.0.0',
    unit_id         TEXT NOT NULL,
    order_id        TEXT,
    ordered_sku     TEXT,
    ordered_asin    TEXT,
    operator_id     TEXT,
    captured_at     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'completed',
    content_hash    TEXT,
    checks_json     TEXT NOT NULL,
    outcome_json    TEXT NOT NULL,
    images_json     TEXT,
    overrides_json  TEXT DEFAULT '[]',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_records_org ON evidence_records(org_id);
CREATE INDEX IF NOT EXISTS idx_records_unit ON evidence_records(org_id, unit_id);
CREATE INDEX IF NOT EXISTS idx_records_status ON evidence_records(org_id, status);
"""


_initialized_dbs: set[str] = set()


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a SQLite database connection with row factory configured and schema initialized."""
    target_path = db_path or DATABASE_PATH
    db_file = Path(target_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    if target_path not in _initialized_dbs:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        _initialized_dbs.add(target_path)

    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize the SQLite database schema explicitly."""
    target_path = db_path or DATABASE_PATH
    with get_db_connection(target_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        _initialized_dbs.add(target_path)
