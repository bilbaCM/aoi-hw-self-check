from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.integrations.ppmac.axis_map import load_axis_variable_map
from aoi_hw_check.integrations.ppmac.connection import PmacAsciiConnection
from aoi_hw_check.integrations.ppmac.motion_hw_collector import PPMACMotionHWCollector


class _FakeConnection:
    def __init__(self, values: dict[str, float]):
        self._values = values

    def query(self, variable: str) -> float:
        return self._values[variable]


class PPMACMotionHWCollectorTest(unittest.TestCase):
    def test_collects_values_per_axis_and_field(self) -> None:
        connection = _FakeConnection(
            {"Motor[1].ActPos": 12345.0, "Motor[1].Pwm": 42.5}
        )
        axis_map = {"X": {"encoder_count": "Motor[1].ActPos", "pwm_duty_percent": "Motor[1].Pwm"}}

        collector = PPMACMotionHWCollector(connection, axis_map)  # type: ignore[arg-type]
        state = collector.collect()

        self.assertEqual(
            state.axes["X"],
            {"encoder_count": 12345.0, "pwm_duty_percent": 42.5},
        )


class LoadAxisVariableMapTest(unittest.TestCase):
    def test_loads_map_and_skips_comment_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "map.json"
            path.write_text(
                '{"_comment": "note", "X": {"encoder_count": "Motor[1].ActPos"}}',
                encoding="utf-8",
            )

            axis_map = load_axis_variable_map(path)

            self.assertEqual(axis_map, {"X": {"encoder_count": "Motor[1].ActPos"}})

    def test_example_config_file_loads_without_comment_key(self) -> None:
        example_path = (
            Path(__file__).resolve().parent.parent / "config" / "ppmac_axis_map.example.json"
        )

        axis_map = load_axis_variable_map(example_path)

        self.assertNotIn("_comment", axis_map)
        self.assertIn("X", axis_map)


if __name__ == "__main__":
    unittest.main()
