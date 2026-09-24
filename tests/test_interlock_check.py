from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.interlock_check.example_criteria import seed_example_criteria
from aoi_hw_check.checks.interlock_check.judge import run_interlock_check
from aoi_hw_check.checks.interlock_check.models import InterlockSignalEvent
from aoi_hw_check.checks.interlock_check.runner import MockInterlockTestRunner
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore

EXPECTED_SEQUENCE = ["upstream_ready", "load_request", "load_complete", "downstream_ack"]


class InterlockCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")
        self.criteria_store = JSONCriteriaStore(Path(self._tmpdir.name) / "criteria.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_normal_sequence_passes(self) -> None:
        result = run_interlock_check(
            MockInterlockTestRunner(),
            EXPECTED_SEQUENCE,
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.PASS)

    def test_missing_signal_fails(self) -> None:
        events = [
            InterlockSignalEvent("upstream_ready", 1, 120.0, True),
            InterlockSignalEvent("load_request", 2, 80.0, False),
        ]

        result = run_interlock_check(
            MockInterlockTestRunner(events),
            EXPECTED_SEQUENCE,
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertTrue(
            any(m.field_path == "load_request" for m in result.deviation)
        )

    def test_out_of_order_sequence_fails(self) -> None:
        events = [
            InterlockSignalEvent("upstream_ready", 2, 120.0, True),
            InterlockSignalEvent("load_request", 1, 80.0, True),
            InterlockSignalEvent("load_complete", 3, 200.0, True),
            InterlockSignalEvent("downstream_ack", 4, 150.0, True),
        ]

        result = run_interlock_check(
            MockInterlockTestRunner(events),
            EXPECTED_SEQUENCE,
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertTrue(any(m.field_path == "sequence_order" for m in result.deviation))

    def test_excessive_delay_fails_when_criteria_registered(self) -> None:
        seed_example_criteria(self.criteria_store)
        events = [
            InterlockSignalEvent("upstream_ready", 1, 999.0, True),
            InterlockSignalEvent("load_request", 2, 80.0, True),
            InterlockSignalEvent("load_complete", 3, 200.0, True),
            InterlockSignalEvent("downstream_ack", 4, 150.0, True),
        ]

        result = run_interlock_check(
            MockInterlockTestRunner(events),
            EXPECTED_SEQUENCE,
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertTrue(
            any(
                m.field_path == "upstream_ready.response_delay_ms"
                for m in result.deviation
            )
        )

    def test_delay_without_registered_criteria_is_ignored(self) -> None:
        events = [
            InterlockSignalEvent("upstream_ready", 1, 999.0, True),
            InterlockSignalEvent("load_request", 2, 80.0, True),
            InterlockSignalEvent("load_complete", 3, 200.0, True),
            InterlockSignalEvent("downstream_ack", 4, 150.0, True),
        ]

        result = run_interlock_check(
            MockInterlockTestRunner(events),
            EXPECTED_SEQUENCE,
            self.criteria_store,
            self.store,
            "EQ01",
        )

        self.assertEqual(result.verdict, Verdict.PASS)


if __name__ == "__main__":
    unittest.main()
