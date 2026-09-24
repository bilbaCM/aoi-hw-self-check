from __future__ import annotations

from typing import Any

from aoi_hw_check.checks.pc_check.collector import PCStateCollector
from aoi_hw_check.checks.pc_check.models import PCState
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore

CHECK_ITEM = "PC 동작 Check"


def diff_against_baseline(
    current: PCState, baseline: dict[str, Any]
) -> list[FieldMismatch]:
    """현재 상태와 baseline을 필드 단위로 비교해 불일치 항목만 반환한다."""
    current_flat = current.to_flat_dict()
    mismatches = []
    for key in sorted(set(current_flat) | set(baseline)):
        current_value = current_flat.get(key)
        baseline_value = baseline.get(key)
        if current_value != baseline_value:
            mismatches.append(
                FieldMismatch(
                    field_path=key,
                    baseline_value=baseline_value,
                    current_value=current_value,
                )
            )
    return mismatches


def run_pc_check(
    collector: PCStateCollector, store: ResultStore, equipment_id: str
) -> CheckResult:
    """설비의 첫 실행 결과를 baseline으로 저장하고, 이후 실행은 baseline과 diff한다."""
    current = collector.collect()
    baseline = store.get_baseline(equipment_id, CHECK_ITEM)

    if baseline is None:
        store.save_baseline(equipment_id, CHECK_ITEM, current.to_flat_dict())
        result = CheckResult(
            equipment_id=equipment_id,
            check_item=CHECK_ITEM,
            verdict=Verdict.PASS,
            deviation=[],
            detail="최초 실행 — 현재 상태를 baseline으로 저장",
        )
    else:
        mismatches = diff_against_baseline(current, baseline)
        verdict = Verdict.FAIL if mismatches else Verdict.PASS
        detail = f"불일치 {len(mismatches)}건" if mismatches else "baseline과 일치"
        result = CheckResult(
            equipment_id=equipment_id,
            check_item=CHECK_ITEM,
            verdict=verdict,
            deviation=mismatches,
            detail=detail,
        )

    store.save_result(result)
    return result
