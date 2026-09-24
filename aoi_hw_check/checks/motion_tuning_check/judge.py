from __future__ import annotations

from aoi_hw_check.checks.motion_tuning_check.runner import MotionTuningRunner
from aoi_hw_check.core.models import CheckResult, FieldMismatch, Verdict
from aoi_hw_check.core.storage import ResultStore
from aoi_hw_check.core.thresholds import CriteriaStore

CHECK_ITEM = "모션 Tuning 상태 확인"
_MIN_PEERS_FOR_COMPARISON = 2  # 자기 자신 포함 — 비교 대상 설비가 1대뿐이면 비교 불가


def run_motion_tuning_check(
    runner: MotionTuningRunner,
    criteria_store: CriteriaStore,
    store: ResultStore,
    equipment_id: str,
) -> CheckResult:
    """축 반복 이동으로 위치편차·오버슈트·정착시간을 측정하고, 동종 설비 실측
    이력 중 최량값 대비 편차가 큰 설비를 조치 대상으로 표시한다.

    절대 기준값이 없으므로(3장 2단계), 이 측정값 자체를 baseline_history에
    쌓아 "동종 설비 비교 저장소"로 쓰고, 그 이력에서 계산한 최량값(작을수록
    좋음)을 비교 기준으로 삼는다. 얼마나 벗어나면 FAIL인지의 허용 배수만
    CriteriaStore에서 metric별로 로드한다.
    """
    state = runner.run_tuning_sequence()
    current_snapshot = state.to_flat_dict()
    store.save_baseline(equipment_id, CHECK_ITEM, current_snapshot)

    peer_snapshots = store.list_latest_baselines_by_equipment(CHECK_ITEM)

    deviations: list[FieldMismatch] = []
    evaluated = 0

    for key, value in current_snapshot.items():
        metric = key.split(".", 1)[1]
        peer_values = [snap[key] for snap in peer_snapshots.values() if key in snap]
        if len(peer_values) < _MIN_PEERS_FOR_COMPARISON:
            continue

        best_value = min(peer_values)
        tolerance = criteria_store.get_criteria(CHECK_ITEM, metric)
        if tolerance is None or best_value <= 0:
            continue

        evaluated += 1
        ratio = value / best_value
        if ratio > tolerance.max_value:
            deviations.append(
                FieldMismatch(
                    field_path=key,
                    baseline_value=(
                        f"<= {tolerance.max_value}x 동종 설비 최량값({best_value:.3f})"
                    ),
                    current_value=round(value, 3),
                )
            )

    if evaluated == 0:
        verdict = Verdict.NA
        detail = "동종 설비 비교 데이터(2대 이상) 또는 허용 배수 기준이 부족해 판정 불가"
    elif deviations:
        verdict = Verdict.FAIL
        detail = f"동종 설비 최량값 대비 편차 큰 항목 {len(deviations)}/{evaluated}건"
    else:
        verdict = Verdict.PASS
        detail = f"전 {evaluated}건 동종 설비 최량값 대비 허용 범위 이내"

    result = CheckResult(
        equipment_id=equipment_id,
        check_item=CHECK_ITEM,
        verdict=verdict,
        deviation=deviations,
        detail=detail,
    )
    store.save_result(result)
    return result
