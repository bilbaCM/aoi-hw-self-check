"""GUI가 쓰는 순수 로직 (tkinter를 import하지 않는다).

판정 결과를 화면에 어떻게 보여줄지 결정하는 부분만 여기 모아, tkinter/디스플레이가
없는 환경(예: 이 저장소의 개발 컨테이너)에서도 단위 테스트로 검증할 수 있게 한다.
실제 위젯 코드는 `aoi_hw_check.gui`에 있다.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass

from aoi_hw_check.checks.io_check.client import DEFAULT_IO_MAP
from aoi_hw_check.checks.io_check.danger_list import load_dangerous_io_ids
from aoi_hw_check.checks.io_check.models import IOPoint
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


def build_run_all_args(
    equipment_id: str,
    *,
    control_program_host: str | None = None,
    control_program_port: int | None = None,
    ppmac_host: str | None = None,
    ppmac_port: int = 1025,
    inspection_program_host: str | None = None,
    inspection_program_port: int | None = None,
    use_wmi: bool = False,
    approve_dangerous: str = "",
) -> argparse.Namespace:
    """GUI에서 사용할 run-all 인자를 만든다 (전체 실행/선택 실행 공용).

    run-all의 전체 인자 집합을 그대로 만들어 두면 `cli.execute_run_all`과
    `cli.execute_selected` 모두에 넘길 수 있다 — 실행할 항목은 args가 아니라
    호출하는 쪽에서 고르는 key 집합으로 정해진다. run.bat과 동일하게 예시
    기준(`--seed-example-criteria`) 자동 등록, 설비 단동 최초 구동은 GUI
    조작자의 감독 하에 승인된 것으로 본다(`--supervised`).

    호스트를 지정한 항목만 실제 연동(CLI의 --control-program-host 등과 동일한
    규칙 — 제어/검사 프로그램은 host+port가 모두 있어야 실제 연동, PPMAC은
    host만 있으면 됨)을 쓰고, 나머지는 Mock으로 실행된다. 인자 없이 부르면
    이전과 동일하게 전부 Mock이다. 입력값(숫자 여부, host/port 짝) 검증은
    `build_connected_run_all_args`가 미리 한다 — 이 함수는 이미 검증된 값을
    받는다고 가정한다.

    approve_dangerous는 CLI의 --approve-dangerous와 동일하게 콤마로 구분한
    io_id 목록 — 작업자가 확인·승인한 위험 출력만 I/O Check가 시험한다.
    """
    argv = [
        "run-all",
        "--equipment-id",
        equipment_id,
        "--seed-example-criteria",
        "--supervised",
    ]
    if control_program_host and control_program_port:
        argv += [
            "--control-program-host",
            control_program_host,
            "--control-program-port",
            str(control_program_port),
        ]
    if ppmac_host:
        argv += ["--ppmac-host", ppmac_host, "--ppmac-port", str(ppmac_port)]
    if inspection_program_host and inspection_program_port:
        argv += [
            "--inspection-program-host",
            inspection_program_host,
            "--inspection-program-port",
            str(inspection_program_port),
        ]
    if use_wmi:
        argv.append("--use-wmi")
    if approve_dangerous:
        argv += ["--approve-dangerous", approve_dangerous]
    return build_parser().parse_args(argv)


@dataclass
class ConnectionInputs:
    """연동 설정 창의 입력 필드를 그대로 담는 값 객체 (전부 문자열 — Entry 위젯의
    StringVar와 1:1로 대응). 비워두면 그 항목은 Mock으로 실행된다."""

    control_program_host: str = ""
    control_program_port: str = ""
    ppmac_host: str = ""
    ppmac_port: str = "1025"
    inspection_program_host: str = ""
    inspection_program_port: str = ""
    use_wmi: bool = False


def _parse_port(text: str, label: str) -> int:
    text = text.strip()
    if not text:
        raise ValueError(f"{label} 포트를 입력하세요.")
    try:
        port = int(text)
    except ValueError:
        raise ValueError(f"{label} 포트는 숫자여야 합니다.") from None
    if not 0 < port < 65536:
        raise ValueError(f"{label} 포트는 1~65535 사이여야 합니다.")
    return port


def build_connected_run_all_args(
    equipment_id: str,
    inputs: ConnectionInputs,
    approved_dangerous_io_ids: Iterable[str] = (),
) -> argparse.Namespace:
    """연동 설정 창의 입력값으로 run-all 인자를 만든다. 호스트를 비워둔 항목은
    Mock으로 남는다. 호스트는 입력했는데 포트가 비었거나 숫자가 아니면
    ValueError를 낸다(메시지를 그대로 사용자에게 보여줄 수 있다).

    approved_dangerous_io_ids는 작업자가 화면에서 체크해 승인한 위험 출력
    io_id들 — 승인하지 않은 위험 출력은 계속 NA로 남는다(안전 기본값).
    """
    kwargs: dict[str, object] = {"use_wmi": inputs.use_wmi}

    if inputs.control_program_host.strip():
        kwargs["control_program_host"] = inputs.control_program_host.strip()
        kwargs["control_program_port"] = _parse_port(inputs.control_program_port, "제어 프로그램")

    if inputs.ppmac_host.strip():
        kwargs["ppmac_host"] = inputs.ppmac_host.strip()
        kwargs["ppmac_port"] = _parse_port(inputs.ppmac_port or "1025", "PPMAC")

    if inputs.inspection_program_host.strip():
        kwargs["inspection_program_host"] = inputs.inspection_program_host.strip()
        kwargs["inspection_program_port"] = _parse_port(inputs.inspection_program_port, "검사 프로그램")

    approved = sorted({io_id.strip() for io_id in approved_dangerous_io_ids if io_id.strip()})
    if approved:
        kwargs["approve_dangerous"] = ",".join(approved)

    return build_run_all_args(equipment_id, **kwargs)


def describe_connection_inputs(inputs: ConnectionInputs) -> str:
    """상단에 표시할 한 줄 요약 — 뭐가 실제 연동으로 설정돼 있는지 한눈에 보여준다."""
    parts = []
    if inputs.control_program_host.strip():
        parts.append("제어 프로그램")
    if inputs.ppmac_host.strip():
        parts.append("PPMAC")
    if inputs.inspection_program_host.strip():
        parts.append("검사 프로그램")
    if inputs.use_wmi:
        parts.append("PC WMI")
    if not parts:
        return "연동: 전부 Mock"
    return "연동: " + ", ".join(parts) + " 실기 연결"


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


# run-all의 --danger-list 기본값과 동일 — I/O Check가 실제로 읽는 파일이다.
DANGER_LIST_PATH = "config/io_check_danger_list.example.json"


def list_dangerous_io_points() -> list[IOPoint]:
    """위험 출력 목록(DANGER_LIST_PATH)에 있는 I/O를, 설명이 있으면 함께 반환한다.

    io_check가 실제로 쓰는 I/O Map은 지금 DEFAULT_IO_MAP 하나뿐이라(실제 I/O
    Map 설정 파일은 아직 없음 — TBD) 여기서 설명을 찾아온다. 파일이 없거나
    비어 있으면 빈 리스트.
    """
    dangerous_ids = load_dangerous_io_ids(DANGER_LIST_PATH)
    by_id = {point.io_id: point for point in DEFAULT_IO_MAP}
    return [
        by_id.get(io_id, IOPoint(io_id, None, None, ""))
        for io_id in sorted(dangerous_ids)
    ]
