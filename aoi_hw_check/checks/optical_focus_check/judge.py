from __future__ import annotations

from aoi_hw_check.checks.c_class_scan.models import ScanResult
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore
from aoi_hw_check.core.thresholds import CriteriaStore

CHECK_ITEM = "광학계 Focus"


def run_optical_focus_check(
    scan_result: ScanResult,
    criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """스캔 영상의 Focus measure를 기준 시료(최초 실행 결과) 대비 비율로 정규화해 판정한다.

    절대값이 아닌 상대 비교이므로, 이 설비의 최초 실행 결과를 기준 시료 값으로
    저장하고(baseline), 이후 실행은 baseline 대비 비율을 CriteriaStore의 허용
    범위와 비교한다.
    """
    measures = scan_result.scan_images.focus_measures
    baseline = store.get_baseline(equipment_id, CHECK_ITEM)

    if baseline is None:
        store.save_baseline(equipment_id, CHECK_ITEM, measures)
        result = CheckResult(
            equipment_id=equipment_id,
            check_item=CHECK_ITEM,
            verdict=Verdict.PASS,
            deviation=[],
            detail="최초 실행 — 현재 Focus measure를 기준 시료 값으로 저장",
        )
        store.save_result(result)
        return result

    deviations: list[FieldMismatch] = []
    notes: list[str] = []
    evaluated = 0

    for subsystem, value in measures.items():
        baseline_value = baseline.get(subsystem)
        if not baseline_value:
            continue

        ratio = value / baseline_value
        criteria = criteria_store.get_criteria(CHECK_ITEM, subsystem)
        if criteria is None:
            notes.append(f"{subsystem}: 비율 {ratio:.3f} — 허용 범위 미등록")
            continue

        evaluated += 1
        notes.append(f"{subsystem}: 비율 {ratio:.3f} (허용 [{criteria.min_value}, {criteria.max_value}])")
        if not (criteria.min_value <= ratio <= criteria.max_value):
            deviations.append(
                FieldMismatch(
                    field_path=subsystem,
                    baseline_value=f"[{criteria.min_value}, {criteria.max_value}]",
                    current_value=round(ratio, 3),
                )
            )

    if evaluated == 0:
        verdict = Verdict.NA
        detail = ("등록된 허용 범위가 없어 판정 불가 — " + "; ".join(notes)) if notes else "Focus measure 데이터 부족"
    elif deviations:
        verdict = Verdict.FAIL
        detail = f"초점 비율 이탈 {len(deviations)}/{evaluated}계통 — " + "; ".join(notes)
    else:
        verdict = Verdict.PASS
        detail = f"전 {evaluated}계통 초점 비율 기준 이내 — " + "; ".join(notes)

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=verdict,
        deviation=deviations,
        detail=detail,
    )
    store.save_result(result)
    return result
