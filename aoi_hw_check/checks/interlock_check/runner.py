from __future__ import annotations

from abc import ABC, abstractmethod

from aoi_hw_check.checks.interlock_check.models import InterlockSignalEvent


class InterlockTestRunner(ABC):
    """실제 구현은 전후 공정 장비와 연동 신호를 주고받으며 순서·지연을 기록한다."""

    @abstractmethod
    def run_interlock_test(self) -> list[InterlockSignalEvent]: ...


class MockInterlockTestRunner(InterlockTestRunner):
    """실제 연동 신호 연동 전까지 사용하는 Mock 구현체."""

    def __init__(self, events: list[InterlockSignalEvent] | None = None):
        self._events = events or self._default_events()

    def run_interlock_test(self) -> list[InterlockSignalEvent]:
        return self._events

    @staticmethod
    def _default_events() -> list[InterlockSignalEvent]:
        return [
            InterlockSignalEvent("upstream_ready", 1, 120.0, True),
            InterlockSignalEvent("load_request", 2, 80.0, True),
            InterlockSignalEvent("load_complete", 3, 200.0, True),
            InterlockSignalEvent("downstream_ack", 4, 150.0, True),
        ]
