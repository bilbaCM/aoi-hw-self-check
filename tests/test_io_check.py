from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.io_check.client import MockPLCTestModeClient
from aoi_hw_check.checks.io_check.danger_list import load_dangerous_io_ids
from aoi_hw_check.checks.io_check.judge import run_io_check
from aoi_hw_check.checks.io_check.models import IOPoint
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore


class IOCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_all_points_matching_passes(self) -> None:
        io_map = [IOPoint("io1", True, True), IOPoint("io2", False, False)]

        result = run_io_check(
            MockPLCTestModeClient(), io_map, set(), set(), self.store, "EQ01"
        )

        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertEqual(result.deviation, [])

    def test_mismatched_point_fails(self) -> None:
        io_map = [IOPoint("io1", True, True)]
        client = MockPLCTestModeClient(faulty_io_ids={"io1"})

        result = run_io_check(client, io_map, set(), set(), self.store, "EQ01")

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(result.deviation[0].field_path, "io1")

    def test_dangerous_point_without_approval_is_skipped(self) -> None:
        io_map = [IOPoint("io1", True, True), IOPoint("danger_io", True, True)]

        result = run_io_check(
            MockPLCTestModeClient(),
            io_map,
            dangerous_io_ids={"danger_io"},
            approved_dangerous_io_ids=set(),
            store=self.store,
            equipment_id="EQ01",
        )

        self.assertEqual(result.verdict, Verdict.NA)
        self.assertIn("danger_io", result.detail)

    def test_approved_dangerous_point_is_tested(self) -> None:
        io_map = [IOPoint("danger_io", True, True)]

        result = run_io_check(
            MockPLCTestModeClient(),
            io_map,
            dangerous_io_ids={"danger_io"},
            approved_dangerous_io_ids={"danger_io"},
            store=self.store,
            equipment_id="EQ01",
        )

        self.assertEqual(result.verdict, Verdict.PASS)

    def test_load_dangerous_io_ids_missing_file_returns_empty_set(self) -> None:
        self.assertEqual(
            load_dangerous_io_ids(Path(self._tmpdir.name) / "nonexistent.json"), set()
        )

    def test_load_dangerous_io_ids_reads_json_array(self) -> None:
        path = Path(self._tmpdir.name) / "danger.json"
        path.write_text('["io1", "io2"]', encoding="utf-8")

        self.assertEqual(load_dangerous_io_ids(path), {"io1", "io2"})


if __name__ == "__main__":
    unittest.main()
