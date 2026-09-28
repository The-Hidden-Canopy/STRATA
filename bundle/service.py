"""Application service helpers used by the CLI and HTTP surface."""

from __future__ import annotations

from pathlib import Path

from .store import Database


def open_database(path: str | Path | None = None) -> Database:
    return Database(Path(path or ".bundle/bundle.db"))
