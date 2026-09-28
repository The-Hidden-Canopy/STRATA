"""STRATA spatial-temporal metadata store.

The legacy execution tables remain available through :class:`bundle.store.Database`.
This subclass adds the renderer-neutral historical model required by the STRATA
spec while preserving the existing local agent workflow.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from bundle.store import Database, NotFoundError, ValidationError, dumps, loads

from .ids import new_id
from .temporal import HistoricalInterval, contains


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(value: Any, default: Any = None) -> Any:
    if value is None:
        return {} if default is None else default
    if isinstance(value, str):
        return loads(value, {} if default is None else default)
    return value


def _row(row: Any) -> dict[str, Any]:
    result = dict(row)
    for key in list(result):
        if key.endswith("_json"):
            result[key[:-5]] = _json(result.pop(key))
    return result


STRATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS strata_entity (
    entity_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_entity_alias (
    alias_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    alias TEXT NOT NULL,
    valid_time_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS strata_entity_relation (
    relation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    subject_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    relation_type TEXT NOT NULL,
    object_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    valid_time_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL,
    provenance_id TEXT
);
CREATE TABLE IF NOT EXISTS strata_state (
    state_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    valid_time_json TEXT NOT NULL,
    transaction_time_json TEXT NOT NULL,
    geometry_id TEXT,
    properties_json TEXT NOT NULL DEFAULT '{}',
    uncertainty_json TEXT NOT NULL DEFAULT '{}',
    geometry_class TEXT NOT NULL DEFAULT 'inferred',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_event (
    event_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    entity_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    event_type TEXT NOT NULL,
    occurred_json TEXT NOT NULL,
    effects_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_source (
    source_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    title TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    uri TEXT NOT NULL DEFAULT '',
    content_hash TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_source_file (
    source_file_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES strata_source(source_id),
    blob_hash TEXT NOT NULL,
    size INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    original_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_source_region (
    region_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES strata_source(source_id),
    page INTEGER,
    region_json TEXT NOT NULL DEFAULT '{}',
    label TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS strata_observation (
    observation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    source_id TEXT NOT NULL REFERENCES strata_source(source_id),
    region_id TEXT,
    entity_id TEXT,
    observed_json TEXT NOT NULL,
    extraction_json TEXT NOT NULL DEFAULT '{}',
    review_state TEXT NOT NULL DEFAULT 'unreviewed',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_assertion (
    assertion_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    entity_id TEXT NOT NULL REFERENCES strata_entity(entity_id),
    property_path TEXT NOT NULL,
    value_json TEXT NOT NULL,
    valid_time_json TEXT NOT NULL,
    uncertainty_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_assertion_support (
    assertion_id TEXT NOT NULL REFERENCES strata_assertion(assertion_id),
    observation_id TEXT NOT NULL REFERENCES strata_observation(observation_id),
    PRIMARY KEY(assertion_id, observation_id)
);
CREATE TABLE IF NOT EXISTS strata_assertion_conflict (
    conflict_id TEXT PRIMARY KEY,
    assertion_id TEXT NOT NULL REFERENCES strata_assertion(assertion_id),
    conflicting_assertion_id TEXT NOT NULL REFERENCES strata_assertion(assertion_id),
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    CHECK(assertion_id <> conflicting_assertion_id)
);
CREATE TABLE IF NOT EXISTS strata_branch (
    branch_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    name TEXT NOT NULL,
    parent_branch_id TEXT REFERENCES strata_branch(branch_id),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(project_id, name)
);
CREATE TABLE IF NOT EXISTS strata_branch_assertion (
    branch_id TEXT NOT NULL REFERENCES strata_branch(branch_id),
    assertion_id TEXT NOT NULL REFERENCES strata_assertion(assertion_id),
    decision TEXT NOT NULL CHECK(decision IN ('accepted','rejected','unresolved')),
    PRIMARY KEY(branch_id, assertion_id)
);
CREATE TABLE IF NOT EXISTS strata_decision (
    decision_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    branch_id TEXT NOT NULL REFERENCES strata_branch(branch_id),
    entity_id TEXT REFERENCES strata_entity(entity_id),
    assertion_id TEXT REFERENCES strata_assertion(assertion_id),
    action TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_geometry (
    geometry_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    kind TEXT NOT NULL,
    content_hash TEXT,
    geometry_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_material (
    material_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    name TEXT NOT NULL,
    properties_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_spatial_anchor (
    anchor_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    entity_id TEXT REFERENCES strata_entity(entity_id),
    crs_json TEXT NOT NULL,
    coordinates_json TEXT NOT NULL,
    local_coordinates_json TEXT NOT NULL DEFAULT '{}',
    uncertainty_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_provenance (
    provenance_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    inputs_json TEXT NOT NULL DEFAULT '[]',
    operation TEXT NOT NULL,
    tool TEXT NOT NULL,
    tool_version TEXT NOT NULL DEFAULT '',
    parameters_hash TEXT NOT NULL DEFAULT '',
    ai_model_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    output_hash TEXT
);
CREATE TABLE IF NOT EXISTS strata_import_job (
    import_job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    source_id TEXT,
    status TEXT NOT NULL,
    input_hash TEXT,
    checkpoint_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_export_job (
    export_job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    format TEXT NOT NULL,
    output_uri TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_tag (
    tag_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    entity_id TEXT REFERENCES strata_entity(entity_id),
    label TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_timeline_marker (
    marker_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    label TEXT NOT NULL,
    time_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strata_user_note (
    note_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    entity_id TEXT,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_strata_entity_project ON strata_entity(project_id);
CREATE INDEX IF NOT EXISTS idx_strata_state_entity ON strata_state(entity_id);
CREATE INDEX IF NOT EXISTS idx_strata_source_project ON strata_source(project_id);
CREATE INDEX IF NOT EXISTS idx_strata_assertion_entity ON strata_assertion(entity_id);
CREATE INDEX IF NOT EXISTS idx_strata_event_entity ON strata_event(entity_id);
CREATE INDEX IF NOT EXISTS idx_strata_provenance_project ON strata_provenance(project_id);
"""


