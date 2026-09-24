"""GUI가 쓰는 순수 로직 (tkinter를 import하지 않는다).

판정 결과를 화면에 어떻게 보여줄지 결정하는 부분만 여기 모아, tkinter/디스플레이가
없는 환경(예: 이 저장소의 개발 컨테이너)에서도 단위 테스트로 검증할 수 있게 한다.
실제 위젯 코드는 `aoi_hw_check.gui`에 있다.
"""

from __future__ import annotations

import argparse

from aoi_hw_check.cli import build_parser
from aoi_hw_check.core.models import CheckResult, Verdict

VERDICT_LABEL = {Verdict.PASS: "PASS", Verdict.FAIL: "FAIL", Verdict.NA: "NA"}
VERDICT_COLOR = {Verdict.PASS: "#1a7f37", Verdict.FAIL: "#cf222e", Verdict.NA: "#9a6700"}

DEFAULT_EQUIPMENT_ID = "EQ01"


def build_run_all_args(equipment_id: str) -> argparse.Namespace:
    """GUI에서 사용할 run-all 인자를 만든다.

    run.bat과 동일하게 전 항목 Mock, 예시 기준(`--seed-example-criteria`) 자동
    등록, 설비 단동 최초 구동은 GUI 조작자의 감독 하에 승인된 것으로 본다
    (`--supervised`). 실제 설비 연동(제어/PPMAC/검사 프로그램 TCP 접속, WMI)은
    1차 범위 밖이며, 기본 파서의 나머지 옵션은 전부 기본값(Mock)을 그대로 쓴다.
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
