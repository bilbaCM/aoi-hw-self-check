from __future__ import annotations

from dataclasses import dataclass

from aoi_hw_check.checks.afm_setting_check.judge import run_afm_setting_check
from aoi_hw_check.checks.c_class_scan.collector import ScanCollector
from aoi_hw_check.checks.gantry_squareness_check.judge import run_gantry_squareness_check
from aoi_hw_check.checks.optical_focus_check.judge import run_optical_focus_check
from aoi_hw_check.checks.optical_tilt_check.judge import run_optical_tilt_check
from aoi_hw_check.checks.pin_pad_flatness_check.judge import run_pin_pad_flatness_check
from aoi_hw_check.core.models import CheckResult, Verdict
from aoi_hw_check.core.storage import ResultStore
from aoi_hw_check.core.thresholds import CriteriaStore

DEFAULT_MAX_SCAN_ATTEMPTS = 3


@dataclass(frozen=True)
class CClassPipelineOutcome:
    results: list[CheckResult]
    all_passed: bool
    escalated: bool
    detail: str


def run_c_class_pipeline(
    collector: ScanCollector,
    dof_criteria_store: CriteriaStore,
    focus_criteria_store: CriteriaStore,
    flatness_criteria_store: CriteriaStore,
    gantry_criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
    max_scan_attempts: int = DEFAULT_MAX_SCAN_ATTEMPTS,
) -> CClassPipelineOutcome:
    """기준 시료 1회 Scan으로 C분류 5개 항목을 함께 판정한다.

    영상은 설비를 구동해야만 취득되고(Scan 1회 = 셋업 시간) 단독 취득이
    불가능하므로, 재Scan 횟수에 상한을 두어 NG 몇 건으로 셋업 시간이
    무한정 늘어나는 것을 막는다. 상한을 초과하면 이 함수는 Scan 자체를
    다시 시도하지 않고 작업자 개입으로 전환한다(results가 빈 채로 반환됨).
    """
    attempts = store.count_scan_attempts_since_last_pass(equipment_id)
    if attempts >= max_scan_attempts:
        return CClassPipelineOutcome(
            results=[],
            all_passed=False,
            escalated=True,
            detail=(
                f"재Scan {attempts}회 초과 (상한 {max_scan_attempts}회) — "
                "자동 재시도를 중단합니다. 작업자 개입이 필요합니다."
            ),
        )

    scan_result = collector.run_reference_scan()

    results = [
        run_pin_pad_flatness_check(scan_result, flatness_criteria_store, store, equipment_id),
        run_optical_tilt_check(scan_result, dof_criteria_store, store, equipment_id),
        run_afm_setting_check(scan_result, dof_criteria_store, store, equipment_id),
        run_optical_focus_check(scan_result, focus_criteria_store, store, equipment_id),
        run_gantry_squareness_check(scan_result, gantry_criteria_store, store, equipment_id),
    ]

    all_passed = all(r.verdict == Verdict.PASS for r in results)
    store.record_scan_attempt(equipment_id, all_passed)

    ng_count = sum(1 for r in results if r.verdict != Verdict.PASS)
    detail = (
        "전 항목 PASS"
        if all_passed
        else f"NG {ng_count}건 — 작업자 수동 Setting 조치 후 재Scan 필요"
    )
    return CClassPipelineOutcome(
        results=results, all_passed=all_passed, escalated=False, detail=detail
    )
