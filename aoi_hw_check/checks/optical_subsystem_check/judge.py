from __future__ import annotations

from aoi_hw_check.checks.c_class_scan.constants import DOF_CHECK_ITEM
from aoi_hw_check.checks.c_class_scan.geometry import (
    fit_plane,
    plane_z_range,
    tilt_direction_deg,
    tilt_magnitude_deg,
)
from aoi_hw_check.checks.c_class_scan.models import ScanResult
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore
from aoi_hw_check.core.thresholds import CriteriaStore


def check_item_name(inspector_id: str) -> str:
    """인스펙터 카메라(설비마다 대수가 다름)별 광학계 상태 확인 항목명 — Focus와 Tilt를 함께 판정한다."""
    return f"{inspector_id} 광학계 상태 확인"


def _evaluate_tilt(
    inspector_id: str, scan_result: ScanResult, dof_criteria_store: CriteriaStore
) -> tuple[Verdict, list[FieldMismatch], str]:
    """AF Z 맵에 평면을 피팅해 기울기 크기·방향을 산출하고, Tilt로 인한 초점
    이탈(측정 영역 내 높이 변화량)이 광학계 DOF 이내인지 판정한다."""
    track = scan_result.af_z_map.tracks.get(inspector_id)
    if track is None or len(track.samples) < 3:
        return Verdict.NA, [], "Tilt: AF Z 트랙 데이터 부족"

    points = [(s.x_mm, s.y_mm, s.z_um) for s in track.samples]
    a, b, c = fit_plane(points)
    magnitude = tilt_magnitude_deg(a, b)
    direction = tilt_direction_deg(a, b)
    focus_deviation_um = plane_z_range(a, b, c, points)
    note = (
        f"Tilt: 기울기 {magnitude:.4f}도(방향 {direction:.1f}도), "
        f"초점 이탈 {focus_deviation_um:.3f}um"
    )

    dof = dof_criteria_store.get_criteria(DOF_CHECK_ITEM, inspector_id)
    if dof is None:
        return Verdict.NA, [], note + " — DOF 미등록"

    note += f" / DOF {dof.max_value}um"
    if focus_deviation_um > dof.max_value:
        deviation = [
            FieldMismatch(
                "tilt_focus_deviation_um",
                f"<= {dof.max_value}um (DOF)",
                round(focus_deviation_um, 3),
            )
        ]
        return Verdict.FAIL, deviation, note
    return Verdict.PASS, [], note


def _evaluate_focus(
    inspector_id: str,
    scan_result: ScanResult,
    focus_criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
    check_item: str,
) -> tuple[Verdict, list[FieldMismatch], str]:
    """스캔 영상의 Focus measure(검사 프로그램이 인스펙터 카메라별로 산출)를 기준
    시료(최초 실행 결과) 대비 비율로 정규화해 판정한다.

    절대값이 아닌 상대 비교이므로, 이 설비/카메라의 최초 실행 결과를 기준
    시료 값으로 저장하고(baseline), 이후 실행은 baseline 대비 비율을
    CriteriaStore의 허용 범위와 비교한다.
    """
    value = scan_result.scan_images.focus_measures.get(inspector_id)
    if value is None:
        return Verdict.NA, [], "Focus: 측정값 없음"

    baseline = store.get_baseline(equipment_id, check_item)
    if baseline is None:
        store.save_baseline(equipment_id, check_item, {"focus_measure": value})
        return Verdict.PASS, [], "Focus: 최초 실행 — 기준 시료 값으로 저장"

    baseline_value = baseline.get("focus_measure")
    if not baseline_value:
        return Verdict.NA, [], "Focus: baseline 값 없음"

    ratio = value / baseline_value
    note = f"Focus: 비율 {ratio:.3f}"
    criteria = focus_criteria_store.get_criteria(check_item, "focus_ratio")
    if criteria is None:
        return Verdict.NA, [], note + " — 허용 범위 미등록"

    note += f" (허용 [{criteria.min_value}, {criteria.max_value}])"
    if not (criteria.min_value <= ratio <= criteria.max_value):
        deviation = [
            FieldMismatch(
                "focus_ratio",
                f"[{criteria.min_value}, {criteria.max_value}]",
                round(ratio, 3),
            )
        ]
        return Verdict.FAIL, deviation, note
    return Verdict.PASS, [], note


def run_optical_subsystem_check(
    inspector_id: str,
    scan_result: ScanResult,
    dof_criteria_store: CriteriaStore,
    focus_criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """인스펙터 카메라 1대(설비마다 대수가 다름)의 Focus·Tilt를 함께 판정해 하나의 결과로 합친다."""
    check_item = check_item_name(inspector_id)

    tilt_verdict, tilt_deviation, tilt_note = _evaluate_tilt(
        inspector_id, scan_result, dof_criteria_store
    )
    focus_verdict, focus_deviation, focus_note = _evaluate_focus(
        inspector_id, scan_result, focus_criteria_store, store, equipment_id, check_item
    )

    sub_verdicts = (tilt_verdict, focus_verdict)
    if Verdict.FAIL in sub_verdicts:
        verdict = Verdict.FAIL
    elif Verdict.NA in sub_verdicts:
        verdict = Verdict.NA
    else:
        verdict = Verdict.PASS

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=check_item,
        verdict=verdict,
        deviation=tilt_deviation + focus_deviation,
        detail=f"{tilt_note}; {focus_note}",
    )
    store.save_result(result)
    return result
