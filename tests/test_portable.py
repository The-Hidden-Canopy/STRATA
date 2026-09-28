from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bundle.portable import export_project, import_project
from bundle.store import Database


class PortableProjectTests(unittest.TestCase):
    def test_export_and_import_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Database(root / "source.db")
            project = source.create_project("portable", objective="move me")
            source.create_work(project["project_id"], "keep this work", priority=4)
            archive = export_project(source, project["project_id"], root / "portable.bundle.zip")
            self.assertTrue(archive.is_file())
            destination = Database(root / "destination.db")
            imported = import_project(destination, archive)
            self.assertEqual(imported["name"], "portable")
            self.assertEqual(destination.list_work(imported["project_id"])[0]["title"], "keep this work")
            source.close()
            destination.close()
