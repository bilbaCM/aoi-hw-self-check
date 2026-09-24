from __future__ import annotations

import os
import tempfile
import unittest

from aoi_hw_check.cli import CRITERIA_STORE_FILES, list_all_criteria
from aoi_hw_check.core.thresholds import JSONCriteriaStore


class ListAllCriteriaTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._old_cwd = os.getcwd()
        os.chdir(self._tmpdir.name)

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        self._tmpdir.cleanup()

    def test_empty_when_no_criteria_registered_anywhere(self) -> None:
        self.assertEqual(list_all_criteria(), [])

    def test_finds_criteria_registered_in_any_of_the_known_store_files(self) -> None:
        JSONCriteriaStore(CRITERIA_STORE_FILES[0]).save_criteria(
            "모션 H/W Check", "X.encoder_count", 90000, 110000
        )
        JSONCriteriaStore(CRITERIA_STORE_FILES[-1]).save_criteria(
            "계측 Y축 Gantry 직각도", "squareness_deg", 0.0, 0.05
        )

        found = list_all_criteria()

        self.assertEqual(len(found), 2)
        store_paths = {path for path, _criteria in found}
        self.assertEqual(store_paths, {CRITERIA_STORE_FILES[0], CRITERIA_STORE_FILES[-1]})
        check_items = {criteria.check_item for _path, criteria in found}
        self.assertEqual(check_items, {"모션 H/W Check", "계측 Y축 Gantry 직각도"})

    def test_only_returns_latest_version_per_key(self) -> None:
        store = JSONCriteriaStore(CRITERIA_STORE_FILES[0])
        store.save_criteria("모션 H/W Check", "X.encoder_count", 90000, 110000)
        store.save_criteria("모션 H/W Check", "X.encoder_count", 95000, 105000)

        found = list_all_criteria()

        self.assertEqual(len(found), 1)
        _path, criteria = found[0]
        self.assertEqual(criteria.version, 2)


if __name__ == "__main__":
    unittest.main()
