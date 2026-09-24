from __future__ import annotations

from typing import Any, Callable

from aoi_hw_check.checks.pc_check.collector import PCStateCollector
from aoi_hw_check.checks.pc_check.models import PCState
from aoi_hw_check.integrations.windows_pc.config import PCCheckConfig
from aoi_hw_check.integrations.windows_pc.event_log import default_count_recent_errors


def create_wmi_client() -> Any:
    """실제 Windows PC에서 wmi.WMI() 인스턴스를 생성한다.

    Windows 전용 (pip install wmi pywin32) — 지연 import라 Windows가 아닌
    환경에서 이 함수를 호출하지 않는 한 나머지 코드의 import는 깨지지 않는다.
    """
    import wmi

    return wmi.WMI()


class WindowsPCStateCollector(PCStateCollector):
    """WMI(및 Get-WinEvent)로 실제 Windows PC 상태를 수집한다.

    wmi_client는 `wmi.WMI()` 인스턴스(또는 같은 인터페이스의 대역 객체)를
    주입받는다 — 이 클래스 자체는 플랫폼에 종속되지 않아 테스트 가능하다.
    communication(PLC/DAFM 등 연결 상태)은 이 클래스의 범위 밖이다 —
    호출자가 collect_communication을 주입해 다른 연동 클라이언트들의
    연결 확인 결과를 채워 넣을 수 있다.
    """

    def __init__(
        self,
        wmi_client: Any,
        config: PCCheckConfig,
        count_recent_errors: Callable[[float], int] = default_count_recent_errors,
        collect_communication: Callable[[], dict[str, Any]] = lambda: {},
    ):
        self._wmi = wmi_client
        self._config = config
        self._count_recent_errors = count_recent_errors
        self._collect_communication = collect_communication

    def collect(self) -> PCState:
        return PCState(
            os=self._collect_os(),
            cpu=self._collect_cpu(),
            memory=self._collect_memory(),
            disk=self._collect_disk(),
            services=self._collect_services(),
            devices=self._collect_devices(),
            communication=self._collect_communication(),
            errors=self._collect_errors(),
        )

    def _collect_os(self) -> dict[str, Any]:
        os_info = self._wmi.Win32_OperatingSystem()[0]
        return {"version": os_info.Caption, "build": os_info.BuildNumber}

    def _collect_cpu(self) -> dict[str, Any]:
        cpu_info = self._wmi.Win32_Processor()[0]
        return {"model": cpu_info.Name, "usage_percent": cpu_info.LoadPercentage}

    def _collect_memory(self) -> dict[str, Any]:
        os_info = self._wmi.Win32_OperatingSystem()[0]
        total_kb = float(os_info.TotalVisibleMemorySize)
        free_kb = float(os_info.FreePhysicalMemory)
        return {
            "total_gb": round(total_kb / (1024 * 1024), 1),
            "used_gb": round((total_kb - free_kb) / (1024 * 1024), 1),
        }

    def _collect_disk(self) -> dict[str, Any]:
        disk: dict[str, Any] = {}
        for drive in self._config.disk_drives:
            entries = self._wmi.Win32_LogicalDisk(DeviceID=drive)
            key = f"{drive.rstrip(':').lower()}_free_gb"
            if not entries:
                disk[key] = None
                continue
            free_bytes = float(entries[0].FreeSpace or 0)
            disk[key] = round(free_bytes / (1024**3), 1)
        return disk

    def _collect_services(self) -> dict[str, Any]:
        services: dict[str, Any] = {}
        for name in self._config.service_names:
            entries = self._wmi.Win32_Service(Name=name)
            services[name] = entries[0].State if entries else "NotFound"
        return services

    def _collect_devices(self) -> dict[str, Any]:
        devices: dict[str, Any] = {}
        for name in self._config.device_names:
            entries = self._wmi.Win32_PnPEntity(Name=name)
            devices[name] = entries[0].Status if entries else "NotFound"
        return devices

    def _collect_errors(self) -> dict[str, Any]:
        count = self._count_recent_errors(self._config.error_log_lookback_hours)
        return {"event_log_errors_24h": count}
