"""Versioned STRATA SQLite migrations."""

from __future__ import annotations

import sqlite3

from .schema import STRATA_SCHEMA


LATEST_SCHEMA_VERSION = 2


class SchemaVersionError(RuntimeError):
    """Raised when a project cannot be opened safely at its schema version."""


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return {str(row[0]) for row in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_v1_project_table(conn: sqlite3.Connection) -> None:
    tables = _tables(conn)
    if "strata_project" not in tables and "projects" in tables:
        conn.execute("ALTER TABLE projects RENAME TO strata_project")
    elif "strata_project" not in tables:
        raise SchemaVersionError("schema v1 has no project table to migrate")

    columns = _columns(conn, "strata_project")
    if "title" not in columns:
        conn.execute("ALTER TABLE strata_project ADD COLUMN title TEXT NOT NULL DEFAULT ''")
        if "name" in columns:
            conn.execute("UPDATE strata_project SET title=name WHERE title='' OR title IS NULL")
    if "description" not in columns:
        conn.execute("ALTER TABLE strata_project ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    if "created_at" not in columns:
        raise SchemaVersionError("schema v1 project table is missing created_at")
    if "updated_at" not in columns:
        raise SchemaVersionError("schema v1 project table is missing updated_at")


def migrate(conn: sqlite3.Connection, *, readonly: bool = False) -> None:
    current = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if current > LATEST_SCHEMA_VERSION:
        raise SchemaVersionError(f"project schema {current} is newer than supported {LATEST_SCHEMA_VERSION}")
    if readonly:
        if current != LATEST_SCHEMA_VERSION:
            raise SchemaVersionError(f"read-only open requires schema {LATEST_SCHEMA_VERSION}; found {current}")
        return

    tables = _tables(conn)
    if current == 0:
        if tables:
            raise SchemaVersionError("unversioned SQLite tables found; refusing to relabel them")
        conn.executescript(STRATA_SCHEMA)
        conn.execute(f"PRAGMA user_version = {LATEST_SCHEMA_VERSION}")
        conn.commit()
        return

    if current == 1:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _migrate_v1_project_table(conn)
            conn.executescript(STRATA_SCHEMA)
            conn.execute(f"PRAGMA user_version = {LATEST_SCHEMA_VERSION}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return

    if current != LATEST_SCHEMA_VERSION:
        raise SchemaVersionError(f"unsupported project schema {current}")

