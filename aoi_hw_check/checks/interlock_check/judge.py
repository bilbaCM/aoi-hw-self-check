from __future__ import annotations

from aoi_hw_check.checks.interlock_check.runner import InterlockTestRunner
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore
from aoi_hw_check.core.thresholds import CriteriaStore

CHECK_ITEM = "설비 연동 동작 Test"


def run_interlock_check(
    runner: InterlockTestRunner,
    expected_sequence: list[str],
    criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """연동 신호 수수·순서를 시험하고, 응답 지연을 정상 로그 최대치와 비교한다."""
    events = runner.run_interlock_test()
    by_id = {event.signal_id: event for event in events}

    deviations: list[FieldMismatch] = []

    for signal_id in expected_sequence:
        event = by_id.get(signal_id)
        if event is None or not event.received:
            deviations.append(FieldMismatch(signal_id, "신호 수신", "미수신"))

    observed_order = [
        e.signal_id for e in sorted(events, key=lambda e: e.sequence_order) if e.received
    ]
    expected_received_order = [
        signal_id
        for signal_id in expected_sequence
        if by_id.get(signal_id) and by_id[signal_id].received
    ]
    if observed_order != expected_received_order:
        deviations.append(
            FieldMismatch("sequence_order", expected_received_order, observed_order)
        )

    for event in events:
        if not event.received:
            continue
        criteria = criteria_store.get_criteria(
            CHECK_ITEM, f"{event.signal_id}.response_delay_ms"
        )
        if criteria is None or event.response_delay_ms <= criteria.max_value:
            continue
        deviations.append(
            FieldMismatch(
                field_path=f"{event.signal_id}.response_delay_ms",
                baseline_value=f"<= {criteria.max_value}",
                current_value=event.response_delay_ms,
            )
        )

    verdict = Verdict.FAIL if deviations else Verdict.PASS
    detail = f"이탈 {len(deviations)}건" if deviations else "신호 수수·순서·지연 모두 정상"

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=verdict,
        deviation=deviations,
        detail=detail,
    )
    store.save_result(result)
    return result
