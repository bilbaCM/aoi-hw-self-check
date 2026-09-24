from __future__ import annotations

from typing import Any

from aoi_hw_check.checks.pc_check.collector import PCStateCollector
from aoi_hw_check.checks.pc_check.models import PCState
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore
from aoi_hw_check.core.thresholds import CriteriaStore

CHECK_ITEM = "PC 동작 Check"


def diff_against_baseline(
    current: PCState, baseline: dict[str, Any], criteria_store: CriteriaStore
) -> list[FieldMismatch]:
    """현재 상태를 baseline/기준 범위와 필드 단위로 비교해 불일치 항목만 반환한다.

    CriteriaStore에 범위(min/max)가 등록된 필드(CPU 사용률·메모리 사용량·디스크
    여유공간·최근 이벤트 로그 에러 건수처럼 정상 동작 중에도 계속 변하는 값)는
    baseline과 완전히 같은지가 아니라 등록된 범위 안에 있는지로 판정한다.
    등록되지 않은 필드(OS 버전, 서비스/장치/통신 상태 등)는 기존처럼 baseline과
    완전히 같은지로 판정한다.
    """
    current_flat = current.to_flat_dict()
    mismatches: list[FieldMismatch] = []
    for key in sorted(set(current_flat) | set(baseline)):
        current_value = current_flat.get(key)
        criteria = criteria_store.get_criteria(CHECK_ITEM, key)
        if criteria is not None:
            if not (criteria.min_value <= current_value <= criteria.max_value):
                mismatches.append(
                    FieldMismatch(
                        field_path=key,
                        baseline_value=f"[{criteria.min_value}, {criteria.max_value}]",
                        current_value=current_value,
                    )
                )
            continue

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
    collector: PCStateCollector,
    criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """설비의 첫 실행 결과를 baseline으로 저장하고, 이후 실행은 baseline과 diff한다.

    다만 CriteriaStore에 범위가 등록된 필드는 baseline 여부와 무관하게 항상
    그 범위로 판정한다 — 등록된 기준은 "처음 관측된 값"이 아니라 정해진
    스펙이므로, 최초 실행이라도 그냥 통과시키지 않는다.
    """
    current = collector.collect()
    baseline = store.get_baseline(equipment_id, CHECK_ITEM)
    is_first_run = baseline is None

    if is_first_run:
        store.save_baseline(equipment_id, CHECK_ITEM, current.to_flat_dict())
        # 기준 범위가 없는 필드는 이번 값을 그대로 baseline 삼아 비교에서 제외한다.
        baseline = current.to_flat_dict()

    mismatches = diff_against_baseline(current, baseline, criteria_store)
    verdict = Verdict.FAIL if mismatches else Verdict.PASS

    if mismatches:
        detail = f"불일치/범위 이탈 {len(mismatches)}건"
    elif is_first_run:
        detail = "최초 실행 — 현재 상태를 baseline으로 저장"
    else:
        detail = "baseline·기준 범위 모두 정상"

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=verdict,
        deviation=mismatches,
        detail=detail,
    )

    store.save_result(result)
    return result
