from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aoi_hw_check.integrations.windows_pc.collector import WindowsPCStateCollector
from aoi_hw_check.integrations.windows_pc.config import PCCheckConfig, load_pc_check_config


class _Entry:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeWMIClient:
    def __init__(self, os_entry, cpu_entry, disks: dict, services: dict, devices: dict):
        self._os_entry = os_entry
        self._cpu_entry = cpu_entry
        self._disks = disks
        self._services = services
        self._devices = devices

    def Win32_OperatingSystem(self):
        return [self._os_entry]

    def Win32_Processor(self):
        return [self._cpu_entry]

    def Win32_LogicalDisk(self, DeviceID):
        entry = self._disks.get(DeviceID)
        return [entry] if entry else []

    def Win32_Service(self, Name):
        entry = self._services.get(Name)
        return [entry] if entry else []

    def Win32_PnPEntity(self, Name):
        entry = self._devices.get(Name)
        return [entry] if entry else []


def _default_wmi_client() -> _FakeWMIClient:
    return _FakeWMIClient(
        os_entry=_Entry(
            Caption="Windows 10 Enterprise",
            BuildNumber="19045",
            TotalVisibleMemorySize=32 * 1024 * 1024,
            FreePhysicalMemory=23 * 1024 * 1024,
        ),
        cpu_entry=_Entry(Name="Intel i7-9700", LoadPercentage=12),
        disks={
            "C:": _Entry(FreeSpace=210 * 1024**3),
            "D:": _Entry(FreeSpace=480 * 1024**3),
        },
        services={"AOI_VisionService": _Entry(State="Running")},
        devices={"frame_grabber_1": _Entry(Status="OK")},
    )


def _default_config() -> PCCheckConfig:
    return PCCheckConfig(
        service_names=["AOI_VisionService", "AOI_MotionService"],
        disk_drives=["C:", "D:"],
        device_names=["frame_grabber_1", "io_board_1"],
        error_log_lookback_hours=24.0,
    )


class WindowsPCStateCollectorTest(unittest.TestCase):
    def test_collects_os_and_cpu(self) -> None:
        collector = WindowsPCStateCollector(
            _default_wmi_client(), _default_config(), count_recent_errors=lambda h: 0
        )

        state = collector.collect()

        self.assertEqual(state.os, {"version": "Windows 10 Enterprise", "build": "19045"})
        self.assertEqual(state.cpu, {"model": "Intel i7-9700", "usage_percent": 12})

    def test_disk_free_space_converted_to_gb(self) -> None:
        collector = WindowsPCStateCollector(
            _default_wmi_client(), _default_config(), count_recent_errors=lambda h: 0
        )

        state = collector.collect()

        self.assertEqual(state.disk["c_free_gb"], 210.0)
        self.assertEqual(state.disk["d_free_gb"], 480.0)

    def test_missing_service_reports_not_found(self) -> None:
        collector = WindowsPCStateCollector(
            _default_wmi_client(), _default_config(), count_recent_errors=lambda h: 0
        )

        state = collector.collect()

        self.assertEqual(state.services["AOI_VisionService"], "Running")
        self.assertEqual(state.services["AOI_MotionService"], "NotFound")

    def test_missing_device_reports_not_found(self) -> None:
        collector = WindowsPCStateCollector(
            _default_wmi_client(), _default_config(), count_recent_errors=lambda h: 0
        )

        state = collector.collect()

        self.assertEqual(state.devices["frame_grabber_1"], "OK")
        self.assertEqual(state.devices["io_board_1"], "NotFound")

    def test_error_count_uses_injected_callable_with_configured_lookback(self) -> None:
        received_hours: list[float] = []

        def fake_count(hours: float) -> int:
            received_hours.append(hours)
            return 3

        collector = WindowsPCStateCollector(
            _default_wmi_client(), _default_config(), count_recent_errors=fake_count
        )

        state = collector.collect()

        self.assertEqual(state.errors, {"event_log_errors_24h": 3})
        self.assertEqual(received_hours, [24.0])

    def test_communication_defaults_to_empty_and_can_be_injected(self) -> None:
        default_collector = WindowsPCStateCollector(
            _default_wmi_client(), _default_config(), count_recent_errors=lambda h: 0
        )
        self.assertEqual(default_collector.collect().communication, {})

        injected_collector = WindowsPCStateCollector(
            _default_wmi_client(),
            _default_config(),
            count_recent_errors=lambda h: 0,
            collect_communication=lambda: {"plc_link": "Connected"},
        )
        self.assertEqual(
            injected_collector.collect().communication, {"plc_link": "Connected"}
        )

    def test_memory_computed_from_total_and_free_kb(self) -> None:
        client = _FakeWMIClient(
            os_entry=_Entry(
                Caption="Windows 10",
                BuildNumber="19045",
                TotalVisibleMemorySize=32 * 1024 * 1024,
                FreePhysicalMemory=23 * 1024 * 1024,
            ),
            cpu_entry=_Entry(Name="CPU", LoadPercentage=0),
            disks={},
            services={},
            devices={},
        )
        collector = WindowsPCStateCollector(
            client, PCCheckConfig(), count_recent_errors=lambda h: 0
        )

        state = collector.collect()

        self.assertEqual(state.memory, {"total_gb": 32.0, "used_gb": 9.0})


class LoadPCCheckConfigTest(unittest.TestCase):
    def test_loads_config_from_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            path.write_text(
                """
                {
                  "service_names": ["svc1"],
                  "disk_drives": ["C:"],
                  "device_names": ["dev1"],
                  "error_log_lookback_hours": 12
                }
                """,
                encoding="utf-8",
            )

            config = load_pc_check_config(path)

            self.assertEqual(config.service_names, ["svc1"])
            self.assertEqual(config.error_log_lookback_hours, 12)

    def test_example_config_file_loads(self) -> None:
        example_path = (
            Path(__file__).resolve().parent.parent
            / "config"
            / "windows_pc_check.example.json"
        )

        config = load_pc_check_config(example_path)

        self.assertIn("frame_grabber_1", config.device_names)


if __name__ == "__main__":
    unittest.main()
