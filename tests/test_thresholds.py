from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
