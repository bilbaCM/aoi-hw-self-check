from __future__ import annotations

from aoi_hw_check.core.models import GateStatus

_ORDER = [
    GateStatus.GENERATED,
    GateStatus.TRIAL,
    GateStatus.OPTIMIZED,
    GateStatus.VALIDATED,
    GateStatus.APPLIED,
]


class InvalidGateTransition(ValueError):
    """허용되지 않는 Gate 상태 전이를 시도했을 때 발생한다."""


def transition(current: GateStatus, target: GateStatus) -> GateStatus:
    """current -> target 전이가 유효한지 검증하고 target을 반환한다.

    자동 산출된 보정값·설정값(Criteria)은 GENERATED(최초 산출) -> TRIAL(시험
    적용) -> OPTIMIZED(반복 안정화) -> VALIDATED(기준 충족 확인) ->
    APPLIED(실사용 반영) 순서로만, 한 단계씩만 전진할 수 있다. 역행이나
    단계 건너뛰기는 모두 거부한다.
    """
    current_index = _ORDER.index(current)
    target_index = _ORDER.index(target)
    if target_index != current_index + 1:
        raise InvalidGateTransition(
            f"{current.value} -> {target.value} 전이는 허용되지 않습니다 "
            f"(한 단계씩만 전진 가능: {' -> '.join(s.value for s in _ORDER)})"
        )
    return target


def next_status(current: GateStatus) -> GateStatus | None:
    """current 바로 다음 단계를 반환한다. 이미 마지막 단계(APPLIED)면 None."""
    index = _ORDER.index(current)
    if index + 1 >= len(_ORDER):
        return None
    return _ORDER[index + 1]
