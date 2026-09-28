"""Vendor-neutral runtime adapters."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Any, Protocol

from .models import RuntimeHealth, RuntimeResult, WorkContext


class AgentRuntime(Protocol):
    def probe(self) -> RuntimeHealth: ...
    def execute(self, context: WorkContext) -> RuntimeResult: ...


class GenericCommandRuntime:
    def __init__(self, command: list[str], timeout_seconds: int = 300, identity: str = "generic-command"):
        if not command:
            raise ValueError("command is required")
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.identity = identity

    def probe(self) -> RuntimeHealth:
        return RuntimeHealth(True, True, self.identity)

    def execute(self, context: WorkContext) -> RuntimeResult:
        payload = {"work_id": context.work_id, "project_id": context.project_id, "objective": context.objective, "detail": context.detail, "acceptance_criteria": context.acceptance_criteria}
        started = time.perf_counter()
        try:
            completed = subprocess.run(self.command, input=json.dumps(payload), text=True, capture_output=True, timeout=self.timeout_seconds, check=False)
        except subprocess.TimeoutExpired as exc:
            return RuntimeResult("retryable_failure", "command timed out", stdout=exc.stdout or "", stderr=exc.stderr or "", partial_side_effect=True)
        elapsed = (time.perf_counter() - started) * 1000
        if completed.returncode == 0:
            return RuntimeResult("complete", "command completed", completed.stdout, completed.stderr, result_code=0)
        return RuntimeResult("retryable_failure", f"command exited with {completed.returncode}", completed.stdout, completed.stderr, result_code=completed.returncode, partial_side_effect=True)


class GenericHTTPRuntime:
    def __init__(self, url: str, timeout_seconds: int = 60, identity: str = "generic-http"):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.identity = identity

    def probe(self) -> RuntimeHealth:
        return RuntimeHealth(True, True, self.identity)

    def execute(self, context: WorkContext) -> RuntimeResult:
        payload = {"work_id": context.work_id, "project_id": context.project_id, "objective": context.objective, "detail": context.detail, "acceptance_criteria": context.acceptance_criteria}
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode() or "{}")
            return RuntimeResult(
                status=data.get("status", "complete"),
                summary=data.get("summary", "http runtime completed"),
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
                artifacts=data.get("artifacts", []),
                blockers=data.get("blockers", []),
                discovered_work=data.get("discovered_work", []),
                handoff=data.get("handoff", ""),
                result_code=data.get("result_code"),
                partial_side_effect=data.get("partial_side_effect", False),
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return RuntimeResult("retryable_failure", f"HTTP runtime failed: {exc}", partial_side_effect=True)
