from __future__ import annotations

import unittest
from datetime import datetime, timezone

from aoi_hw_check.integrations.windows_pc.event_log import build_event_log_query


class BuildEventLogQueryTest(unittest.TestCase):
    def test_includes_error_level_and_log_names(self) -> None:
        script = build_event_log_query(24.0, now=datetime(2026, 1, 2, tzinfo=timezone.utc))

        self.assertIn("Level=2", script)
        self.assertIn("LogName='Application','System'", script)
        self.assertIn("Get-WinEvent", script)

    def test_start_time_reflects_lookback_hours(self) -> None:
        now = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)

        script = build_event_log_query(24.0, now=now)

        self.assertIn("2026-01-01T12:00:00", script)

    def test_different_lookback_produces_different_start_time(self) -> None:
        now = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)

        script_1h = build_event_log_query(1.0, now=now)
        script_48h = build_event_log_query(48.0, now=now)

        self.assertIn("2026-01-02T11:00:00", script_1h)
        self.assertIn("2025-12-31T12:00:00", script_48h)


if __name__ == "__main__":
    unittest.main()
