from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.checks.single_unit_check.judge import run_single_unit_check
from aoi_hw_check.checks.single_unit_check.models import SequenceStepResult
from aoi_hw_check.checks.single_unit_check.runner import MockSingleUnitSequenceRunner
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore


class SingleUnitCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteResultStore(Path(self._tmpdir.name) / "results.sqlite3")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_first_run_without_supervision_is_na(self) -> None:
        result = run_single_unit_check(
            MockSingleUnitSequenceRunner(), self.store, "EQ01", supervised=False
        )

        self.assertEqual(result.verdict, Verdict.NA)

    def test_first_run_with_supervision_executes_and_passes(self) -> None:
        result = run_single_unit_check(
            MockSingleUnitSequenceRunner(), self.store, "EQ01", supervised=True
        )

        self.assertEqual(result.verdict, Verdict.PASS)

    def test_subsequent_run_does_not_require_supervision(self) -> None:
        run_single_unit_check(
            MockSingleUnitSequenceRunner(), self.store, "EQ01", supervised=True
        )

        result = run_single_unit_check(
            MockSingleUnitSequenceRunner(), self.store, "EQ01", supervised=False
        )

        self.assertEqual(result.verdict, Verdict.PASS)

    def test_abnormal_stop_fails(self) -> None:
        steps = [
            SequenceStepResult("step1", completed=True, abnormal_stop=False),
            SequenceStepResult("step2", completed=False, abnormal_stop=True),
        ]

        result = run_single_unit_check(
            MockSingleUnitSequenceRunner(steps), self.store, "EQ01", supervised=True
        )

        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertEqual(result.deviation[0].field_path, "step2")


if __name__ == "__main__":
    unittest.main()
