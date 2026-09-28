from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bundle.scheduler import pull
from bundle.store import ConflictError, Database, ValidationError


class BundleCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "bundle.db")
        self.project = self.db.create_project("test project", objective="exercise the loop")
        self.project_id = self.project["project_id"]

    def tearDown(self) -> None:
        self.db.close()
        self.temp.cleanup()

    def test_claim_heartbeat_checkin_and_dependency_frontier(self) -> None:
        agent = self.db.create_agent(self.project_id, "worker", ["code.python"])
        first = self.db.create_work(self.project_id, "first", required_capabilities=["code.python"])
        second = self.db.create_work(self.project_id, "second", dependencies=[first["work_id"]])

        candidate = pull(self.db, self.project_id, agent["agent_id"])
        self.assertEqual(candidate["work_id"], first["work_id"])
        claim = self.db.claim(first["work_id"], agent["agent_id"], first["revision"])
        self.db.heartbeat(claim["claim_id"], current_action="testing")
        result = self.db.checkin(claim["claim_id"], "complete", "first complete", artifacts=[{"name": "result.txt", "uri": "memory://result"}])

        self.assertEqual(result["status"], "complete")
        ready = self.db.list_work(self.project_id, "ready")
        self.assertEqual([item["work_id"] for item in ready], [second["work_id"]])
        self.assertEqual(len(self.db.list_artifacts(self.project_id)), 1)

    def test_revision_prevents_duplicate_claim(self) -> None:
        agent_a = self.db.create_agent(self.project_id, "a")
        agent_b = self.db.create_agent(self.project_id, "b")
        work = self.db.create_work(self.project_id, "single claim")
        self.db.claim(work["work_id"], agent_a["agent_id"], work["revision"])
        with self.assertRaises(ConflictError):
            self.db.claim(work["work_id"], agent_b["agent_id"], work["revision"])

    def test_cycle_is_rejected(self) -> None:
        first = self.db.create_work(self.project_id, "first")
        second = self.db.create_work(self.project_id, "second")
        self.db.add_dependency(first["work_id"], second["work_id"])
        with self.assertRaises(ValidationError):
            self.db.add_dependency(second["work_id"], first["work_id"])

    def test_expired_side_effecting_claim_requires_reconciliation(self) -> None:
        agent = self.db.create_agent(self.project_id, "worker")
        work = self.db.create_work(self.project_id, "external mutation", side_effecting=True)
        claim = self.db.claim(work["work_id"], agent["agent_id"], work["revision"], ttl_seconds=5)
        expired = self.db.expire_claims("9999-01-01T00:00:00Z")
        self.assertEqual(expired, [claim["claim_id"]])
        self.assertEqual(self.db.get_work(work["work_id"])["status"], "reconciliation")
