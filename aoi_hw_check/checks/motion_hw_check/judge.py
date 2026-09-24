from __future__ import annotations

from aoi_hw_check.checks.motion_hw_check.collector import MotionHWCollector
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore
from aoi_hw_check.core.thresholds import CriteriaStore

CHECK_ITEM = "모션 H/W Check"


def run_motion_hw_check(
    collector: MotionHWCollector,
    criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """전 축의 Encoder/PWM/I/O 값을 기준 범위(출하 DATA)와 비교해 이탈 축을 검출한다.

    해당 축.필드에 등록된 기준이 없으면 그 필드는 판정에서 제외한다 — 등록된
    기준이 하나도 없으면 NA, 하나라도 범위를 벗어나면 FAIL로 판정한다.
    """
    state = collector.collect()

    checked = 0
    out_of_range: list[FieldMismatch] = []
    for key, value in state.to_flat_dict().items():
        criteria = criteria_store.get_criteria(CHECK_ITEM, key)
        if criteria is None:
            continue
        checked += 1
        if not (criteria.min_value <= value <= criteria.max_value):
            out_of_range.append(
                FieldMismatch(
                    field_path=key,
                    baseline_value=f"[{criteria.min_value}, {criteria.max_value}]",
                    current_value=value,
                )
            )

    if checked == 0:
        verdict = Verdict.NA
        detail = "등록된 기준 범위가 없어 판정 불가 — CriteriaStore에 축별 기준 등록 필요"
    elif out_of_range:
        verdict = Verdict.FAIL
        detail = f"범위 이탈 {len(out_of_range)}건 / {checked}건 판정"
    else:
        verdict = Verdict.PASS
        detail = f"전 축 {checked}건 기준 범위 이내"

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=verdict,
        deviation=out_of_range,
        detail=detail,
    )
    store.save_result(result)
    return result
