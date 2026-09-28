"""Offline collaboration patches with explicit base-hash checks."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


def project_hash(project_root: str | Path) -> str:
    """Return a canonical identity for authoritative project state.

    Disposable exports, previews, caches, logs, partial files, and SQLite
    journal sidecars never participate in this hash.
    """
    root = Path(project_root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest.pop("modified_at", None)
    manifest_hash = hashlib.sha256(_canonical(manifest)).hexdigest()
    database_hash = _database_hash(root / manifest.get("database", "project.db"))
    blob_hashes = []
    blob_root = root / "blobs"
    for path in (sorted(blob_root.rglob("*")) if blob_root.is_dir() else []):
        if path.is_file() and not path.name.endswith((".partial", "-wal", "-shm")):
            blob_hashes.append({"path": path.relative_to(blob_root).as_posix(), "hash": _file_hash(path)})
    blob_tree_hash = hashlib.sha256(_canonical(blob_hashes)).hexdigest()
    root_identity = {
        "format": "strata-project-root-1",
        "manifest_hash": manifest_hash,
        "database_hash": database_hash,
        "blob_tree_hash": blob_tree_hash,
    }
    return hashlib.sha256(_canonical(root_identity)).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _database_hash(path: Path) -> str:
    """Hash a SQLite backup so WAL state is included without checkpointing it."""
    if not path.is_file():
        return "missing"
    with tempfile.TemporaryDirectory(prefix="strata-hash-") as directory:
        copy = Path(directory) / "project.db"
        source = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
        destination = sqlite3.connect(copy)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        return _file_hash(copy)


def create_patch(base_project_hash: str, author: str, changes: list[dict[str, Any]], blobs: list[str] | None = None) -> dict[str, Any]:
    return {"format": "strata-patch-1", "base_project_hash": base_project_hash, "author": author, "changes": changes, "blobs": blobs or []}


def write_patch(patch: dict[str, Any], output: str | Path) -> Path:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(patch, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def read_patch(path: str | Path) -> dict[str, Any]:
    patch = json.loads(Path(path).read_text(encoding="utf-8"))
    if patch.get("format") != "strata-patch-1":
        raise ValueError("unsupported STRATA patch format")
    return patch
