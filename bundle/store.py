"""SQLite persistence and transactional domain operations for Bundle."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def dumps(value: Any) -> str:
    return json.dumps(value if value is not None else [], separators=(",", ":"), sort_keys=True)


def loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return [] if default is None else default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return [] if default is None else default


class BundleError(Exception):
    """Base error for expected Bundle domain failures."""


class NotFoundError(BundleError):
    pass


class ConflictError(BundleError):
    pass


class ValidationError(BundleError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    objective TEXT NOT NULL DEFAULT '',
    success_definition TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT
);
CREATE TABLE IF NOT EXISTS phases (
    phase_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    revision INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    objective TEXT NOT NULL DEFAULT '',
    ordinal INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    UNIQUE(project_id, ordinal)
);
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    capabilities_json TEXT NOT NULL DEFAULT '[]',
    primary_lane TEXT NOT NULL DEFAULT 'core',
    secondary_lanes_json TEXT NOT NULL DEFAULT '[]',
    emergency_lanes_json TEXT NOT NULL DEFAULT '[]',
    max_active_claims INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_memberships (
    membership_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    primary_role TEXT NOT NULL DEFAULT 'worker',
    status TEXT NOT NULL DEFAULT 'active',
    joined_at TEXT NOT NULL,
    left_at TEXT,
    UNIQUE(project_id, agent_id)
);
CREATE TABLE IF NOT EXISTS runtimes (
    runtime_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    healthy INTEGER NOT NULL DEFAULT 1,
    identity TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS work_items (
    work_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    phase_id TEXT REFERENCES phases(phase_id),
    revision INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL,
    objective TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    priority INTEGER NOT NULL DEFAULT 0,
    lane TEXT NOT NULL DEFAULT 'core',
    role_hint TEXT,
    required_capabilities_json TEXT NOT NULL DEFAULT '[]',
    preferred_agent_ids_json TEXT NOT NULL DEFAULT '[]',
    excluded_agent_ids_json TEXT NOT NULL DEFAULT '[]',
    expected_outputs_json TEXT NOT NULL DEFAULT '[]',
    acceptance_criteria_json TEXT NOT NULL DEFAULT '[]',
    owner_agent_id TEXT,
    active_claim_id TEXT,
    attempt INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    side_effecting INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS work_dependencies (
    work_id TEXT NOT NULL REFERENCES work_items(work_id),
    depends_on_work_id TEXT NOT NULL REFERENCES work_items(work_id),
    hard INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(work_id, depends_on_work_id),
    CHECK(work_id <> depends_on_work_id)
);
CREATE TABLE IF NOT EXISTS work_claims (
    claim_id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES work_items(work_id),
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    agent_instance_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    execution_ref TEXT,
    side_effecting INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS heartbeats (
    heartbeat_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES work_claims(claim_id),
    agent_instance_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    state TEXT NOT NULL,
    current_action TEXT NOT NULL DEFAULT '',
    progress_hint TEXT NOT NULL DEFAULT '',
    blocker_hint TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    phase_id TEXT,
    work_id TEXT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    uri TEXT NOT NULL,
    content_hash TEXT,
    size INTEGER,
    mime_type TEXT,
    producer_agent_id TEXT,
    created_at TEXT NOT NULL,
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS blockers (
    blocker_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    work_id TEXT,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    requires_json TEXT NOT NULL DEFAULT '[]',
    created_by TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    kind TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attention_state (
    attention_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    source_ref TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plan_revisions (
    plan_revision_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    base_revision INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    proposed_by TEXT,
    proposed_at TEXT NOT NULL,
    committed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_work_project_status ON work_items(project_id, status);
CREATE INDEX IF NOT EXISTS idx_claim_expiry ON work_claims(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_events_project_created ON events(project_id, created_at);
"""


