from __future__ import annotations

from aoi_hw_check.checks.c_class_scan.models import ScanResult
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore
from aoi_hw_check.core.thresholds import CriteriaStore

CHECK_ITEM = "Stage PIN·PAD·Sensor 평탄도"
_CRITERIA_KEY = "pin_height_deviation_um"


def run_pin_pad_flatness_check(
    scan_result: ScanResult,
    criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """AF가 기록한 PIN별 높이에서 편차를 산출해 Glass 뜸·기울어짐을 검출한다."""
    heights = scan_result.af_z_map.pin_heights

    if len(heights) < 2:
        result = CheckResult(
            equipment_id=equipment_id,
            check_item=CHECK_ITEM,
            verdict=Verdict.NA,
            deviation=[],
            detail="PIN 높이 데이터 부족 (2개 이상 필요)",
        )
        store.save_result(result)
        return result

    zs = [p.z_um for p in heights]
    deviation_um = max(zs) - min(zs)
    criteria = criteria_store.get_criteria(CHECK_ITEM, _CRITERIA_KEY)

    if criteria is None:
        verdict = Verdict.NA
        detail = f"PIN 간 높이 편차 {deviation_um:.2f}um — 등록된 기준이 없어 판정 불가"
        deviation: list[FieldMismatch] = []
    elif deviation_um > criteria.max_value:
        verdict = Verdict.FAIL
        detail = f"PIN 간 높이 편차 {deviation_um:.2f}um > 기준 {criteria.max_value}um"
        deviation = [
            FieldMismatch(_CRITERIA_KEY, f"<= {criteria.max_value}", round(deviation_um, 3))
        ]
    else:
        verdict = Verdict.PASS
        detail = f"PIN 간 높이 편차 {deviation_um:.2f}um (기준 {criteria.max_value}um 이내)"
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
