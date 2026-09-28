from __future__ import annotations

import hashlib
import io
import json
import tempfile
import threading
import unittest
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

from strata.archive import pack_project, unpack_project
from strata.compiler import SceneCompiler
from strata.importers import import_file
from strata.project import StrataProject
from strata.patches import create_patch, project_hash, write_patch
from strata.spatial import ENU, Geodetic, ecef_to_enu, enu_to_ecef, geodetic_to_ecef
from strata.temporal import HistoricalDate, HistoricalInterval, interval
from strata.verify import doctor_project, verify_project
from strata.web import serve as serve_web


class StrataTemporalTests(unittest.TestCase):
    def test_historical_precision_is_lossless(self) -> None:
        circa = HistoricalDate.parse("circa 1910")
        self.assertEqual(circa.raw, "circa 1910")
        self.assertEqual(circa.precision, "circa-year")
        self.assertEqual(circa.earliest.isoformat(), "1909-01-01")
        self.assertEqual(circa.latest.isoformat(), "1911-12-31")

    def test_unknown_and_bounded_interval(self) -> None:
        value = HistoricalInterval.parse("before 1948", "after 1890")
        self.assertIsNone(value.start.earliest)
        self.assertIsNone(value.end.latest)


class StrataProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "town.strata"
        self.project = StrataProject.create(self.root, "Historic Town")

    def tearDown(self) -> None:
        self.project.close()
        self.temp.cleanup()

    def test_manifest_blob_and_source_import(self) -> None:
        source_file = Path(self.temp.name) / "map.geojson"
        source_file.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
        result = import_file(self.project, source_file, "geojson")
        digest = hashlib.sha256(source_file.read_bytes()).hexdigest()
        self.assertEqual(result.source["content_hash"], digest)
        self.assertTrue(self.project.blobs.path_for(digest).is_file())
        self.assertTrue(verify_project(self.root)["ok"])

    def test_entities_states_assertions_branch_and_scene(self) -> None:
        db = self.project.db
        entity = db.create_entity(self.project.project_id, "building", "Old Hotel")
        state = db.add_state(entity["entity_id"], interval("1890", "1948"), {"floors": 2}, geometry_class="documented", uncertainty={"source_reliability": 0.9})
        source = db.add_source(self.project.project_id, "Permit 1911", "document")
        observation = db.add_observation(self.project.project_id, source["source_id"], {"visible_windows": 4}, entity["entity_id"])
        assertion = db.add_assertion(self.project.project_id, entity["entity_id"], "building.floors", 3, interval("1911", "1948"), observation_ids=[observation["observation_id"]])
        branch = db.create_branch(self.project.project_id, "hypothesis/remodeled", parent_branch_id=db.branch_by_name(self.project.project_id, "main")["branch_id"])
        db.set_branch_assertion(branch["branch_id"], assertion["assertion_id"], "accepted")
        db.add_decision(self.project.project_id, branch["branch_id"], entity["entity_id"], assertion["assertion_id"], "accept", "Permit supports the remodel")
        scene_a = SceneCompiler(self.project).build_scene("1920-01-01", "hypothesis/remodeled")
        scene_b = SceneCompiler(self.project).build_scene("1920-01-01", "hypothesis/remodeled")
        self.assertEqual(scene_a["root_hash"], scene_b["root_hash"])
        self.assertEqual(scene_a["entities"][0]["state"]["state_id"], state["state_id"])
        gltf = SceneCompiler.write_gltf(scene_a, self.root / "exports" / "scene.gltf")
        self.assertEqual(json.loads(gltf.read_text(encoding="utf-8"))["asset"]["version"], "2.0")

    def test_archive_round_trip(self) -> None:
        archive = pack_project(self.root, Path(self.temp.name) / "town.strata.zip")
        restored = Path(self.temp.name) / "restored"
        unpack_project(archive, restored)
        self.assertTrue((restored / "manifest.json").is_file())
        self.assertTrue(verify_project(restored)["ok"])

    def test_doctor_reports_healthy_workspace(self) -> None:
        report = doctor_project(self.root)
        self.assertTrue(report["ok"], report)
        self.assertIn("sqlite.integrity", {item["name"] for item in report["checks"]})

    def test_web_surface_serves_frontend_and_project_api(self) -> None:
        server = serve_web(self.project, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            html = urllib.request.urlopen(base + "/", timeout=2).read().decode("utf-8")
            javascript = urllib.request.urlopen(base + "/static/app.js", timeout=2).read().decode("utf-8")
            stylesheet = urllib.request.urlopen(base + "/static/styles.css", timeout=2).read().decode("utf-8")
            api = json.loads(urllib.request.urlopen(base + "/api/v1/project", timeout=2).read())
            self.assertIn("Spatial evidence workbench", html)
            self.assertIn("function init", javascript)
            self.assertIn("--teal", stylesheet)
            self.assertEqual(api["default_branch"], "main")
        finally:
            server.shutdown()
            server.server_close()

    def test_branch_merge_refuses_semantic_conflict(self) -> None:
        db = self.project.db
        entity = db.create_entity(self.project.project_id, "building", "Conflicted Building")
        first = db.add_assertion(self.project.project_id, entity["entity_id"], "building.floors", 2, interval("1900", "1910"))
        second = db.add_assertion(self.project.project_id, entity["entity_id"], "building.floors", 3, interval("1900", "1910"))
        base = db.branch_by_name(self.project.project_id, "main")
        left = db.create_branch(self.project.project_id, "left", base["branch_id"])
        right = db.create_branch(self.project.project_id, "right", base["branch_id"])
        db.set_branch_assertion(left["branch_id"], first["assertion_id"], "accepted")
        db.set_branch_assertion(right["branch_id"], first["assertion_id"], "rejected")
        result = db.merge_branch(left["branch_id"], right["branch_id"])
        self.assertFalse(result["merged"])
        self.assertEqual(result["conflicts"], [first["assertion_id"]])
        self.assertNotIn(second["assertion_id"], result["conflicts"])

    def test_spatial_enu_round_trip(self) -> None:
        origin = Geodetic(36.0, -116.0, 100.0)
        local = ENU(12.5, -4.0, 2.0)
        point = enu_to_ecef(origin, local)
        recovered = ecef_to_enu(origin, point)
        self.assertAlmostEqual(recovered.east, local.east, places=6)
        self.assertAlmostEqual(recovered.north, local.north, places=6)
        self.assertAlmostEqual(recovered.up, local.up, places=6)
        self.assertNotEqual(geodetic_to_ecef(origin).x, 0)

    def test_offline_patch_has_stable_base_hash(self) -> None:
        base = project_hash(self.root)
        patch_path = write_patch(create_patch(base, "tester", [{"op": "add", "path": "entity/1"}]), self.root / "exports" / "change.stratapatch")
        self.assertEqual(json.loads(patch_path.read_text(encoding="utf-8"))["base_project_hash"], base)


class StrataCliTests(unittest.TestCase):
    def test_init_and_verify_commands(self) -> None:
        from strata.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cli-project"
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["init", str(root), "--title", "CLI Town"]), 0)
                self.assertEqual(main(["verify", str(root)]), 0)
            self.assertIn("CLI Town", output.getvalue())
