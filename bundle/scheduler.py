"""Deterministic pull scheduling over the persisted ready frontier."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .store import Database, ValidationError


def _age_seconds(timestamp: str) -> float:
    created = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return max(0.0, (datetime.now(timezone.utc) - created).total_seconds())


def lane_rank(agent: dict[str, Any], lane: str) -> int:
    if lane == agent.get("primary_lane"):
        return 3
    if lane in agent.get("secondary_lanes", []):
        return 2
    if lane in agent.get("emergency_lanes", []):
        return 1
    return 0


def rank_candidates(candidates: list[dict[str, Any]], agent: dict[str, Any]) -> list[dict[str, Any]]:
    for item in candidates:
        item["eligibility_score"] = (
            item.get("priority", 0) * 100
            + lane_rank(agent, item["lane"]) * 20
            + min(_age_seconds(item["created_at"]) / 60.0, 50.0)
        )
    return sorted(candidates, key=lambda item: (-item["eligibility_score"], item["created_at"], item["work_id"]))


def pull(db: Database, project_id: str, agent_id: str) -> dict[str, Any] | None:
    agents = [agent for agent in db.list_agents(project_id) if agent["agent_id"] == agent_id]
    if not agents:
        raise ValidationError("agent is not a member of this project")
    candidates = db.candidate_work(project_id, agent_id)
    ranked = rank_candidates(candidates, agents[0])
    return ranked[0] if ranked else None
