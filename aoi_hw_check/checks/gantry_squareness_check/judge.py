from __future__ import annotations

from aoi_hw_check.checks.c_class_scan.geometry import (
    angle_between_directions_deg,
    fit_line_direction_deg,
)
from aoi_hw_check.checks.c_class_scan.models import ScanResult
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore
from aoi_hw_check.core.thresholds import CriteriaStore

CHECK_ITEM = "계측 Y축 Gantry 직각도"
_CRITERIA_KEY = "perpendicularity_deviation_deg"
_MIN_POINTS_PER_AXIS = 3  # 2점 측정 금지 — 구간 직진도 오차를 직각도로 오인하는 것을 방지


def run_gantry_squareness_check(
    scan_result: ScanResult,
    criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """X·Y 구동 중 다점 취득한 Cell 패턴 좌표에 각각 최소자승 직선을 피팅해
    두 직선의 사잇각을 구하고, 90도로부터의 편차를 계측 요구정밀도와 비교한다."""
    x_samples = scan_result.scan_images.gantry_x_axis_samples
    y_samples = scan_result.scan_images.gantry_y_axis_samples

    if len(x_samples) < _MIN_POINTS_PER_AXIS or len(y_samples) < _MIN_POINTS_PER_AXIS:
        result = CheckResult(
            equipment_id=equipment_id,
            check_item=CHECK_ITEM,
            verdict=Verdict.NA,
            deviation=[],
            detail=(
                f"축당 최소 {_MIN_POINTS_PER_AXIS}점 이상 필요 (2점 측정 금지 — "
                "구간 직진도 오차를 직각도로 오인할 수 있음)"
            ),
        )
        store.save_result(result)
        return result

    theta_x = fit_line_direction_deg([(s.x_um, s.y_um) for s in x_samples])
    theta_y = fit_line_direction_deg([(s.x_um, s.y_um) for s in y_samples])
    angle = angle_between_directions_deg(theta_x, theta_y)
    deviation_deg = abs(angle - 90.0)

    criteria = criteria_store.get_criteria(CHECK_ITEM, _CRITERIA_KEY)

    if criteria is None:
        verdict = Verdict.NA
        detail = f"사잇각 {angle:.4f}도 (90도 대비 편차 {deviation_deg:.4f}도) — 등록된 기준 없어 판정 불가"
        deviation: list[FieldMismatch] = []
    elif deviation_deg > criteria.max_value:
        verdict = Verdict.FAIL
        detail = f"직각도 편차 {deviation_deg:.4f}도 > 계측 요구정밀도 {criteria.max_value}도"
        deviation = [
            FieldMismatch(
                _CRITERIA_KEY, f"<= {criteria.max_value}", round(deviation_deg, 4)
            )
        ]
    else:
        verdict = Verdict.PASS
        detail = f"직각도 편차 {deviation_deg:.4f}도 (계측 요구정밀도 {criteria.max_value}도 이내)"
        deviation = []

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=verdict,
        deviation=deviation,
        detail=detail,
    )
    store.save_result(result)
    return result
