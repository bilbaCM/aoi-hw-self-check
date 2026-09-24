from __future__ import annotations

from aoi_hw_check.checks.interlock_check.judge import CHECK_ITEM
from aoi_hw_check.core.thresholds import CriteriaStore

# 개발/테스트용 예시 값 — 실제 "정상 로그 최대치"는 운영 로그 실측 후 등록 필요 (TBD).
_EXAMPLE_MAX_DELAY_MS: dict[str, float] = {
    "upstream_ready.response_delay_ms": 300.0,
    "load_request.response_delay_ms": 300.0,
    "load_complete.response_delay_ms": 300.0,
    "downstream_ack.response_delay_ms": 300.0,
}


def seed_example_criteria(criteria_store: CriteriaStore) -> None:
    for key, max_delay in _EXAMPLE_MAX_DELAY_MS.items():
        criteria_store.save_criteria(CHECK_ITEM, key, 0.0, max_delay)
