"""Loopback-only HTTP API and zero-build web UI."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from ..scheduler import pull
from ..store import BundleError, Database


STATIC = Path(__file__).parent / "static"


class BundleHandler(BaseHTTPRequestHandler):
    db: Database

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(size).decode() or "{}") if size else {}

    def _error(self, exc: Exception) -> None:
        status = HTTPStatus.CONFLICT if isinstance(exc, BundleError) else HTTPStatus.BAD_REQUEST
        self._json(status, {"error": type(exc).__name__, "message": str(exc)})

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/":
            return self._static("index.html")
        if path.startswith("/static/"):
            return self._static(path.removeprefix("/static/"))
        try:
            parts = path.split("/")
            if path == "/api/v1/projects":
                return self._json(200, {"projects": self.db.list_projects()})
            if len(parts) == 5 and parts[3] == "projects" and parts[4]:
                return self._json(200, self.db.get_project(parts[4]))
            if len(parts) == 6 and parts[3] == "projects" and parts[5] in {"work", "agents", "artifacts", "attention", "events"}:
                project_id = parts[4]
                getter = {"work": lambda: self.db.list_work(project_id), "agents": lambda: self.db.list_agents(project_id), "artifacts": lambda: self.db.list_artifacts(project_id), "attention": lambda: self.db.list_attention(project_id), "events": lambda: self.db.list_events(project_id)}[parts[5]]
                return self._json(200, {parts[5]: getter()})
            if len(parts) == 7 and parts[3] == "projects" and parts[5] == "work" and parts[6] == "ready":
                return self._json(200, {"work": self.db.list_work(parts[4], "ready")})
            if path == "/api/v1/runtimes":
                return self._json(200, {"runtimes": self.db.list_runtimes()})
            self._json(404, {"error": "not_found"})
        except Exception as exc:
            self._error(exc)

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        body = self._body()
        try:
            parts = path.split("/")
            if path == "/api/v1/projects":
                return self._json(201, self.db.create_project(body.get("name", ""), body.get("description", ""), body.get("objective", ""), body.get("success_definition", "")))
            if len(parts) == 6 and parts[3] == "projects" and parts[5] == "phases":
                return self._json(201, self.db.create_phase(parts[4], body.get("name", ""), body.get("objective", ""), body.get("ordinal")))
            if len(parts) == 6 and parts[3] == "projects" and parts[5] == "work":
                return self._json(201, self.db.create_work(parts[4], body.get("title", ""), body.get("objective", ""), body.get("detail", ""), body.get("phase_id"), body.get("lane", "core"), body.get("priority", 0), body.get("required_capabilities", []), body.get("acceptance_criteria", []), body.get("dependencies", []), body.get("max_attempts", 3), body.get("side_effecting", False)))
            if len(parts) == 6 and parts[3] == "projects" and parts[5] == "agents":
                return self._json(201, self.db.create_agent(parts[4], body.get("name", ""), body.get("capabilities", []), body.get("primary_lane", "core"), body.get("secondary_lanes", []), body.get("max_active_claims", 1), body.get("agent_id")))
            if len(parts) == 6 and parts[3] == "projects" and parts[5] == "pull":
                return self._json(200, {"work": pull(self.db, parts[4], body["agent_id"])})
            if len(parts) == 6 and parts[3] == "work" and parts[5] == "claim":
                result = self.db.claim(parts[4], body["agent_id"], body["expected_revision"], body.get("agent_instance_id", "default"), body.get("ttl_seconds", 120))
                return self._json(201, result)
            if len(parts) == 6 and parts[3] == "claims" and parts[5] == "heartbeat":
                return self._json(200, self.db.heartbeat(parts[4], body.get("state", "working"), body.get("current_action", ""), body.get("progress_hint", ""), body.get("blocker_hint", ""), body.get("ttl_seconds", 120)))
            if len(parts) == 6 and parts[3] == "claims" and parts[5] == "checkin":
                return self._json(200, self.db.checkin(parts[4], body.get("outcome", "complete"), body.get("summary", ""), body.get("artifacts", []), body.get("blockers", [])))
            if len(parts) == 6 and parts[3] == "claims" and parts[5] == "release":
                return self._json(200, self.db.release(parts[4]))
            if path == "/api/v1/runtimes":
                return self._json(201, self.db.add_runtime(body.get("kind", "generic-command"), body.get("config", {}), body.get("identity")))
            self._json(404, {"error": "not_found"})
        except Exception as exc:
            self._error(exc)

    def _static(self, name: str) -> None:
        target = (STATIC / name).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file():
            return self._json(404, {"error": "not_found"})
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(db: Database, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    handler = type("ConfiguredBundleHandler", (BundleHandler,), {"db": db})
    server = ThreadingHTTPServer((host, port), handler)
    return server
