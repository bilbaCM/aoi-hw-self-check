from __future__ import annotations

from aoi_hw_check.core.models import CheckResult, Verdict
from aoi_hw_check.core.storage import ResultStore

_ACTION_REQUIRED_VERDICTS = {Verdict.FAIL, Verdict.NA}


def build_action_item_list(store: ResultStore, equipment_id: str) -> list[CheckResult]:
    """셋업 착수 전 조치 대상 목록을 만든다.

    설비의 각 판정 항목별 가장 최근 결과 중 FAIL(조치 필요) 또는
    NA(판정 불가 — 기준 미등록, 작업자 승인 대기 등)인 것만 모은다.
    """
    latest = store.get_latest_results(equipment_id)
    action_items = [
        result for result in latest.values() if result.verdict in _ACTION_REQUIRED_VERDICTS
    ]
    return sorted(action_items, key=lambda result: result.check_item)
