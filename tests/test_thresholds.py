from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.core.gate import InvalidGateTransition
from aoi_hw_check.core.models import GateStatus
from aoi_hw_check.core.thresholds import JSONCriteriaStore

CHECK_ITEM = "모션 H/W Check"


class JSONCriteriaStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = JSONCriteriaStore(Path(self._tmpdir.name) / "criteria.json")

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_missing_criteria_returns_none(self) -> None:
        self.assertIsNone(self.store.get_criteria(CHECK_ITEM, "X.encoder_count"))

    def test_get_criteria_returns_latest_version(self) -> None:
        self.store.save_criteria(CHECK_ITEM, "X.encoder_count", 90000, 110000)
        self.store.save_criteria(CHECK_ITEM, "X.encoder_count", 95000, 105000)

        criteria = self.store.get_criteria(CHECK_ITEM, "X.encoder_count")

        self.assertEqual((criteria.min_value, criteria.max_value), (95000, 105000))
        self.assertEqual(criteria.version, 2)

    def test_history_keeps_all_versions(self) -> None:
        self.store.save_criteria(CHECK_ITEM, "X.encoder_count", 90000, 110000)
        self.store.save_criteria(CHECK_ITEM, "X.encoder_count", 95000, 105000)

        history = self.store.list_criteria_history(CHECK_ITEM, "X.encoder_count")

        self.assertEqual([c.version for c in history], [1, 2])

    def test_criteria_is_persisted_across_instances(self) -> None:
        path = Path(self._tmpdir.name) / "persist.json"
        JSONCriteriaStore(path).save_criteria(CHECK_ITEM, "Y.pwm_duty_percent", 30, 60)

        reloaded = JSONCriteriaStore(path)
        criteria = reloaded.get_criteria(CHECK_ITEM, "Y.pwm_duty_percent")

        self.assertEqual((criteria.min_value, criteria.max_value), (30, 60))

    def test_new_criteria_starts_as_generated(self) -> None:
        criteria = self.store.save_criteria(CHECK_ITEM, "X.encoder_count", 90000, 110000)

        self.assertEqual(criteria.gate_status, GateStatus.GENERATED)


class CriteriaGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = JSONCriteriaStore(Path(self._tmpdir.name) / "criteria.json")
        self.store.save_criteria(CHECK_ITEM, "X.encoder_count", 90000, 110000)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_advancing_to_next_stage_updates_gate_status(self) -> None:
        criteria = self.store.advance_criteria_gate(
            CHECK_ITEM, "X.encoder_count", GateStatus.TRIAL
        )

        self.assertEqual(criteria.gate_status, GateStatus.TRIAL)
        self.assertEqual(
            self.store.get_criteria(CHECK_ITEM, "X.encoder_count").gate_status,
            GateStatus.TRIAL,
        )

    def test_advancing_does_not_create_a_new_version(self) -> None:
        self.store.advance_criteria_gate(CHECK_ITEM, "X.encoder_count", GateStatus.TRIAL)

        criteria = self.store.get_criteria(CHECK_ITEM, "X.encoder_count")
        self.assertEqual(criteria.version, 1)
        self.assertEqual(
            len(self.store.list_criteria_history(CHECK_ITEM, "X.encoder_count")), 1
        )

    def test_skipping_a_stage_is_rejected(self) -> None:
        with self.assertRaises(InvalidGateTransition):
            self.store.advance_criteria_gate(
                CHECK_ITEM, "X.encoder_count", GateStatus.OPTIMIZED
            )

    def test_advancing_unregistered_criteria_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.store.advance_criteria_gate(CHECK_ITEM, "Y.unknown", GateStatus.TRIAL)

    def test_gate_status_persists_across_instances(self) -> None:
        path = Path(self._tmpdir.name) / "persist_gate.json"
        store = JSONCriteriaStore(path)
        store.save_criteria(CHECK_ITEM, "X.encoder_count", 90000, 110000)
        store.advance_criteria_gate(CHECK_ITEM, "X.encoder_count", GateStatus.TRIAL)

        reloaded = JSONCriteriaStore(path)
        self.assertEqual(
            reloaded.get_criteria(CHECK_ITEM, "X.encoder_count").gate_status,
            GateStatus.TRIAL,
        )


if __name__ == "__main__":
    unittest.main()
