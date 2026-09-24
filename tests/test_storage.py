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


class CrossEquipmentBaselineTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "test.sqlite3")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_no_snapshots_yields_empty_dict(self) -> None:
        self.assertEqual(self.store.list_latest_baselines_by_equipment(CHECK_ITEM), {})

    def test_collects_latest_snapshot_per_equipment(self) -> None:
        self.store.save_baseline("EQ01", CHECK_ITEM, {"x": 1.0})
        self.store.save_baseline("EQ02", CHECK_ITEM, {"x": 2.0})
        self.store.save_baseline("EQ01", CHECK_ITEM, {"x": 1.5})  # EQ01 갱신

        snapshots = self.store.list_latest_baselines_by_equipment(CHECK_ITEM)

        self.assertEqual(snapshots, {"EQ01": {"x": 1.5}, "EQ02": {"x": 2.0}})

    def test_other_check_items_are_excluded(self) -> None:
        self.store.save_baseline("EQ01", CHECK_ITEM, {"x": 1.0})
        self.store.save_baseline("EQ01", "다른 항목", {"x": 9.0})

        snapshots = self.store.list_latest_baselines_by_equipment(CHECK_ITEM)

        self.assertEqual(snapshots, {"EQ01": {"x": 1.0}})


class ScanAttemptTrackingTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "test.sqlite3")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_no_attempts_yet_counts_zero(self) -> None:
        self.assertEqual(self.store.count_scan_attempts_since_last_pass("EQ01"), 0)

    def test_failed_attempts_accumulate(self) -> None:
        self.store.record_scan_attempt("EQ01", all_passed=False)
        self.store.record_scan_attempt("EQ01", all_passed=False)

        self.assertEqual(self.store.count_scan_attempts_since_last_pass("EQ01"), 2)

    def test_count_resets_after_a_pass(self) -> None:
        self.store.record_scan_attempt("EQ01", all_passed=False)
        self.store.record_scan_attempt("EQ01", all_passed=True)
        self.store.record_scan_attempt("EQ01", all_passed=False)

        self.assertEqual(self.store.count_scan_attempts_since_last_pass("EQ01"), 1)

    def test_attempts_are_isolated_per_equipment(self) -> None:
        self.store.record_scan_attempt("EQ01", all_passed=False)

        self.assertEqual(self.store.count_scan_attempts_since_last_pass("EQ02"), 0)


if __name__ == "__main__":
    unittest.main()
