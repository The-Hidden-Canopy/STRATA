"""Project integrity and recovery diagnostics."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .project import StrataProject
from .temporal import HistoricalInterval


def _check(report: dict[str, Any], name: str, ok: bool, detail: str) -> None:
    report["checks"].append({"name": name, "ok": ok, "detail": detail})
    if not ok:
        report["errors"].append({"name": name, "detail": detail})


def verify_project(root: str | Path) -> dict[str, Any]:
    report: dict[str, Any] = {"ok": True, "project": str(root), "checks": [], "errors": [], "warnings": []}
    try:
        project = StrataProject.open(root)
    except Exception as exc:
        _check(report, "open", False, str(exc))
        report["ok"] = False
        return report
    try:
        manifest = project.manifest
        _check(report, "manifest.format", manifest.get("format", {}).get("major") == 1, "format major must be 1")
        for name in ("blobs", "previews", "exports", "cache", "logs"):
            _check(report, f"directory.{name}", (project.root / name).is_dir(), f"{name} directory exists")
        integrity = project.db.conn.execute("PRAGMA integrity_check").fetchone()[0]
        _check(report, "sqlite.integrity", integrity == "ok", str(integrity))
        foreign = project.db.conn.execute("PRAGMA foreign_key_check").fetchall()
        _check(report, "sqlite.foreign_keys", not foreign, f"{len(foreign)} foreign-key violations")
        _check(report, "schema.version", project.db.conn.execute("PRAGMA user_version").fetchone()[0] >= 1, "schema version is present")
        for state in project.db.list_states(project_id=project.project_id):
            try:
                HistoricalInterval.from_dict(state["valid_time"])
            except Exception as exc:
                _check(report, f"state.{state['state_id']}.time", False, str(exc))
        branches = project.db.list_branches(project.project_id)
        branch_ids = {branch["branch_id"] for branch in branches}
        for branch in branches:
            parent = branch.get("parent_branch_id")
            _check(report, f"branch.{branch['name']}.parent", parent is None or parent in branch_ids, "parent branch reference")
        for source in project.db.list_sources(project.project_id):
            if source.get("content_hash"):
                result = project.blobs.verify(source["content_hash"])
                _check(report, f"blob.{source['content_hash']}", bool(result["ok"]), str(result))
        counts = project.db.counts(project.project_id)
        report["counts"] = counts
    finally:
        project.close()
    report["ok"] = not report["errors"]
    return report


def doctor_project(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    report: dict[str, Any] = {"ok": True, "project": str(root), "checks": [], "errors": [], "warnings": []}
    for name in ("blobs", "previews", "exports", "cache", "logs"):
        path = root / name
        writable = path.is_dir() and os.access(path, os.W_OK)
        _check(report, f"writable.{name}", writable, str(path))
    verified = verify_project(root)
    report["checks"].extend(verified["checks"])
    report["errors"].extend(verified["errors"])
    report["warnings"].extend(verified["warnings"])
    report["counts"] = verified.get("counts", {})
    report["ok"] = not report["errors"]
    return report

