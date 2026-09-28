from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from bundle.store import Database
from bundle.web.server import serve


class WebApiTests(unittest.TestCase):
    def test_project_and_work_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "bundle.db")
            server = serve(db, "127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            request = urllib.request.Request(base + "/api/v1/projects", data=json.dumps({"name": "web project"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request) as response:
                project = json.loads(response.read())
                self.assertEqual(response.status, 201)
            with urllib.request.urlopen(base + "/api/v1/projects") as response:
                projects = json.loads(response.read())
            self.assertEqual(projects["projects"][0]["project_id"], project["project_id"])
            server.shutdown()
            server.server_close()
            db.close()
