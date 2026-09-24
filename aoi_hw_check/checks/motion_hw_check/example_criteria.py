from __future__ import annotations

from aoi_hw_check.checks.motion_hw_check.judge import CHECK_ITEM
from aoi_hw_check.core.thresholds import CriteriaStore

# 개발/테스트용 예시 값이다. 실제 설비 출하 DATA(벤더 스펙) 확보 전까지는
# 판정에 절대 신뢰하지 말 것 — 실측치 확보 즉시 교체 필요 (TBD).
_EXAMPLE_RANGES: dict[str, tuple[float, float]] = {
    "X.encoder_count": (90000, 110000),
    "X.pwm_duty_percent": (30, 60),
    "X.io_home_sensor": (0, 1),
    "Y.encoder_count": (90000, 110000),
    "Y.pwm_duty_percent": (30, 60),
    "Y.io_home_sensor": (0, 1),
    "Z.encoder_count": (0, 10000),
    "Z.pwm_duty_percent": (0, 30),
    "Z.io_home_sensor": (0, 1),
}


def seed_example_criteria(criteria_store: CriteriaStore) -> None:
    for key, (min_value, max_value) in _EXAMPLE_RANGES.items():
        criteria_store.save_criteria(CHECK_ITEM, key, min_value, max_value)
