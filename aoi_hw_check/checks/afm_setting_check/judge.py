from __future__ import annotations

from aoi_hw_check.checks.c_class_scan.constants import DOF_CHECK_ITEM
from aoi_hw_check.checks.c_class_scan.models import ScanResult
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore
from aoi_hw_check.core.thresholds import CriteriaStore

CHECK_ITEM = "AFM Setting 상태 확인"
_DOF_FRACTION = 1 / 3


def run_afm_setting_check(
    scan_result: ScanResult,
    dof_criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """같은 AF Z 데이터에서 Beam Position 추종 오차를 집계해 DOF의 1/3 이내인지 판정한다."""
    deviations: list[FieldMismatch] = []
    notes: list[str] = []
    evaluated = 0

    for subsystem, track in scan_result.af_z_map.tracks.items():
        if not track.samples:
            continue

        max_error = max(abs(s.beam_position_error_um) for s in track.samples)
        dof = dof_criteria_store.get_criteria(DOF_CHECK_ITEM, subsystem)
        if dof is None:
            notes.append(f"{subsystem}: 추종 오차 {max_error:.4f}um — DOF 미등록")
            continue

        evaluated += 1
        allowed = dof.max_value * _DOF_FRACTION
        notes.append(f"{subsystem}: 추종 오차 {max_error:.4f}um / 허용 {allowed:.4f}um (DOF/3)")
        if max_error > allowed:
            deviations.append(
                FieldMismatch(
                    field_path=subsystem,
                    baseline_value=f"<= {allowed:.4f}um (DOF/3)",
                    current_value=round(max_error, 4),
                )
            )

    if evaluated == 0:
        verdict = Verdict.NA
        detail = ("등록된 DOF 기준이 없어 판정 불가 — " + "; ".join(notes)) if notes else "AF Z 트랙 데이터 부족"
    elif deviations:
        verdict = Verdict.FAIL
        detail = f"추종 오차 초과 {len(deviations)}/{evaluated}계통 — " + "; ".join(notes)
    else:
        verdict = Verdict.PASS
        detail = f"전 {evaluated}계통 추종 오차 기준 이내 — " + "; ".join(notes)

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=verdict,
        deviation=deviations,
        detail=detail,
    )
    store.save_result(result)
    return result
