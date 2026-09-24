"""GUI가 쓰는 순수 로직 (tkinter를 import하지 않는다).

판정 결과를 화면에 어떻게 보여줄지 결정하는 부분만 여기 모아, tkinter/디스플레이가
없는 환경(예: 이 저장소의 개발 컨테이너)에서도 단위 테스트로 검증할 수 있게 한다.
실제 위젯 코드는 `aoi_hw_check.gui`에 있다.
"""

from __future__ import annotations

import argparse

from aoi_hw_check.cli import (
    C_CLASS_SCAN_KEY,
    C_CLASS_SCAN_LABEL,
    CHECK_ITEM_SPECS,
    build_parser,
    list_all_criteria,
)
from aoi_hw_check.core.gate import next_status
from aoi_hw_check.core.models import CheckResult, GateStatus, Verdict
from aoi_hw_check.core.thresholds import Criteria, JSONCriteriaStore

VERDICT_LABEL = {Verdict.PASS: "PASS", Verdict.FAIL: "FAIL", Verdict.NA: "NA"}
VERDICT_COLOR = {Verdict.PASS: "#1a7f37", Verdict.FAIL: "#cf222e", Verdict.NA: "#9a6700"}

DEFAULT_EQUIPMENT_ID = "EQ01"

# 체크박스 목록에 쓰는 (선택 key, 화면 표시 이름) 순서쌍 — 13개 항목 중 C분류
# 6항목은 기준 시료 1회 Scan을 공유해 나눌 수 없으므로 한 단위로 선택한다.
SELECTABLE_ITEMS: list[tuple[str, str]] = [
    (key, label) for key, label, _execute_fn in CHECK_ITEM_SPECS
] + [(C_CLASS_SCAN_KEY, C_CLASS_SCAN_LABEL)]


def build_run_all_args(equipment_id: str) -> argparse.Namespace:
    """GUI에서 사용할 run-all 인자를 만든다 (전체 실행/선택 실행 공용).

    run-all의 전체 인자 집합을 그대로 만들어 두면 `cli.execute_run_all`과
    `cli.execute_selected` 모두에 넘길 수 있다 — 실행할 항목은 args가 아니라
    호출하는 쪽에서 고르는 key 집합으로 정해진다. run.bat과 동일하게 전 항목
    Mock, 예시 기준(`--seed-example-criteria`) 자동 등록, 설비 단동 최초 구동은
    GUI 조작자의 감독 하에 승인된 것으로 본다(`--supervised`). 실제 설비 연동
    (제어/PPMAC/검사 프로그램 TCP 접속, WMI)은 1차 범위 밖이며, 기본 파서의
    나머지 옵션은 전부 기본값(Mock)을 그대로 쓴다.
    """
    return build_parser().parse_args(
        [
            "run-all",
            "--equipment-id",
            equipment_id,
            "--seed-example-criteria",
            "--supervised",
        ]
    )


def format_detail_cell(result: CheckResult) -> str:
    """표의 "상세" 칸에 넣을 문자열. 편차(deviation)가 있으면 뒤에 이어붙인다."""
    if not result.deviation:
        return result.detail
    mismatches = "; ".join(
        f"{m.field_path}: baseline={m.baseline_value}→current={m.current_value}"
        for m in result.deviation
    )
    return f"{result.detail}  ⚠ {mismatches}"


def format_action_items(equipment_id: str, action_items: list[CheckResult]) -> str:
    if not action_items:
        return f"{equipment_id}: 조치 대상 없음 — 셋업 착수 가능"
    lines = [f"{equipment_id} 조치 대상 목록 ({len(action_items)}건)"]
    for item in action_items:
        lines.append(f"  [{item.verdict.value}] {item.check_item}: {item.detail}")
    return "\n".join(lines)


GATE_COLUMNS = ("store", "check_item", "key", "version", "range", "gate_status", "updated_at")


def list_criteria_rows() -> list[tuple[str, Criteria]]:
    """Gate 관리 화면 표에 넣을 목록. (기준 파일 경로, 최신 기준) 순서쌍을
    항목/key 순으로 정렬해서 반환한다."""
    return sorted(list_all_criteria(), key=lambda row: (row[1].check_item, row[1].key))


def format_criteria_row(store_path: str, criteria: Criteria) -> tuple[str, str, str, str, str, str, str]:
    return (
        store_path,
        criteria.check_item,
        criteria.key,
        str(criteria.version),
        f"{criteria.min_value} ~ {criteria.max_value}",
        criteria.gate_status.value,
        criteria.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
    )


def advance_criteria_gate(store_path: str, check_item: str, key: str, target: GateStatus) -> Criteria:
    """지정한 기준 파일에서 해당 기준의 Gate를 target 단계로 전진시킨다."""
    return JSONCriteriaStore(store_path).advance_criteria_gate(check_item, key, target)


def parse_min_max(min_text: str, max_text: str) -> tuple[float, float]:
    """입력 문자열을 (min_value, max_value)로 검증·변환한다.

    숫자가 아니거나 최소값이 최대값보다 작지 않으면 사용자에게 그대로 보여줄
    수 있는 한국어 메시지로 ValueError를 낸다.
    """
    try:
        min_value = float(min_text)
        max_value = float(max_text)
    except ValueError as exc:
        raise ValueError("최소값/최대값은 숫자여야 합니다.") from exc
    if min_value >= max_value:
        raise ValueError("최소값은 최대값보다 작아야 합니다.")
    return min_value, max_value


def save_criteria_value(
    store_path: str, check_item: str, key: str, min_value: float, max_value: float
) -> Criteria:
    """기준값을 새 버전으로 등록한다 (GENERATED 상태로 시작).

    core/thresholds.py의 설계대로, 값이 바뀌면 기존 Gate 단계는 유지되지 않고
    처음부터 다시 검증을 거쳐야 한다 — 여기서도 그 원칙을 그대로 따른다.
    """
    return JSONCriteriaStore(store_path).save_criteria(check_item, key, min_value, max_value)
