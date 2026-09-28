"""Safe, resumable source registration for common evidence formats."""

from __future__ import annotations

import csv
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .project import StrataProject


EXTENSIONS = {
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".tif": "geotiff", ".tiff": "geotiff",
    ".pdf": "pdf", ".geojson": "geojson", ".json": "json", ".csv": "csv", ".las": "las",
    ".laz": "laz", ".gltf": "gltf", ".glb": "gltf", ".obj": "obj", ".txt": "text", ".md": "text",
}


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    path: Path
    kind: str
    media_type: str
    size: int


@dataclass(frozen=True, slots=True)
class ImportPlan:
    descriptor: SourceDescriptor
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ImportResult:
    source: dict[str, Any]
    source_file: dict[str, Any]
    job: dict[str, Any]


def describe(path: str | Path, kind: str | None = None) -> SourceDescriptor:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    return SourceDescriptor(source, kind or EXTENSIONS.get(source.suffix.lower(), "binary"), mimetypes.guess_type(source.name)[0] or "application/octet-stream", source.stat().st_size)


def inspect(descriptor: SourceDescriptor) -> ImportPlan:
    metadata: dict[str, Any] = {"name": descriptor.path.name, "size": descriptor.size, "media_type": descriptor.media_type, "kind": descriptor.kind}
    if descriptor.kind in {"json", "geojson", "gltf"} and descriptor.size <= 25_000_000:
        try:
            value = json.loads(descriptor.path.read_text(encoding="utf-8"))
            metadata["json_type"] = value.get("type") if isinstance(value, dict) else type(value).__name__
            if descriptor.kind == "geojson" and isinstance(value, dict):
                metadata["feature_count"] = len(value.get("features", []))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            metadata["parse_error"] = str(exc)
    elif descriptor.kind == "csv":
        with descriptor.path.open(newline="", encoding="utf-8", errors="replace") as handle:
            metadata["columns"] = next(csv.reader(handle), [])
    return ImportPlan(descriptor, metadata)


def import_file(project: StrataProject, path: str | Path, kind: str | None = None, title: str | None = None) -> ImportResult:
    plan = inspect(describe(path, kind))
    blob = project.blobs.put_file(plan.descriptor.path, plan.descriptor.media_type)
    source = project.db.add_source(project.project_id, title or plan.descriptor.path.stem, plan.descriptor.kind, str(plan.descriptor.path), blob.hash, plan.metadata)
    source_file = project.db.attach_source_file(source["source_id"], blob.hash, blob.size, blob.media_type, plan.descriptor.path.name)
    job = project.db.add_import_job(project.project_id, "complete", source["source_id"], blob.hash, {"stage": "registered"})
    return ImportResult(source, source_file, job)

