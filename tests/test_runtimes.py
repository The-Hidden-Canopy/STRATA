from __future__ import annotations

import sys
import unittest

from bundle.models import WorkContext
from bundle.runtimes import GenericCommandRuntime


class RuntimeTests(unittest.TestCase):
    def test_generic_command_returns_result(self) -> None:
        runtime = GenericCommandRuntime([sys.executable, "-c", "print('runtime-ok')"])
        result = runtime.execute(WorkContext("w", "p", "run a command"))
        self.assertEqual(result.status, "complete")
        self.assertIn("runtime-ok", result.stdout)
