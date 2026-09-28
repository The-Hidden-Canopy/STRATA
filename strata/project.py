"""Portable local STRATA project workspace."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .blobs import BlobStore
from .ids import new_id
from .store import StrataDatabase


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class StrataProject:
    """A directory-form ``.strata`` project with SQLite and blob storage."""

    MANIFEST = "manifest.json"

    def __init__(self, root: str | Path, manifest: dict[str, Any], db: StrataDatabase):
        self.root = Path(root)
        self.manifest = manifest
        self.db = db
        self.blobs = BlobStore(self.root / "blobs")

    @property
    def project_id(self) -> str:
        return str(self.manifest["project_id"])

    @property
    def default_branch(self) -> str:
        return str(self.manifest.get("default_branch", "main"))

    @classmethod
    def create(
        cls,
        root: str | Path,
        title: str,
        description: str = "",
        canonical_crs: dict[str, Any] | None = None,
        local_origin: dict[str, float] | None = None,
    ) -> "StrataProject":
        target = Path(root)
        target.mkdir(parents=True, exist_ok=True)
        if (target / cls.MANIFEST).exists():
            raise FileExistsError(f"STRATA project already exists: {target}")
        for directory in ("blobs", "previews", "exports", "cache", "logs"):
            (target / directory).mkdir(exist_ok=True)
        project_id = new_id("project")
        manifest = {
            "format": {"major": 1, "minor": 0},
            "project_id": project_id,
            "title": title,
            "description": description,
            "created_at": utc_now(),
            "modified_at": utc_now(),
            "canonical_crs": canonical_crs or {},
            "local_origin": local_origin or {"latitude": 0.0, "longitude": 0.0, "height_m": 0.0},
            "default_branch": "main",
            "default_time": "unknown",
            "database": "project.db",
        }
        db = StrataDatabase(target / "project.db")
        db.ensure_project(project_id, title, description)
        result = cls(target, manifest, db)
        result.save_manifest()
        db.create_branch(project_id, "main", description="Default reconstruction branch")
        return result

    @classmethod
    def open(cls, root: str | Path) -> "StrataProject":
        target = Path(root)
        manifest_path = target / cls.MANIFEST
        if not manifest_path.is_file():
            raise FileNotFoundError(f"not a STRATA project directory: {target}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        db = StrataDatabase(target / manifest.get("database", "project.db"))
        return cls(target, manifest, db)

    def save_manifest(self) -> None:
        self.manifest["modified_at"] = utc_now()
        temporary = self.root / f"{self.MANIFEST}.partial"
        temporary.write_text(json.dumps(self.manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.root / self.MANIFEST)

    def close(self) -> None:
        self.save_manifest()
        self.db.close()

    def __enter__(self) -> "StrataProject":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

