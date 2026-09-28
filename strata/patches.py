"""Offline collaboration patches with explicit base-hash checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def project_hash(project_root: str | Path) -> str:
    root = Path(project_root)
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".git" not in path.parts and "cache" not in path.parts and "logs" not in path.parts:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def create_patch(base_project_hash: str, author: str, changes: list[dict[str, Any]], blobs: list[str] | None = None) -> dict[str, Any]:
    return {"format": "stratapatch-1", "base_project_hash": base_project_hash, "author": author, "changes": changes, "blobs": blobs or []}


def write_patch(patch: dict[str, Any], output: str | Path) -> Path:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(patch, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def read_patch(path: str | Path) -> dict[str, Any]:
    patch = json.loads(Path(path).read_text(encoding="utf-8"))
    if patch.get("format") != "stratapatch-1":
        raise ValueError("unsupported STRATA patch format")
    return patch

