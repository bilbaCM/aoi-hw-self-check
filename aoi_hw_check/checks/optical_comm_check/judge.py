from __future__ import annotations

from aoi_hw_check.checks.optical_comm_check.collector import OpticalCommCollector
from aoi_hw_check.checks.optical_comm_check.models import ChannelResponse
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore

CHECK_ITEM = "광학 부품 동작·통신 확인"

# 카메라 Gray 출력은 8bit라 255가 상한이다 — 광량을 계속 올려도 센서가 그 이상
# 표현하지 못해 255에서 눌러붙는(포화) 구간이 생기는데, 이는 고장이 아니라
# 정상 거동이므로 그 구간에서 Gray 값이 늘지 않는 것만으로는 FAIL 처리하지
# 않는다. 다만 포화 구간에서 값이 오히려 줄어드는 건(노이즈/고장) 여전히 FAIL.
_SATURATION_GRAY_VALUE = 255


def evaluate_channel(response: ChannelResponse) -> tuple[Verdict, str]:
    """통신 응답과, 광량 증가에 따른 Gray 단조 증가 여부를 판정한다 (절대 기준 수치 불필요)."""
    if not response.communication_ok:
        return Verdict.FAIL, "통신 응답 없음"

    if len(response.samples) < 2:
        return Verdict.NA, "Gray 응답 샘플 부족 (2점 이상 필요)"

    ordered = sorted(response.samples, key=lambda s: s.light_level)
    for prev, curr in zip(ordered, ordered[1:]):
        if curr.gray_value > prev.gray_value:
            continue
        if prev.gray_value >= _SATURATION_GRAY_VALUE and curr.gray_value >= _SATURATION_GRAY_VALUE:
            continue  # 이미 포화된 상한(255)에 눌러붙은 것 — 정상
        return Verdict.FAIL, (
            f"광량 {prev.light_level}->{curr.light_level} 구간에서 "
            f"Gray 비단조 ({prev.gray_value}->{curr.gray_value})"
        )

    return Verdict.PASS, "광량 증가에 따라 Gray 단조 증가 확인 (포화 구간 제외)"


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
