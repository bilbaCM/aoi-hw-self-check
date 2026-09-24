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

CHECK_ITEM = "광학계 Tilt"


def run_optical_tilt_check(
    scan_result: ScanResult,
    dof_criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """AF Z 맵에 평면을 피팅해 계통별 기울기 크기·방향을 산출하고, Tilt로 인한
    초점 이탈(측정 영역 내 높이 변화량)이 광학계 DOF 이내인지 판정한다."""
    deviations: list[FieldMismatch] = []
    notes: list[str] = []
    evaluated = 0

    for subsystem, track in scan_result.af_z_map.tracks.items():
        points = [(s.x_mm, s.y_mm, s.z_um) for s in track.samples]
        if len(points) < 3:
            continue

        a, b, c = fit_plane(points)
        magnitude = tilt_magnitude_deg(a, b)
        direction = tilt_direction_deg(a, b)
        focus_deviation_um = plane_z_range(a, b, c, points)

        dof = dof_criteria_store.get_criteria(DOF_CHECK_ITEM, subsystem)
        if dof is None:
            notes.append(f"{subsystem}: 기울기 {magnitude:.4f}도 (방향 {direction:.1f}도) — DOF 미등록")
            continue

        evaluated += 1
        notes.append(
            f"{subsystem}: 기울기 {magnitude:.4f}도 (방향 {direction:.1f}도), "
            f"초점 이탈 {focus_deviation_um:.3f}um / DOF {dof.max_value}um"
        )
        if focus_deviation_um > dof.max_value:
            deviations.append(
                FieldMismatch(
                    field_path=subsystem,
                    baseline_value=f"<= {dof.max_value}um (DOF)",
                    current_value=round(focus_deviation_um, 3),
                )
            )

    if evaluated == 0:
        verdict = Verdict.NA
        detail = "등록된 DOF 기준이 없어 판정 불가 — " + "; ".join(notes) if notes else "AF Z 트랙 데이터 부족"
    elif deviations:
        verdict = Verdict.FAIL
        detail = f"DOF 이탈 {len(deviations)}/{evaluated}계통 — " + "; ".join(notes)
    else:
        verdict = Verdict.PASS
        detail = f"전 {evaluated}계통 DOF 이내 — " + "; ".join(notes)

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=verdict,
        deviation=deviations,
        detail=detail,
    )
    store.save_result(result)
    return result
