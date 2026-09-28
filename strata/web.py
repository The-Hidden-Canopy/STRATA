"""Small standalone read-only web surface for local STRATA projects."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .compiler import SceneCompiler
from .project import StrataProject


def serve(project: StrataProject, host: str = "127.0.0.1", port: int = 8766) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def reply(self, status: int, value: object, content_type: str = "application/json") -> None:
            body = value if isinstance(value, bytes) else json.dumps(value, indent=2, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                return self.reply(200, b"<!doctype html><title>STRATA</title><h1>STRATA</h1><p>Local project inspection surface.</p>", "text/html; charset=utf-8")
            if parsed.path == "/api/v1/entities":
                return self.reply(200, {"entities": project.db.list_entities(project.project_id)})
            if parsed.path == "/api/v1/sources":
                return self.reply(200, {"sources": project.db.list_sources(project.project_id)})
            if parsed.path == "/api/v1/scene":
                query = parse_qs(parsed.query)
                scene = SceneCompiler(project).build_scene(query.get("time", [project.manifest.get("default_time", "unknown")])[0], query.get("branch", [project.default_branch])[0])
                return self.reply(200, scene)
            return self.reply(404, {"error": "not_found"})

    return ThreadingHTTPServer((host, port), Handler)

