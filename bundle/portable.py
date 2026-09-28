"""Portable bundle-project-1 export and import."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from .store import Database, ValidationError


FORMAT = "bundle-project-1"


def export_project(db: Database, project_id: str, archive_path: str | Path) -> Path:
    """Write a self-contained JSON/JSONL project snapshot to a zip archive."""
    project = db.get_project(project_id)
    payloads: dict[str, Any] = {
        "project.json": project,
        "phases.json": db.list_phases(project_id),
        "work.json": db.list_work(project_id),
        "agents.json": db.list_agents(project_id),
        "dependencies.json": db.list_dependencies(project_id),
        "events.jsonl": db.list_events(project_id, 100000),
        "artifacts.json": db.list_artifacts(project_id),
    }
    target = Path(archive_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("format.txt", FORMAT + "\n")
        for name, value in payloads.items():
            if name.endswith(".jsonl"):
                text = "".join(json.dumps(item, sort_keys=True) + "\n" for item in value)
            else:
                text = json.dumps(value, indent=2, sort_keys=True) + "\n"
            archive.writestr(name, text)
    return target


def _read_json(archive: zipfile.ZipFile, name: str, default: Any) -> Any:
    try:
        return json.loads(archive.read(name).decode())
    except KeyError:
        return default


def import_project(db: Database, archive_path: str | Path) -> dict[str, Any]:
    """Import a project snapshot using public store operations.

    IDs are intentionally regenerated; imported records become a new local
    project while preserving titles, dependencies, lanes, and capabilities.
    """
    with zipfile.ZipFile(archive_path) as archive:
        if archive.read("format.txt").decode().strip() != FORMAT:
            raise ValidationError("unsupported Bundle archive format")
        project_data = _read_json(archive, "project.json", {})
        phases = _read_json(archive, "phases.json", [])
        work = _read_json(archive, "work.json", [])
        agents = _read_json(archive, "agents.json", [])
        dependencies = _read_json(archive, "dependencies.json", [])
    imported = db.create_project(project_data.get("name", "Imported project"), project_data.get("description", ""), project_data.get("objective", ""), project_data.get("success_definition", ""))
    project_id = imported["project_id"]
    phase_ids: dict[str, str] = {}
    for phase in phases:
        created = db.create_phase(project_id, phase.get("name", "Phase"), phase.get("objective", ""), phase.get("ordinal"))
        phase_ids[phase.get("phase_id", created["phase_id"])] = created["phase_id"]
    for agent in agents:
        db.create_agent(project_id, agent.get("name", "Imported agent"), agent.get("capabilities", []), agent.get("primary_lane", "core"), agent.get("secondary_lanes", []), agent.get("max_active_claims", 1))
    work_ids: dict[str, str] = {}
    remaining = list(work)
    while remaining:
        progress = False
        for item in remaining[:]:
            deps = [dependency["depends_on_work_id"] for dependency in dependencies if dependency["work_id"] == item.get("work_id")]
            if any(dep not in work_ids for dep in deps):
                continue
            created = db.create_work(project_id, item.get("title", "Imported work"), item.get("objective", ""), item.get("detail", ""), phase_ids.get(item.get("phase_id")), item.get("lane", "core"), item.get("priority", 0), item.get("required_capabilities", []), item.get("acceptance_criteria", []), [work_ids[dep] for dep in deps], item.get("max_attempts", 3), bool(item.get("side_effecting", 0)))
            work_ids[item.get("work_id", created["work_id"])] = created["work_id"]
            remaining.remove(item)
            progress = True
        if not progress:
            raise ValidationError("archive contains unresolved or cyclic work dependencies")
    return imported
