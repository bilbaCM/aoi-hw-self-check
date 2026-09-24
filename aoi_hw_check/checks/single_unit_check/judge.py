from __future__ import annotations

from aoi_hw_check.checks.single_unit_check.runner import SingleUnitSequenceRunner
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore

CHECK_ITEM = "설비 단동 동작 확인"


def run_single_unit_check(
    runner: SingleUnitSequenceRunner,
    store: ResultStore,
    equipment_id: str,
    supervised: bool = False,
) -> CheckResult:
    """안전 인터락 시험 시퀀스를 구동한다. 설비의 최초 구동은 작업자 감독이 필수다.

    해당 설비에 이 항목의 실행 이력이 없으면(=최초 구동) supervised=True로
    명시적으로 승인된 경우에만 시퀀스를 구동한다.
    """
    is_first_run = len(store.list_results(equipment_id, CHECK_ITEM)) == 0
    if is_first_run and not supervised:
        result = CheckResult(
            equipment_id=equipment_id,
            check_item=CHECK_ITEM,
            verdict=Verdict.NA,
            deviation=[],
            detail="최초 구동 — 작업자 감독 하에 승인(supervised=True) 후 실행 필요",
        )
        store.save_result(result)
        return result

    steps = runner.run_sequence()
    deviation = [
        FieldMismatch(
            field_path=step.step_id,
            baseline_value="정상 완료",
            current_value="이상 정지" if step.abnormal_stop else "미완료",
        )
        for step in steps
        if step.abnormal_stop or not step.completed
    ]

    verdict = Verdict.FAIL if deviation else Verdict.PASS
    detail = (
        f"이상 {len(deviation)}건 / {len(steps)}스텝"
        if deviation
        else f"전 {len(steps)}스텝 완주, 이상 정지 없음"
    )

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=verdict,
        deviation=deviation,
        detail=detail,
    )
    store.save_result(result)
    return result
