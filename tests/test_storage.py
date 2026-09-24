from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.core.storage import SQLiteResultStore

CHECK_ITEM = "PC 동작 Check"


class BaselineHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "test.sqlite3")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_get_baseline_returns_latest_snapshot(self) -> None:
        self.store.save_baseline("EQ01", CHECK_ITEM, {"os.version": "Win10"})
        self.store.save_baseline("EQ01", CHECK_ITEM, {"os.version": "Win11"})

        self.assertEqual(
            self.store.get_baseline("EQ01", CHECK_ITEM), {"os.version": "Win11"}
        )

    def test_baseline_history_keeps_all_versions(self) -> None:
        self.store.save_baseline("EQ01", CHECK_ITEM, {"os.version": "Win10"})
        self.store.save_baseline("EQ01", CHECK_ITEM, {"os.version": "Win11"})

        history = self.store.list_baseline_history("EQ01", CHECK_ITEM)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["snapshot"], {"os.version": "Win10"})
        self.assertEqual(history[1]["snapshot"], {"os.version": "Win11"})

    def test_baselines_are_isolated_per_equipment(self) -> None:
        self.store.save_baseline("EQ01", CHECK_ITEM, {"os.version": "Win10"})

        self.assertIsNone(self.store.get_baseline("EQ02", CHECK_ITEM))


if __name__ == "__main__":
    unittest.main()
