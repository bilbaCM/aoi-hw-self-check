from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_CATEGORIES = (
    "os",
    "cpu",
    "memory",
    "disk",
    "services",
    "devices",
    "communication",
    "errors",
)


@dataclass(frozen=True)
class PCState:
    """PC 동작 Check가 수집하는 항목: OS·CPU·메모리·디스크·서비스·장치·통신·오류."""

    os: dict[str, Any] = field(default_factory=dict)
    cpu: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    disk: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)
    devices: dict[str, Any] = field(default_factory=dict)
    communication: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, Any] = field(default_factory=dict)

    def to_flat_dict(self) -> dict[str, Any]:
        """"category.key" 형태의 평탄화된 dict로 변환한다 (baseline diff에 사용)."""
        flat: dict[str, Any] = {}
        for category in _CATEGORIES:
            for key, value in getattr(self, category).items():
                flat[f"{category}.{key}"] = value
        return flat
