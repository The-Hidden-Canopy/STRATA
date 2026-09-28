"""Small typed models shared by runtime adapters and services."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Outcome = Literal[
    "complete",
    "blocked",
    "needs_review",
    "retryable_failure",
    "final_failure",
    "released",
]


@dataclass(slots=True)
class WorkContext:
    work_id: str
    project_id: str
    objective: str
    detail: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    dependency_outputs: list[dict[str, Any]] = field(default_factory=list)
    role: str | None = None
    lane: str | None = None
    capability_constraints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RuntimeHealth:
    ready: bool
    healthy: bool
    runtime_identity: str
    model_identity: str | None = None
    active_execution_count: int = 0
    latency_ms: float | None = None
    last_error: str | None = None


@dataclass(slots=True)
class RuntimeResult:
    status: Outcome
    summary: str
    stdout: str = ""
    stderr: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[dict[str, Any]] = field(default_factory=list)
    discovered_work: list[dict[str, Any]] = field(default_factory=list)
    handoff: str = ""
    result_code: int | None = None
    partial_side_effect: bool = False
