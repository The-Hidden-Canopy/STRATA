from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bundle.models import WorkContext
from bundle.runtimes import GenericHTTPRuntime
from bundle.scheduler import pull
from bundle.store import ConflictError, Database
from bundle.web.server import serve


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(request) as response:
        return response.status, json.loads(response.read().decode() or "{}")


class DeepStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "bundle.db")
        self.project = self.db.create_project("deep")
        self.project_id = self.project["project_id"]

    def tearDown(self) -> None:
        self.db.close()
        self.temp.cleanup()

    def test_concurrent_claim_race_has_one_winner(self) -> None:
        agents = [self.db.create_agent(self.project_id, f"worker-{i}") for i in range(8)]
        work = self.db.create_work(self.project_id, "one winner")
        barrier = threading.Barrier(len(agents))
        winners: list[str] = []
        conflicts: list[str] = []
        unexpected: list[Exception] = []

        def attempt(agent: dict) -> None:
            try:
                barrier.wait(timeout=5)
                claim = self.db.claim(work["work_id"], agent["agent_id"], work["revision"])
                winners.append(claim["agent_id"])
            except ConflictError as exc:
                conflicts.append(str(exc))
            except Exception as exc:  # pragma: no cover - failure diagnostics
                unexpected.append(exc)

        threads = [threading.Thread(target=attempt, args=(agent,)) for agent in agents]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(unexpected, unexpected)
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(conflicts), len(agents) - 1)
        self.assertEqual(self.db.get_work(work["work_id"])["status"], "claimed")

    def test_expired_non_side_effect_claim_returns_to_ready(self) -> None:
        agent = self.db.create_agent(self.project_id, "worker")
        work = self.db.create_work(self.project_id, "recoverable")
        claim = self.db.claim(work["work_id"], agent["agent_id"], work["revision"], ttl_seconds=5)
        self.db.expire_claims("9999-01-01T00:00:00Z")
        self.assertEqual(self.db.get_work(work["work_id"])["status"], "claim_expired")
        self.db.recompute_ready(self.project_id)
        self.assertEqual(self.db.get_work(work["work_id"])["status"], "ready")
        self.assertEqual(self.db.expire_claims("9999-01-01T00:00:00Z"), [])
        self.assertTrue(claim["claim_id"])

    def test_lane_and_capability_policy_is_enforced_at_claim(self) -> None:
        agent = self.db.create_agent(self.project_id, "frontend", ["code.javascript"], primary_lane="frontend")
        work = self.db.create_work(self.project_id, "backend-only", lane="backend", required_capabilities=["code.python"])
        self.assertIsNone(pull(self.db, self.project_id, agent["agent_id"]))
        with self.assertRaises(ConflictError):
            self.db.claim(work["work_id"], agent["agent_id"], work["revision"])


class DeepWebTests(unittest.TestCase):
    def test_all_claim_lifecycle_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "bundle.db")
            project = db.create_project("api lifecycle")
            agent = db.create_agent(project["project_id"], "api worker")
            work = db.create_work(project["project_id"], "api work")
            server = serve(db, "127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                code, pulled = request_json(base + f"/api/v1/projects/{project['project_id']}/pull", "POST", {"agent_id": agent["agent_id"]})
                self.assertEqual(code, 200)
                self.assertEqual(pulled["work"]["work_id"], work["work_id"])
                code, claim = request_json(base + f"/api/v1/work/{work['work_id']}/claim", "POST", {"agent_id": agent["agent_id"], "expected_revision": work["revision"]})
                self.assertEqual(code, 201)
                code, heartbeat = request_json(base + f"/api/v1/claims/{claim['claim_id']}/heartbeat", "POST", {"current_action": "deep test"})
                self.assertEqual(code, 200)
                self.assertEqual(heartbeat["claim_id"], claim["claim_id"])
                code, checked = request_json(base + f"/api/v1/claims/{claim['claim_id']}/checkin", "POST", {"outcome": "complete", "summary": "done"})
                self.assertEqual(code, 200)
                self.assertEqual(checked["status"], "complete")
            finally:
                server.shutdown()
                server.server_close()
                db.close()


class HTTPRuntimeTests(unittest.TestCase):
    def test_generic_http_runtime_normalizes_result(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                body = json.dumps({"status": "complete", "summary": payload["objective"] + " done", "result_code": 0}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = GenericHTTPRuntime(f"http://127.0.0.1:{server.server_port}").execute(WorkContext("w", "p", "ship"))
            self.assertEqual(result.status, "complete")
            self.assertEqual(result.summary, "ship done")
            self.assertEqual(result.result_code, 0)
        finally:
            server.shutdown()
            server.server_close()


class CLIWorkflowTests(unittest.TestCase):
    def test_cli_can_run_project_to_checkin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "bundle.db")

            def cli(*args: str) -> dict:
                completed = subprocess.run([sys.executable, "-m", "bundle", "--db", db_path, *args], capture_output=True, text=True, check=True)
                return json.loads(completed.stdout)

            project = cli("project", "create", "cli deep")
            agent = cli("agent", "create", project["project_id"], "cli worker")
            work = cli("work", "create", project["project_id"], "cli work")
            candidate = cli("work", "pull", project["project_id"], agent["agent_id"])
            self.assertEqual(candidate["work_id"], work["work_id"])
            claim = cli("work", "claim", work["work_id"], agent["agent_id"], str(work["revision"]))
            cli("heartbeat", claim["claim_id"], "--action", "testing")
            checked = cli("checkin", claim["claim_id"], "--summary", "complete")
            self.assertEqual(checked["status"], "complete")