class Database:
    """Thread-safe SQLite store with explicit transaction boundaries."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    @contextmanager
    def _tx(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self.conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield self.conn
            except Exception:
                self.conn.rollback()
                raise
            else:
                self.conn.commit()

    @staticmethod
    def _json_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        for key in list(result):
            if key.endswith("_json"):
                result[key[:-5]] = loads(result.pop(key), {} if key.endswith("metadata_json") or key.endswith("config_json") else [])
        return result

    def _event(self, conn: sqlite3.Connection, project_id: str, kind: str, entity_type: str, entity_id: str, payload: dict[str, Any] | None = None) -> None:
        conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id("evt"), project_id, kind, entity_type, entity_id, dumps(payload or {}), utc_now()),
        )

    def _require_project(self, conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"project not found: {project_id}")
        return row

    def create_project(self, name: str, description: str = "", objective: str = "", success_definition: str = "") -> dict[str, Any]:
        if not name.strip():
            raise ValidationError("project name is required")
        project_id, now = new_id("prj"), utc_now()
        with self._tx(True) as conn:
            conn.execute(
                "INSERT INTO projects(project_id,name,description,objective,success_definition,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (project_id, name.strip(), description, objective, success_definition, now, now),
            )
            self._event(conn, project_id, "project.created", "project", project_id, {"name": name.strip()})
            row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        return self._json_row(row) or {}

    def get_project(self, project_id: str) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        result = self._json_row(row)
        if result is None:
            raise NotFoundError(f"project not found: {project_id}")
        return result

    def list_projects(self) -> list[dict[str, Any]]:
        return [self._json_row(row) or {} for row in self.conn.execute("SELECT * FROM projects ORDER BY created_at")]

    def create_phase(self, project_id: str, name: str, objective: str = "", ordinal: int | None = None) -> dict[str, Any]:
        phase_id, now = new_id("phs"), utc_now()
        with self._tx(True) as conn:
            self._require_project(conn, project_id)
            if ordinal is None:
                ordinal = conn.execute("SELECT COALESCE(MAX(ordinal), 0) + 1 FROM phases WHERE project_id = ?", (project_id,)).fetchone()[0]
            conn.execute(
                "INSERT INTO phases(phase_id,project_id,name,objective,ordinal,created_at,started_at) VALUES (?,?,?,?,?,?,?)",
                (phase_id, project_id, name.strip(), objective, ordinal, now, now),
            )
            self._event(conn, project_id, "phase.created", "phase", phase_id, {"name": name.strip()})
            row = conn.execute("SELECT * FROM phases WHERE phase_id = ?", (phase_id,)).fetchone()
        return self._json_row(row) or {}

    def create_agent(self, project_id: str, name: str, capabilities: list[str] | None = None, primary_lane: str = "core", secondary_lanes: list[str] | None = None, max_active_claims: int = 1, agent_id: str | None = None) -> dict[str, Any]:
        agent_id, now = agent_id or new_id("agt"), utc_now()
        with self._tx(True) as conn:
            self._require_project(conn, project_id)
            conn.execute(
                "INSERT INTO agents(agent_id,name,capabilities_json,primary_lane,secondary_lanes_json,max_active_claims,created_at) VALUES (?,?,?,?,?,?,?)",
                (agent_id, name.strip(), dumps(capabilities or []), primary_lane, dumps(secondary_lanes or []), max_active_claims, now),
            )
            conn.execute(
                "INSERT INTO project_memberships VALUES (?,?,?,?,?,?,?)",
                (new_id("mbr"), project_id, agent_id, "worker", "active", now, None),
            )
            self._event(conn, project_id, "agent.joined", "agent", agent_id, {"name": name.strip()})
            row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        return self._json_row(row) or {}

    def list_agents(self, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id:
            rows = self.conn.execute(
                "SELECT a.* FROM agents a JOIN project_memberships m ON m.agent_id=a.agent_id WHERE m.project_id=? AND m.status='active' ORDER BY a.name",
                (project_id,),
            )
        else:
            rows = self.conn.execute("SELECT * FROM agents ORDER BY name")
        return [self._json_row(row) or {} for row in rows]

    def add_runtime(self, kind: str, config: dict[str, Any] | None = None, identity: str | None = None) -> dict[str, Any]:
        runtime_id, now = new_id("rtm"), utc_now()
        with self._tx(True) as conn:
            conn.execute("INSERT INTO runtimes VALUES (?,?,?,?,?,?)", (runtime_id, kind, dumps(config or {}), 1, identity or kind, now))
            row = conn.execute("SELECT * FROM runtimes WHERE runtime_id = ?", (runtime_id,)).fetchone()
        return self._json_row(row) or {}

    def list_runtimes(self) -> list[dict[str, Any]]:
        return [self._json_row(row) or {} for row in self.conn.execute("SELECT * FROM runtimes ORDER BY created_at")]

    def _phase_is_active(self, conn: sqlite3.Connection, phase_id: str | None) -> bool:
        if phase_id is None:
            return True
        row = conn.execute("SELECT status FROM phases WHERE phase_id=?", (phase_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"phase not found: {phase_id}")
        return row[0] == "active"

    def _dependencies_complete(self, conn: sqlite3.Connection, work_id: str) -> bool:
        row = conn.execute(
            "SELECT COUNT(*) FROM work_dependencies d JOIN work_items w ON w.work_id=d.depends_on_work_id WHERE d.work_id=? AND d.hard=1 AND w.status <> 'complete'",
            (work_id,),
        ).fetchone()
        return row[0] == 0

    def create_work(self, project_id: str, title: str, objective: str = "", detail: str = "", phase_id: str | None = None, lane: str = "core", priority: int = 0, required_capabilities: list[str] | None = None, acceptance_criteria: list[str] | None = None, dependencies: list[str] | None = None, max_attempts: int = 3, side_effecting: bool = False) -> dict[str, Any]:
        work_id, now = new_id("wrk"), utc_now()
        dependencies = dependencies or []
        with self._tx(True) as conn:
            project = self._require_project(conn, project_id)
            if project["status"] != "active":
                raise ConflictError("project is not active")
            if phase_id and conn.execute("SELECT project_id FROM phases WHERE phase_id=?", (phase_id,)).fetchone()[0] != project_id:
                raise ValidationError("phase belongs to another project")
            for dep in dependencies:
                if conn.execute("SELECT 1 FROM work_items WHERE work_id=? AND project_id=?", (dep, project_id)).fetchone() is None:
                    raise NotFoundError(f"dependency work item not found: {dep}")
            status = "ready" if not dependencies and self._phase_is_active(conn, phase_id) else "draft"
            conn.execute(
                "INSERT INTO work_items(work_id,project_id,phase_id,title,objective,detail,status,priority,lane,required_capabilities_json,acceptance_criteria_json,max_attempts,side_effecting,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (work_id, project_id, phase_id, title.strip(), objective, detail, status, priority, lane, dumps(required_capabilities or []), dumps(acceptance_criteria or []), max_attempts, int(side_effecting), now, now),
            )
            for dep in dependencies:
                self._ensure_no_cycle(conn, work_id, dep)
                conn.execute("INSERT INTO work_dependencies VALUES (?,?,1)", (work_id, dep))
            self._event(conn, project_id, "work.created", "work", work_id, {"title": title.strip(), "status": status})
            row = conn.execute("SELECT * FROM work_items WHERE work_id = ?", (work_id,)).fetchone()
        return self._json_row(row) or {}

    def add_dependency(self, work_id: str, depends_on_work_id: str, hard: bool = True) -> None:
        """Add a graph edge while rejecting cycles atomically."""
        with self._tx(True) as conn:
            work = conn.execute("SELECT project_id FROM work_items WHERE work_id=?", (work_id,)).fetchone()
            dependency = conn.execute("SELECT project_id FROM work_items WHERE work_id=?", (depends_on_work_id,)).fetchone()
            if work is None or dependency is None:
                raise NotFoundError("both work items must exist")
            if work["project_id"] != dependency["project_id"]:
                raise ValidationError("dependencies must stay within one project")
            self._ensure_no_cycle(conn, work_id, depends_on_work_id)
            conn.execute("INSERT INTO work_dependencies VALUES (?,?,?)", (work_id, depends_on_work_id, int(hard)))
            conn.execute("UPDATE work_items SET status='draft',revision=revision+1,updated_at=? WHERE work_id=?", (utc_now(), work_id))
            self._event(conn, work["project_id"], "work.dependency_added", "work", work_id, {"depends_on": depends_on_work_id, "hard": hard})

    def _ensure_no_cycle(self, conn: sqlite3.Connection, work_id: str, depends_on: str) -> None:
        found = conn.execute(
            "WITH RECURSIVE reach(work_id) AS (SELECT depends_on_work_id FROM work_dependencies WHERE work_id=? UNION ALL SELECT d.depends_on_work_id FROM work_dependencies d JOIN reach r ON d.work_id=r.work_id) SELECT 1 FROM reach WHERE work_id=? LIMIT 1",
            (depends_on, work_id),
        ).fetchone()
        if found:
            raise ValidationError("dependency would introduce a cycle")

    def list_work(self, project_id: str, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.conn.execute("SELECT * FROM work_items WHERE project_id=? AND status=? ORDER BY priority DESC, created_at", (project_id, status))
        else:
            rows = self.conn.execute("SELECT * FROM work_items WHERE project_id=? ORDER BY priority DESC, created_at", (project_id,))
        return [self._json_row(row) or {} for row in rows]

    def get_work(self, work_id: str) -> dict[str, Any]:
        result = self._json_row(self.conn.execute("SELECT * FROM work_items WHERE work_id=?", (work_id,)).fetchone())
        if result is None:
            raise NotFoundError(f"work item not found: {work_id}")
        return result

    def recompute_ready(self, project_id: str) -> int:
        changed = 0
        with self._tx(True) as conn:
            project = self._require_project(conn, project_id)
            rows = conn.execute("SELECT work_id,status,phase_id FROM work_items WHERE project_id=?", (project_id,)).fetchall()
            for row in rows:
                if row["status"] not in {"draft", "claim_expired", "failed_retryable"}:
                    continue
                if project["status"] != "active" or not self._phase_is_active(conn, row["phase_id"]):
                    continue
                if self._dependencies_complete(conn, row["work_id"]):
                    conn.execute("UPDATE work_items SET status='ready', updated_at=? WHERE work_id=?", (utc_now(), row["work_id"]))
                    changed += 1
            if changed:
                self._event(conn, project_id, "work.ready_frontier.recomputed", "project", project_id, {"changed": changed})
        return changed

    def candidate_work(self, project_id: str, agent_id: str) -> list[dict[str, Any]]:
        self.recompute_ready(project_id)
        rows = self.conn.execute(
            "SELECT w.*, a.capabilities_json, a.primary_lane, a.secondary_lanes_json, a.emergency_lanes_json, a.active AS agent_active, m.status AS membership_status FROM work_items w JOIN agents a ON a.agent_id=? JOIN project_memberships m ON m.agent_id=a.agent_id AND m.project_id=w.project_id WHERE w.project_id=? AND w.status='ready'",
            (agent_id, project_id),
        )
        result = []
        capacity = self.conn.execute("SELECT max_active_claims FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
        active_count = self.conn.execute("SELECT COUNT(*) FROM work_claims WHERE agent_id=? AND status='active'", (agent_id,)).fetchone()[0]
        if capacity is None or active_count >= capacity[0]:
            return result
        for row in rows:
            item = self._json_row(row) or {}
            if not item["agent_active"] or item["membership_status"] != "active":
                continue
            caps = set(item.get("capabilities", []))
            if not set(item.get("required_capabilities", [])) <= caps:
                continue
            if agent_id in item.get("excluded_agent_ids", []):
                continue
            allowed_lanes = {item["primary_lane"], *item.get("secondary_lanes", [])}
            if item["lane"] not in allowed_lanes:
                continue
            result.append(item)
        return result

    def claim(self, work_id: str, agent_id: str, expected_revision: int, agent_instance_id: str = "default", ttl_seconds: int = 120) -> dict[str, Any]:
        if ttl_seconds < 5:
            raise ValidationError("claim TTL must be at least five seconds")
        now_dt = datetime.now(timezone.utc)
        now = now_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        expires = (now_dt + timedelta(seconds=ttl_seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with self._tx(True) as conn:
            work = conn.execute("SELECT * FROM work_items WHERE work_id=?", (work_id,)).fetchone()
            if work is None:
                raise NotFoundError(f"work item not found: {work_id}")
            if work["status"] != "ready":
                raise ConflictError(f"work is not ready: {work['status']}")
            if work["revision"] != expected_revision:
                raise ConflictError("work revision changed; refresh before claiming")
            member = conn.execute(
                "SELECT a.*,m.status AS membership_status FROM agents a JOIN project_memberships m ON m.agent_id=a.agent_id WHERE a.agent_id=? AND m.project_id=?",
                (agent_id, work["project_id"]),
            ).fetchone()
            if member is None or not member["active"] or member["membership_status"] != "active":
                raise ConflictError("agent is not an active project member")
            caps = set(loads(member["capabilities_json"]))
            if not set(loads(work["required_capabilities_json"])) <= caps:
                raise ConflictError("agent lacks required capabilities")
            allowed_lanes = {member["primary_lane"], *loads(member["secondary_lanes_json"]), *loads(member["emergency_lanes_json"])}
            if work["lane"] not in allowed_lanes:
                raise ConflictError("agent lane policy does not permit this work")
            if agent_id in loads(work["excluded_agent_ids_json"]):
                raise ConflictError("agent is excluded from this work")
            if not self._dependencies_complete(conn, work_id):
                raise ConflictError("dependencies are not complete")
            active_count = conn.execute("SELECT COUNT(*) FROM work_claims WHERE agent_id=? AND status='active'", (agent_id,)).fetchone()[0]
            if active_count >= member["max_active_claims"]:
                raise ConflictError("agent has reached active claim capacity")
            claim_id = new_id("clm")
            conn.execute(
                "INSERT INTO work_claims(claim_id,work_id,agent_id,agent_instance_id,issued_at,expires_at,heartbeat_at,execution_ref,side_effecting) VALUES (?,?,?,?,?,?,?,?,?)",
                (claim_id, work_id, agent_id, agent_instance_id, now, expires, now, None, work["side_effecting"]),
            )
            conn.execute("UPDATE work_items SET status='claimed',owner_agent_id=?,active_claim_id=?,attempt=attempt+1,revision=revision+1,updated_at=? WHERE work_id=? AND status='ready' AND revision=?", (agent_id, claim_id, now, work_id, expected_revision))
            if conn.execute("SELECT changes()").fetchone()[0] != 1:
                raise ConflictError("work was claimed concurrently")
            self._event(conn, work["project_id"], "work.claimed", "work", work_id, {"claim_id": claim_id, "agent_id": agent_id})
            result = conn.execute("SELECT * FROM work_claims WHERE claim_id=?", (claim_id,)).fetchone()
        return self._json_row(result) or {}

    def heartbeat(self, claim_id: str, state: str = "working", current_action: str = "", progress_hint: str = "", blocker_hint: str = "", ttl_seconds: int = 120) -> dict[str, Any]:
        now_dt = datetime.now(timezone.utc)
        now = now_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        expires = (now_dt + timedelta(seconds=ttl_seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with self._tx(True) as conn:
            claim = conn.execute("SELECT * FROM work_claims WHERE claim_id=?", (claim_id,)).fetchone()
            if claim is None:
                raise NotFoundError(f"claim not found: {claim_id}")
            if claim["status"] != "active":
                raise ConflictError("claim is no longer active")
            conn.execute("UPDATE work_claims SET heartbeat_at=?,expires_at=? WHERE claim_id=?", (now, expires, claim_id))
            conn.execute("INSERT INTO heartbeats VALUES (?,?,?,?,?,?,?,?)", (new_id("hb"), claim_id, claim["agent_instance_id"], now, state, current_action, progress_hint, blocker_hint))
            self._event(conn, self.conn.execute("SELECT project_id FROM work_items WHERE work_id=?", (claim["work_id"],)).fetchone()[0], "claim.heartbeat", "claim", claim_id, {"state": state})
            result = conn.execute("SELECT * FROM work_claims WHERE claim_id=?", (claim_id,)).fetchone()
        return self._json_row(result) or {}

    def checkin(self, claim_id: str, outcome: str, summary: str, artifacts: list[dict[str, Any]] | None = None, blockers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        valid = {"complete", "blocked", "needs_review", "retryable_failure", "final_failure", "released"}
        if outcome not in valid:
            raise ValidationError(f"invalid check-in outcome: {outcome}")
        with self._tx(True) as conn:
            claim = conn.execute("SELECT * FROM work_claims WHERE claim_id=?", (claim_id,)).fetchone()
            if claim is None:
                raise NotFoundError(f"claim not found: {claim_id}")
            if claim["status"] != "active":
                raise ConflictError("claim is no longer active")
            work = conn.execute("SELECT * FROM work_items WHERE work_id=?", (claim["work_id"],)).fetchone()
            project_id = work["project_id"]
            status = {"complete": "complete", "blocked": "blocked", "needs_review": "review", "retryable_failure": "failed_retryable", "final_failure": "failed_final", "released": "ready"}[outcome]
            claim_status = "released" if outcome == "released" else "completed"
            now = utc_now()
            conn.execute("UPDATE work_claims SET status=? WHERE claim_id=?", (claim_status, claim_id))
            conn.execute("UPDATE work_items SET status=?,owner_agent_id=NULL,active_claim_id=NULL,revision=revision+1,updated_at=? WHERE work_id=?", (status, now, claim["work_id"]))
            for artifact in artifacts or []:
                artifact_id = artifact.get("artifact_id") or new_id("art")
                conn.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (artifact_id, project_id, work["phase_id"], work["work_id"], artifact.get("name", artifact_id), artifact.get("kind", "file"), artifact.get("uri", ""), artifact.get("content_hash"), artifact.get("size"), artifact.get("mime_type"), claim["agent_id"], now, dumps(artifact.get("source_refs", [])), dumps(artifact.get("metadata", {}))))
            for blocker in blockers or []:
                conn.execute("INSERT INTO blockers VALUES (?,?,?,?,?,?,?,?,?)", (blocker.get("blocker_id") or new_id("blk"), project_id, work["work_id"], blocker.get("kind", "human"), blocker.get("summary", summary), dumps(blocker.get("requires", [])), claim["agent_id"], now, None))
            self._event(conn, project_id, "work.checked_in", "work", work["work_id"], {"claim_id": claim_id, "outcome": outcome, "summary": summary})
            result = conn.execute("SELECT * FROM work_items WHERE work_id=?", (work["work_id"],)).fetchone()
        self.recompute_ready(project_id)
        return self._json_row(result) or {}

    def release(self, claim_id: str) -> dict[str, Any]:
        return self.checkin(claim_id, "released", "claim released")

    def expire_claims(self, now: str | None = None) -> list[str]:
        now = now or utc_now()
        expired: list[str] = []
        with self._tx(True) as conn:
            rows = conn.execute("SELECT c.*,w.project_id,w.work_id FROM work_claims c JOIN work_items w ON w.work_id=c.work_id WHERE c.status='active' AND c.expires_at < ?", (now,)).fetchall()
            for claim in rows:
                expired.append(claim["claim_id"])
                work_status = "reconciliation" if claim["side_effecting"] else "claim_expired"
                conn.execute("UPDATE work_claims SET status='expired' WHERE claim_id=?", (claim["claim_id"],))
                conn.execute("UPDATE work_items SET status=?,owner_agent_id=NULL,active_claim_id=NULL,revision=revision+1,updated_at=? WHERE work_id=?", (work_status, now, claim["work_id"]))
                self._event(conn, claim["project_id"], "claim.expired", "claim", claim["claim_id"], {"work_id": claim["work_id"], "status": work_status})
        return expired

    def list_events(self, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM events WHERE project_id=? ORDER BY created_at DESC LIMIT ?", (project_id, limit))
        return [self._json_row(row) or {} for row in rows]

    def list_phases(self, project_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM phases WHERE project_id=? ORDER BY ordinal", (project_id,))
        return [self._json_row(row) or {} for row in rows]

    def list_dependencies(self, project_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT d.* FROM work_dependencies d JOIN work_items w ON w.work_id=d.work_id WHERE w.project_id=? ORDER BY d.work_id, d.depends_on_work_id",
            (project_id,),
        )
        return [dict(row) for row in rows]

    def list_artifacts(self, project_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM artifacts WHERE project_id=? ORDER BY created_at", (project_id,))
        return [self._json_row(row) or {} for row in rows]

    def list_attention(self, project_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM attention_state WHERE project_id=? AND resolved_at IS NULL ORDER BY created_at", (project_id,))
        return [self._json_row(row) or {} for row in rows]