class StrataDatabase(Database):
    """SQLite store for temporal evidence and compiled world state."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path):
        super().__init__(path)
        self.conn.executescript(STRATA_SCHEMA)
        self.conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        self.conn.commit()

    def ensure_project(self, project_id: str, title: str, description: str = "") -> dict[str, Any]:
        now = _now()
        with self._tx(True) as conn:
            row = conn.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
            if row is None:
                conn.execute("INSERT INTO projects(project_id,name,description,created_at,updated_at) VALUES (?,?,?,?,?)", (project_id, title, description, now, now))
            return dict(conn.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone())

    def _require_entity(self, entity_id: str) -> Any:
        row = self.conn.execute("SELECT * FROM strata_entity WHERE entity_id=?", (entity_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"entity not found: {entity_id}")
        return row

    def create_entity(self, project_id: str, entity_type: str, canonical_name: str, entity_id: str | None = None) -> dict[str, Any]:
        if not canonical_name.strip():
            raise ValidationError("entity name is required")
        entity_id, now = entity_id or new_id("ent"), _now()
        with self._tx(True) as conn:
            self._require_project(conn, project_id)
            conn.execute("INSERT INTO strata_entity VALUES (?,?,?,?,?,?)", (entity_id, project_id, entity_type, canonical_name.strip(), now, now))
            row = conn.execute("SELECT * FROM strata_entity WHERE entity_id=?", (entity_id,)).fetchone()
        return _row(row)

    def get_entity(self, entity_id: str) -> dict[str, Any]:
        return _row(self._require_entity(entity_id))

    def list_entities(self, project_id: str, entity_type: str | None = None) -> list[dict[str, Any]]:
        if entity_type:
            rows = self.conn.execute("SELECT * FROM strata_entity WHERE project_id=? AND entity_type=? ORDER BY canonical_name, entity_id", (project_id, entity_type))
        else:
            rows = self.conn.execute("SELECT * FROM strata_entity WHERE project_id=? ORDER BY canonical_name, entity_id", (project_id,))
        return [_row(row) for row in rows]

    def add_alias(self, entity_id: str, alias: str, valid_time: dict[str, Any] | None = None) -> dict[str, Any]:
        self._require_entity(entity_id)
        alias_id = new_id("alias")
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_entity_alias VALUES (?,?,?,?)", (alias_id, entity_id, alias, dumps(valid_time or {})))
        return {"alias_id": alias_id, "entity_id": entity_id, "alias": alias, "valid_time": valid_time or {}}

    def add_relation(self, project_id: str, subject_id: str, relation_type: str, object_id: str, valid_time: dict[str, Any] | None = None, confidence: float | None = None, provenance_id: str | None = None) -> dict[str, Any]:
        self._require_entity(subject_id)
        self._require_entity(object_id)
        relation_id = new_id("rel")
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_entity_relation VALUES (?,?,?,?,?,?,?)", (relation_id, project_id, subject_id, relation_type, object_id, dumps(valid_time or {}), confidence, provenance_id))
        return {"relation_id": relation_id, "subject_id": subject_id, "relation_type": relation_type, "object_id": object_id, "valid_time": valid_time or {}, "confidence": confidence}

    def list_relations(self, project_id: str) -> list[dict[str, Any]]:
        return [_row(row) for row in self.conn.execute("SELECT * FROM strata_entity_relation WHERE project_id=? ORDER BY relation_id", (project_id,))]

    def add_state(self, entity_id: str, valid_time: dict[str, Any], properties: dict[str, Any] | None = None, geometry_id: str | None = None, uncertainty: dict[str, Any] | None = None, geometry_class: str = "inferred") -> dict[str, Any]:
        entity = self._require_entity(entity_id)
        state_id, now = new_id("state"), _now()
        transaction_time = {"recorded_at": now}
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_state VALUES (?,?,?,?,?,?,?,?,?)", (state_id, entity_id, dumps(valid_time), dumps(transaction_time), geometry_id, dumps(properties or {}), dumps(uncertainty or {}), geometry_class, now))
        return {"state_id": state_id, "entity_id": entity["entity_id"], "valid_time": valid_time, "transaction_time": transaction_time, "geometry_id": geometry_id, "properties": properties or {}, "uncertainty": uncertainty or {}, "geometry_class": geometry_class, "created_at": now}

    def list_states(self, entity_id: str | None = None, project_id: str | None = None) -> list[dict[str, Any]]:
        if entity_id:
            rows = self.conn.execute("SELECT s.* FROM strata_state s WHERE s.entity_id=? ORDER BY s.created_at, s.state_id", (entity_id,))
        elif project_id:
            rows = self.conn.execute("SELECT s.* FROM strata_state s JOIN strata_entity e ON e.entity_id=s.entity_id WHERE e.project_id=? ORDER BY s.created_at, s.state_id", (project_id,))
        else:
            rows = self.conn.execute("SELECT * FROM strata_state ORDER BY created_at, state_id")
        return [_row(row) for row in rows]

    def states_at(self, project_id: str, when: str, branch_id: str | None = None) -> list[dict[str, Any]]:
        states = [state for state in self.list_states(project_id=project_id) if contains(state["valid_time"], when)]
        if branch_id:
            accepted = {item["assertion_id"] for item in self.list_branch_assertions(branch_id, "accepted")}
            if accepted:
                for state in states:
                    state["accepted_assertions"] = sorted(accepted)
        return states

    def add_event(self, project_id: str, entity_id: str, event_type: str, occurred: dict[str, Any], effects: list[dict[str, Any]] | None = None, evidence: list[str] | None = None) -> dict[str, Any]:
        self._require_entity(entity_id)
        event_id, now = new_id("event"), _now()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_event VALUES (?,?,?,?,?,?,?)", (event_id, project_id, entity_id, event_type, dumps(occurred), dumps(effects or []), dumps(evidence or []), now))
        return {"event_id": event_id, "project_id": project_id, "entity_id": entity_id, "event_type": event_type, "occurred": occurred, "effects": effects or [], "evidence": evidence or [], "created_at": now}

    def list_historical_events(self, project_id: str, entity_id: str | None = None) -> list[dict[str, Any]]:
        if entity_id:
            rows = self.conn.execute("SELECT * FROM strata_event WHERE project_id=? AND entity_id=? ORDER BY created_at, event_id", (project_id, entity_id))
        else:
            rows = self.conn.execute("SELECT * FROM strata_event WHERE project_id=? ORDER BY created_at, event_id", (project_id,))
        return [_row(row) for row in rows]

    def add_source(self, project_id: str, title: str, source_kind: str, uri: str = "", content_hash: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        source_id, now = new_id("source"), _now()
        with self._tx(True) as conn:
            self._require_project(conn, project_id)
            conn.execute("INSERT INTO strata_source VALUES (?,?,?,?,?,?,?,?)", (source_id, project_id, title, source_kind, uri, content_hash, dumps(metadata or {}), now))
        return {"source_id": source_id, "project_id": project_id, "title": title, "source_kind": source_kind, "uri": uri, "content_hash": content_hash, "metadata": metadata or {}, "created_at": now}

    def add_source_region(self, source_id: str, page: int | None = None, region: dict[str, Any] | None = None, label: str = "") -> dict[str, Any]:
        region_id = new_id("region")
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_source_region VALUES (?,?,?,?,?)", (region_id, source_id, page, dumps(region or {}), label))
        return {"region_id": region_id, "source_id": source_id, "page": page, "region": region or {}, "label": label}

    def attach_source_file(self, source_id: str, blob_hash: str, size: int, media_type: str, original_name: str) -> dict[str, Any]:
        source_file_id = new_id("file")
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_source_file VALUES (?,?,?,?,?,?,?)", (source_file_id, source_id, blob_hash, size, media_type, original_name, _now()))
        return {"source_file_id": source_file_id, "source_id": source_id, "blob_hash": blob_hash, "size": size, "media_type": media_type, "original_name": original_name}

    def list_sources(self, project_id: str) -> list[dict[str, Any]]:
        return [_row(row) for row in self.conn.execute("SELECT * FROM strata_source WHERE project_id=? ORDER BY created_at, source_id", (project_id,))]

    def add_observation(self, project_id: str, source_id: str, observed: dict[str, Any], entity_id: str | None = None, region_id: str | None = None, extraction: dict[str, Any] | None = None, review_state: str = "unreviewed") -> dict[str, Any]:
        observation_id, now = new_id("obs"), _now()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_observation VALUES (?,?,?,?,?,?,?,?,?)", (observation_id, project_id, source_id, region_id, entity_id, dumps(observed), dumps(extraction or {}), review_state, now))
        return {"observation_id": observation_id, "project_id": project_id, "source_id": source_id, "region_id": region_id, "entity_id": entity_id, "observed": observed, "extraction": extraction or {}, "review_state": review_state, "created_at": now}

    def list_observations(self, project_id: str, entity_id: str | None = None) -> list[dict[str, Any]]:
        if entity_id:
            rows = self.conn.execute("SELECT * FROM strata_observation WHERE project_id=? AND entity_id=? ORDER BY created_at, observation_id", (project_id, entity_id))
        else:
            rows = self.conn.execute("SELECT * FROM strata_observation WHERE project_id=? ORDER BY created_at, observation_id", (project_id,))
        return [_row(row) for row in rows]

    def add_assertion(self, project_id: str, entity_id: str, property_path: str, value: Any, valid_time: dict[str, Any], uncertainty: dict[str, Any] | None = None, status: str = "proposed", observation_ids: Iterable[str] = ()) -> dict[str, Any]:
        assertion_id, now = new_id("assert"), _now()
        with self._tx(True) as conn:
            self._require_entity(entity_id)
            conn.execute("INSERT INTO strata_assertion VALUES (?,?,?,?,?,?,?,?,?)", (assertion_id, project_id, entity_id, property_path, dumps(value), dumps(valid_time), dumps(uncertainty or {}), status, now))
            for observation_id in observation_ids:
                conn.execute("INSERT INTO strata_assertion_support VALUES (?,?)", (assertion_id, observation_id))
        return {"assertion_id": assertion_id, "project_id": project_id, "entity_id": entity_id, "property_path": property_path, "value": value, "valid_time": valid_time, "uncertainty": uncertainty or {}, "status": status, "created_at": now}

    def list_assertions(self, project_id: str, entity_id: str | None = None) -> list[dict[str, Any]]:
        if entity_id:
            rows = self.conn.execute("SELECT * FROM strata_assertion WHERE project_id=? AND entity_id=? ORDER BY created_at, assertion_id", (project_id, entity_id))
        else:
            rows = self.conn.execute("SELECT * FROM strata_assertion WHERE project_id=? ORDER BY created_at, assertion_id", (project_id,))
        return [_row(row) for row in rows]

    def assertions_at(self, project_id: str, when: str, branch_id: str) -> list[dict[str, Any]]:
        accepted = {item["assertion_id"] for item in self.list_branch_assertions(branch_id, "accepted")}
        return [item for item in self.list_assertions(project_id) if item["assertion_id"] in accepted and contains(item["valid_time"], when)]

    def add_conflict(self, assertion_id: str, conflicting_assertion_id: str, reason: str = "") -> dict[str, Any]:
        conflict_id = new_id("conflict")
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_assertion_conflict VALUES (?,?,?,?,?)", (conflict_id, assertion_id, conflicting_assertion_id, reason, _now()))
        return {"conflict_id": conflict_id, "assertion_id": assertion_id, "conflicting_assertion_id": conflicting_assertion_id, "reason": reason}

    def create_branch(self, project_id: str, name: str, parent_branch_id: str | None = None, description: str = "") -> dict[str, Any]:
        branch_id, now = new_id("branch"), _now()
        with self._tx(True) as conn:
            self._require_project(conn, project_id)
            if parent_branch_id and conn.execute("SELECT 1 FROM strata_branch WHERE branch_id=? AND project_id=?", (parent_branch_id, project_id)).fetchone() is None:
                raise NotFoundError(f"parent branch not found: {parent_branch_id}")
            conn.execute("INSERT INTO strata_branch VALUES (?,?,?,?,?,?)", (branch_id, project_id, name, parent_branch_id, description, now))
        return {"branch_id": branch_id, "project_id": project_id, "name": name, "parent_branch_id": parent_branch_id, "description": description, "created_at": now}

    def list_branches(self, project_id: str) -> list[dict[str, Any]]:
        return [_row(row) for row in self.conn.execute("SELECT * FROM strata_branch WHERE project_id=? ORDER BY created_at, name", (project_id,))]

    def branch_by_name(self, project_id: str, name: str) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM strata_branch WHERE project_id=? AND name=?", (project_id, name)).fetchone()
        if row is None:
            raise NotFoundError(f"branch not found: {name}")
        return _row(row)

    def set_branch_assertion(self, branch_id: str, assertion_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"accepted", "rejected", "unresolved"}:
            raise ValidationError("branch assertion decision must be accepted, rejected, or unresolved")
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_branch_assertion VALUES (?,?,?) ON CONFLICT(branch_id, assertion_id) DO UPDATE SET decision=excluded.decision", (branch_id, assertion_id, decision))
        return {"branch_id": branch_id, "assertion_id": assertion_id, "decision": decision}

    def list_branch_assertions(self, branch_id: str, decision: str | None = None) -> list[dict[str, Any]]:
        if decision:
            rows = self.conn.execute("SELECT * FROM strata_branch_assertion WHERE branch_id=? AND decision=? ORDER BY assertion_id", (branch_id, decision))
        else:
            rows = self.conn.execute("SELECT * FROM strata_branch_assertion WHERE branch_id=? ORDER BY assertion_id", (branch_id,))
        return [_row(row) for row in rows]

    def merge_branch(self, target_branch_id: str, source_branch_id: str) -> dict[str, Any]:
        """Merge only non-conflicting decisions; never use last-write-wins."""
        target = {item["assertion_id"]: item["decision"] for item in self.list_branch_assertions(target_branch_id)}
        source = {item["assertion_id"]: item["decision"] for item in self.list_branch_assertions(source_branch_id)}
        conflicts = sorted(assertion_id for assertion_id in set(target) & set(source) if target[assertion_id] != source[assertion_id])
        applied = []
        if conflicts:
            return {"merged": False, "applied": applied, "conflicts": conflicts}
        with self._tx(True) as conn:
            for assertion_id, decision in source.items():
                if assertion_id not in target:
                    conn.execute("INSERT INTO strata_branch_assertion VALUES (?,?,?)", (target_branch_id, assertion_id, decision))
                    applied.append(assertion_id)
        return {"merged": True, "applied": sorted(applied), "conflicts": []}

    def add_decision(self, project_id: str, branch_id: str, entity_id: str | None, assertion_id: str | None, action: str, rationale: str = "") -> dict[str, Any]:
        decision_id, now = new_id("decision"), _now()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_decision VALUES (?,?,?,?,?,?,?,?)", (decision_id, project_id, branch_id, entity_id, assertion_id, action, rationale, now))
        return {"decision_id": decision_id, "project_id": project_id, "branch_id": branch_id, "entity_id": entity_id, "assertion_id": assertion_id, "action": action, "rationale": rationale, "created_at": now}

    def add_geometry(self, project_id: str, kind: str, geometry: dict[str, Any], content_hash: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        geometry_id, now = new_id("geom"), _now()
        if content_hash is None:
            content_hash = hashlib.sha256(json.dumps(geometry, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_geometry VALUES (?,?,?,?,?,?,?)", (geometry_id, project_id, kind, content_hash, dumps(geometry), dumps(metadata or {}), now))
        return {"geometry_id": geometry_id, "project_id": project_id, "kind": kind, "content_hash": content_hash, "geometry": geometry, "metadata": metadata or {}, "created_at": now}

    def list_geometries(self, project_id: str) -> list[dict[str, Any]]:
        return [_row(row) for row in self.conn.execute("SELECT * FROM strata_geometry WHERE project_id=? ORDER BY created_at, geometry_id", (project_id,))]

    def add_material(self, project_id: str, name: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
        material_id, now = new_id("mat"), _now()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_material VALUES (?,?,?,?,?)", (material_id, project_id, name, dumps(properties or {}), now))
        return {"material_id": material_id, "project_id": project_id, "name": name, "properties": properties or {}, "created_at": now}

    def add_tag(self, project_id: str, label: str, entity_id: str | None = None) -> dict[str, Any]:
        tag_id, now = new_id("tag"), _now()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_tag VALUES (?,?,?,?,?)", (tag_id, project_id, entity_id, label, now))
        return {"tag_id": tag_id, "project_id": project_id, "entity_id": entity_id, "label": label, "created_at": now}

    def add_timeline_marker(self, project_id: str, label: str, time_value: dict[str, Any]) -> dict[str, Any]:
        marker_id, now = new_id("marker"), _now()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_timeline_marker VALUES (?,?,?,?,?)", (marker_id, project_id, label, dumps(time_value), now))
        return {"marker_id": marker_id, "project_id": project_id, "label": label, "time": time_value, "created_at": now}

    def add_user_note(self, project_id: str, body: str, entity_id: str | None = None) -> dict[str, Any]:
        note_id, now = new_id("note"), _now()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_user_note VALUES (?,?,?,?,?,?)", (note_id, project_id, entity_id, body, now, now))
        return {"note_id": note_id, "project_id": project_id, "entity_id": entity_id, "body": body, "created_at": now, "updated_at": now}

    def add_spatial_anchor(self, project_id: str, crs: dict[str, Any], coordinates: dict[str, float], entity_id: str | None = None, local_coordinates: dict[str, float] | None = None, uncertainty: dict[str, Any] | None = None) -> dict[str, Any]:
        anchor_id, now = new_id("anchor"), _now()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_spatial_anchor VALUES (?,?,?,?,?,?,?,?)", (anchor_id, project_id, entity_id, dumps(crs), dumps(coordinates), dumps(local_coordinates or {}), dumps(uncertainty or {}), now))
        return {"anchor_id": anchor_id, "project_id": project_id, "entity_id": entity_id, "crs": crs, "coordinates": coordinates, "local_coordinates": local_coordinates or {}, "uncertainty": uncertainty or {}, "created_at": now}

    def add_provenance(self, project_id: str, inputs: list[str], operation: str, tool: str = "strata", tool_version: str = "0.1.0", parameters: Any = None, ai_model: dict[str, Any] | None = None, output_hash: str | None = None) -> dict[str, Any]:
        provenance_id, now = new_id("prov"), _now()
        parameters_hash = hashlib.sha256(json.dumps(parameters or {}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_provenance VALUES (?,?,?,?,?,?,?,?,?,?)", (provenance_id, project_id, dumps(inputs), operation, tool, tool_version, parameters_hash, dumps(ai_model or {}), now, output_hash))
        return {"provenance_id": provenance_id, "project_id": project_id, "inputs": inputs, "operation": operation, "tool": tool, "tool_version": tool_version, "parameters_hash": parameters_hash, "ai_model": ai_model or {}, "created_at": now, "output_hash": output_hash}

    def list_provenance(self, project_id: str) -> list[dict[str, Any]]:
        return [_row(row) for row in self.conn.execute("SELECT * FROM strata_provenance WHERE project_id=? ORDER BY created_at, provenance_id", (project_id,))]

    def add_import_job(self, project_id: str, status: str, source_id: str | None = None, input_hash: str | None = None, checkpoint: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
        job_id, now = new_id("import") , _now()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO strata_import_job VALUES (?,?,?,?,?,?,?,?,?)", (job_id, project_id, source_id, status, input_hash, dumps(checkpoint or {}), error, now, now))
        return {"import_job_id": job_id, "project_id": project_id, "source_id": source_id, "status": status, "input_hash": input_hash, "checkpoint": checkpoint or {}, "error": error, "created_at": now, "updated_at": now}

    def counts(self, project_id: str) -> dict[str, int]:
        tables = {"entities": "strata_entity", "states": "strata_state", "events": "strata_event", "sources": "strata_source", "observations": "strata_observation", "assertions": "strata_assertion", "branches": "strata_branch", "geometries": "strata_geometry", "provenance": "strata_provenance"}
        result: dict[str, int] = {}
        for label, table in tables.items():
            where = " WHERE project_id=?" if table not in {"strata_state"} else " WHERE entity_id IN (SELECT entity_id FROM strata_entity WHERE project_id=?)"
            result[label] = int(self.conn.execute(f"SELECT COUNT(*) FROM {table}{where}", (project_id,)).fetchone()[0])
        return result
