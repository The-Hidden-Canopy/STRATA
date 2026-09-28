"""STRATA-owned SQLite primitives and domain errors."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .migrations import migrate


def dumps(value: Any) -> str:
    return json.dumps(value if value is not None else [], separators=(",", ":"), sort_keys=True)


def loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return [] if default is None else default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return [] if default is None else default


class StrataError(Exception):
    """Base error for expected STRATA storage failures."""


class NotFoundError(StrataError):
    pass


class ConflictError(StrataError):
    pass


class ValidationError(StrataError):
    pass


class ReadOnlyError(StrataError):
    pass


class SQLiteStore:
    """Small STRATA-owned SQLite base with explicit read/write mode."""

    def __init__(self, path: str | Path, *, readonly: bool = False) -> None:
        self.path = Path(path)
        self.readonly = readonly
        self.dirty = False
        if readonly:
            uri = f"file:{self.path.resolve().as_posix()}?mode=ro"
            self.conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if not readonly:
            self.conn.execute("PRAGMA journal_mode = WAL")
        migrate(self.conn, readonly=readonly)

    @contextmanager
    def _tx(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        if write and self.readonly:
            raise ReadOnlyError(f"read-only STRATA project: {self.path}")
        try:
            with self.conn:
                yield self.conn
        except Exception:
            raise
        else:
            if write:
                self.dirty = True

    @staticmethod
    def _require_project(conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM strata_project WHERE project_id=?", (project_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"project not found: {project_id}")
        return row

    def close(self) -> None:
        self.conn.close()

