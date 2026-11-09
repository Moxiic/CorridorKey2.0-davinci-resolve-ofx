import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from model_cache import can_retain, retention_fits


class ModelCacheBudgetTests(unittest.TestCase):
    def test_reserves_ram_headroom(self):
        gb = 1024**3
        self.assertFalse(retention_fits(6*gb, 5*gb))
        self.assertTrue(retention_fits(8*gb, 5*gb))
        self.assertFalse(retention_fits(0, 5*gb))

    def test_environment_can_disable_model_retention(self):
        with patch.dict(os.environ, {"CORRIDORKEY2_CPU_MODEL_CACHE": "0"}):
            self.assertFalse(can_retain(None))
