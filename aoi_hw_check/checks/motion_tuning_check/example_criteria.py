from __future__ import annotations

from aoi_hw_check.checks.motion_tuning_check.judge import CHECK_ITEM
from aoi_hw_check.core.thresholds import CriteriaStore

# 개발/테스트용 예시 값 — "동종 설비 최량값 대비 허용 배수"는 절대 기준이
# 없으므로(3장), 동종 설비 실측 분포가 충분히 쌓인 뒤 통계적으로(예: 최량값
# 분포의 평균+2표준편차) 재산정 필요 (TBD, 2단계 실측 범위 설정).
_EXAMPLE_TOLERANCE_RATIO: dict[str, float] = {
    "position_deviation_um": 1.5,
    "overshoot_percent": 1.5,
    "settling_time_ms": 1.5,
}


def seed_example_criteria(criteria_store: CriteriaStore) -> None:
    for metric, ratio in _EXAMPLE_TOLERANCE_RATIO.items():
        criteria_store.save_criteria(CHECK_ITEM, metric, 1.0, ratio)
