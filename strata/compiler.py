"""Deterministic renderer-neutral scene compilation and glTF export."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .project import StrataProject


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


class SceneCompiler:
    def __init__(self, project: StrataProject):
        self.project = project

    def build_scene(self, when: str, branch: str = "main", seed: int = 0) -> dict[str, Any]:
        db = self.project.db
        branch_row = db.branch_by_name(self.project.project_id, branch)
        entities = {entity["entity_id"]: entity for entity in db.list_entities(self.project.project_id)}
        geometries = {geometry["geometry_id"]: geometry for geometry in db.list_geometries(self.project.project_id)}
        states = db.states_at(self.project.project_id, when, branch_row["branch_id"])
        compiled: list[dict[str, Any]] = []
        for state in states:
            entity = entities.get(state["entity_id"])
            if entity is None:
                continue
            geometry = geometries.get(state.get("geometry_id")) if state.get("geometry_id") else None
            compiled.append({"entity": entity, "state": state, "geometry": geometry})
        compiled.sort(key=lambda item: (item["entity"]["entity_type"], item["entity"]["canonical_name"], item["entity"]["entity_id"], item["state"]["state_id"]))
        accepted = db.list_branch_assertions(branch_row["branch_id"], "accepted")
        assertions = {item["assertion_id"]: item for item in db.list_assertions(self.project.project_id)}
        applied_assertions = [assertions[item["assertion_id"]] for item in accepted if item["assertion_id"] in assertions]
        payload = {
            "format": {"major": 1, "minor": 0},
            "project_id": self.project.project_id,
            "project_title": self.project.manifest["title"],
            "branch": branch,
            "time": when,
            "seed": seed,
            "entities": compiled,
            "assertions": applied_assertions,
            "compiler": {"name": "strata-python", "version": "0.1.0"},
        }
        payload["root_hash"] = hashlib.sha256(_canonical(payload)).hexdigest()
        return payload

    def write(self, scene: dict[str, Any], output: str | Path) -> Path:
        target = Path(output)
        target.mkdir(parents=True, exist_ok=True)
        (target / "scene.json").write_text(json.dumps(scene, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        citations = {"project_id": scene["project_id"], "branch": scene["branch"], "time": scene["time"], "sources": self.project.db.list_sources(self.project.project_id)}
        (target / "citations.json").write_text(json.dumps(citations, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        provenance = {"project_id": scene["project_id"], "root_hash": scene["root_hash"], "records": self.project.db.list_provenance(self.project.project_id)}
        (target / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.write_gltf(scene, target / "scene.gltf")
        return target

    @staticmethod
    def write_gltf(scene: dict[str, Any], output: str | Path) -> Path:
        nodes = []
        for item in scene["entities"]:
            entity = item["entity"]
            state = item["state"]
            nodes.append({"name": entity["canonical_name"], "extras": {"strata_entity_id": entity["entity_id"], "strata_state_id": state["state_id"], "geometry_class": state["geometry_class"]}})
        gltf = {"asset": {"version": "2.0", "generator": "STRATA"}, "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "extras": {"strata_project_id": scene["project_id"], "strata_branch": scene["branch"], "strata_time": scene["time"], "strata_root_hash": scene["root_hash"]}}
        target = Path(output)
        target.write_text(json.dumps(gltf, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    def export_vanta(self, scene: dict[str, Any], output: str | Path) -> Path:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"format": "strata-vanta-1", "scene": scene, "renderer_truth": "STRATA"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

