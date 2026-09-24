from __future__ import annotations

from aoi_hw_check.checks.optical_comm_check.collector import OpticalCommCollector
from aoi_hw_check.checks.optical_comm_check.models import ChannelResponse
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore

CHECK_ITEM = "광학 부품 동작·통신 확인"


def evaluate_channel(response: ChannelResponse) -> tuple[Verdict, str]:
    """통신 응답과, 광량 증가에 따른 Gray 단조 증가 여부를 판정한다 (절대 기준 수치 불필요).

    주의: 카메라 Gray 값이 상한(예: 8bit=255)에서 포화되는 구간은 현재
    비단조로 간주되어 FAIL 처리된다 — 실제 센서 포화 거동 확인 후 허용
    범위를 추가할지 결정 필요 (TBD).
    """
    if not response.communication_ok:
        return Verdict.FAIL, "통신 응답 없음"

    if len(response.samples) < 2:
        return Verdict.NA, "Gray 응답 샘플 부족 (2점 이상 필요)"

    ordered = sorted(response.samples, key=lambda s: s.light_level)
    for prev, curr in zip(ordered, ordered[1:]):
        if curr.gray_value <= prev.gray_value:
            return Verdict.FAIL, (
                f"광량 {prev.light_level}->{curr.light_level} 구간에서 "
                f"Gray 비단조 ({prev.gray_value}->{curr.gray_value})"
            )

    return Verdict.PASS, "광량 증가에 따라 Gray 단조 증가 확인"


def run_optical_comm_check(
    collector: OpticalCommCollector, store: ResultStore, equipment_id: str
) -> CheckResult:
    state = collector.collect()

    deviations: list[FieldMismatch] = []
    verdicts: list[Verdict] = []
    for channel_id, response in state.channels.items():
        verdict, note = evaluate_channel(response)
        verdicts.append(verdict)
        if verdict == Verdict.FAIL:
            deviations.append(
                FieldMismatch(
                    field_path=channel_id,
                    baseline_value="광량 증가 시 Gray 단조 증가 + 통신 응답",
                    current_value=note,
                )
            )

    if not verdicts:
        overall = Verdict.NA
        detail = "채널 없음"
    elif Verdict.FAIL in verdicts:
        overall = Verdict.FAIL
        detail = f"이탈 채널 {len(deviations)}/{len(verdicts)}건"
    elif all(v == Verdict.NA for v in verdicts):
        overall = Verdict.NA
        detail = "전 채널 판정 불가 (샘플 부족)"
    else:
        overall = Verdict.PASS
        detail = f"전 채널 {len(verdicts)}건 정상 (광량-Gray 단조 증가, 통신 정상)"

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=overall,
        deviation=deviations,
        detail=detail,
    )
    store.save_result(result)
    return result
