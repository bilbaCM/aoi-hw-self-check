from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aoi_hw_check.core.gate import transition
from aoi_hw_check.core.models import GateStatus


@dataclass(frozen=True)
class Criteria:
    check_item: str
    key: str
    version: int
    min_value: float
    max_value: float
    updated_at: datetime
    gate_status: GateStatus = GateStatus.GENERATED


class CriteriaStore(ABC):
    """판정 임계값 저장소. 값은 코드에 하드코딩하지 않고 여기서 로드하며, 버전 이력을 남긴다.

    각 기준(버전)은 Gate 상태(GENERATED -> TRIAL -> OPTIMIZED -> VALIDATED ->
    APPLIED)를 필드로 가진다 — 새로 산출된 값을 곧바로 실사용에 반영하지 않고
    단계를 밟아 검증하기 위함이다 (4장).
    """

    @abstractmethod
    def get_criteria(self, check_item: str, key: str) -> Criteria | None:
        """가장 최근 버전의 기준을 반환한다. 등록되지 않았으면 None."""

    @abstractmethod
    def save_criteria(
        self, check_item: str, key: str, min_value: float, max_value: float
    ) -> Criteria:
        """새 버전의 기준을 GENERATED 상태로 등록한다 (기존 이력은 유지)."""

    @abstractmethod
    def list_criteria_history(self, check_item: str, key: str) -> list[Criteria]: ...

    @abstractmethod
    def advance_criteria_gate(
        self, check_item: str, key: str, target_status: GateStatus
    ) -> Criteria:
        """가장 최근 버전의 Gate 상태를 target_status로 한 단계 전진시킨다.

        값(min/max)은 그대로 두고 성숙도만 바꾸는 것이므로 새 버전을
        만들지 않고 최신 버전의 gate_status를 갱신한다. 역행·단계
        건너뛰기는 InvalidGateTransition으로 거부된다.
        """


class JSONCriteriaStore(CriteriaStore):
    """설정 파일(JSON) 기반 임계값 저장소. 엔지니어가 직접 값을 확인·수정할 수 있다."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _record_key(check_item: str, key: str) -> str:
        return f"{check_item}::{key}"

    def get_criteria(self, check_item: str, key: str) -> Criteria | None:
        history = self._load().get(self._record_key(check_item, key), [])
        if not history:
            return None
        return self._to_criteria(check_item, key, history[-1])

    def save_criteria(
        self, check_item: str, key: str, min_value: float, max_value: float
    ) -> Criteria:
        data = self._load()
        record_key = self._record_key(check_item, key)
        history = data.setdefault(record_key, [])
        entry = {
            "version": len(history) + 1,
            "min_value": min_value,
            "max_value": max_value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "gate_status": GateStatus.GENERATED.value,
        }
        history.append(entry)
        self._save(data)
        return self._to_criteria(check_item, key, entry)

    def list_criteria_history(self, check_item: str, key: str) -> list[Criteria]:
        history = self._load().get(self._record_key(check_item, key), [])
        return [self._to_criteria(check_item, key, entry) for entry in history]

    def advance_criteria_gate(
        self, check_item: str, key: str, target_status: GateStatus
    ) -> Criteria:
        data = self._load()
        record_key = self._record_key(check_item, key)
        history = data.get(record_key)
        if not history:
            raise KeyError(f"등록된 기준이 없습니다: {check_item} / {key}")

        latest = history[-1]
        current_status = GateStatus(latest.get("gate_status", GateStatus.GENERATED.value))
        latest["gate_status"] = transition(current_status, target_status).value
        self._save(data)
        return self._to_criteria(check_item, key, latest)

    @staticmethod
    def _to_criteria(check_item: str, key: str, entry: dict) -> Criteria:
        return Criteria(
            check_item=check_item,
            key=key,
            version=entry["version"],
            min_value=entry["min_value"],
            max_value=entry["max_value"],
            updated_at=datetime.fromisoformat(entry["updated_at"]),
            gate_status=GateStatus(entry.get("gate_status", GateStatus.GENERATED.value)),
        )
