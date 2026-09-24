from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.core.models import CheckResult, Verdict
from aoi_hw_check.core.report import build_action_item_list
from aoi_hw_check.core.storage import SQLiteResultStore


class BuildActionItemListTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _save(self, check_item: str, verdict: Verdict, equipment_id: str = "EQ01") -> None:
        self.store.save_result(
            CheckResult(equipment_id=equipment_id, check_item=check_item, verdict=verdict)
        )

    def test_no_results_yields_empty_list(self) -> None:
        self.assertEqual(build_action_item_list(self.store, "EQ01"), [])

    def test_only_fail_and_na_are_included(self) -> None:
        self._save("PC 동작 Check", Verdict.PASS)
        self._save("I/O Check", Verdict.FAIL)
        self._save("모션 H/W Check", Verdict.NA)

        items = build_action_item_list(self.store, "EQ01")

        self.assertEqual(
            [r.check_item for r in items], ["I/O Check", "모션 H/W Check"]
        )

    def test_only_latest_result_per_item_is_considered(self) -> None:
        self._save("I/O Check", Verdict.FAIL)
        self._save("I/O Check", Verdict.PASS)

        self.assertEqual(build_action_item_list(self.store, "EQ01"), [])

    def test_results_from_other_equipment_are_excluded(self) -> None:
        self._save("I/O Check", Verdict.FAIL, equipment_id="EQ02")

        self.assertEqual(build_action_item_list(self.store, "EQ01"), [])


if __name__ == "__main__":
    unittest.main()
