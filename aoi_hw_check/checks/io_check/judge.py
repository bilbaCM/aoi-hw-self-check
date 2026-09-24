from __future__ import annotations

from aoi_hw_check.checks.io_check.client import PLCTestModeClient
from aoi_hw_check.checks.io_check.models import IOPoint
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore

CHECK_ITEM = "I/O Check"


def run_io_check(
    client: PLCTestModeClient,
    io_map: list[IOPoint],
    dangerous_io_ids: set[str],
    approved_dangerous_io_ids: set[str],
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """I/O Map을 전수 시험한다. 위험 출력 목록 항목은 작업자 확인(승인) 없이는 시험하지 않는다."""
    mismatches: list[FieldMismatch] = []
    pending: list[str] = []
    tested = 0

    for point in io_map:
        if point.io_id in dangerous_io_ids and point.io_id not in approved_dangerous_io_ids:
            pending.append(point.io_id)
            continue

        observed = client.test_io_point(point.io_id, point.forced_input_value)
        tested += 1
        if observed != point.expected_output_value:
            mismatches.append(
                FieldMismatch(
                    field_path=point.io_id,
                    baseline_value=point.expected_output_value,
                    current_value=observed,
                )
            )

    if mismatches:
        verdict = Verdict.FAIL
        detail = f"응답 불일치 {len(mismatches)}건 / {tested}건 시험"
    elif pending:
        verdict = Verdict.NA
        detail = f"위험 출력 {len(pending)}건 작업자 확인 대기: {', '.join(pending)}"
    elif tested == 0:
        verdict = Verdict.NA
        detail = "시험할 I/O가 없음"
    else:
        verdict = Verdict.PASS
        detail = f"전 I/O {tested}건 응답 일치"

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=verdict,
        deviation=mismatches,
        detail=detail,
    )
    store.save_result(result)
    return result
