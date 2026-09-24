from __future__ import annotations

import argparse

from aoi_hw_check.checks.c_class_scan.collector import MockScanCollector
from aoi_hw_check.checks.c_class_scan.example_criteria import (
    seed_example_dof_criteria,
    seed_example_flatness_criteria,
    seed_example_focus_criteria,
    seed_example_gantry_criteria,
)
from aoi_hw_check.checks.c_class_scan.pipeline import run_c_class_pipeline
from aoi_hw_check.checks.interlock_check.example_criteria import (
    seed_example_criteria as seed_example_interlock_criteria,
)
from aoi_hw_check.checks.interlock_check.judge import run_interlock_check
from aoi_hw_check.checks.interlock_check.runner import MockInterlockTestRunner
from aoi_hw_check.checks.io_check.client import DEFAULT_IO_MAP, MockPLCTestModeClient
from aoi_hw_check.checks.io_check.danger_list import load_dangerous_io_ids
from aoi_hw_check.checks.io_check.judge import run_io_check
from aoi_hw_check.checks.motion_hw_check.collector import MockMotionHWCollector
from aoi_hw_check.checks.motion_hw_check.example_criteria import (
    seed_example_criteria as seed_example_motion_criteria,
)
from aoi_hw_check.checks.motion_hw_check.judge import run_motion_hw_check
from aoi_hw_check.checks.motion_tuning_check.example_criteria import (
    seed_example_criteria as seed_example_motion_tuning_criteria,
)
from aoi_hw_check.checks.motion_tuning_check.judge import run_motion_tuning_check
from aoi_hw_check.checks.motion_tuning_check.runner import MockMotionTuningRunner
from aoi_hw_check.checks.optical_comm_check.collector import MockOpticalCommCollector
from aoi_hw_check.checks.optical_comm_check.judge import run_optical_comm_check
from aoi_hw_check.checks.pc_check.collector import MockPCStateCollector
from aoi_hw_check.checks.pc_check.judge import run_pc_check
from aoi_hw_check.checks.single_unit_check.judge import run_single_unit_check
from aoi_hw_check.checks.single_unit_check.runner import MockSingleUnitSequenceRunner
from aoi_hw_check.core.gate import InvalidGateTransition
from aoi_hw_check.core.models import CheckResult, GateStatus, Verdict
from aoi_hw_check.core.report import build_action_item_list
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore
from aoi_hw_check.integrations.control_program.clients import (
    TCPInterlockTestRunner,
    TCPPLCTestModeClient,
    TCPSingleUnitSequenceRunner,
)
from aoi_hw_check.integrations.control_program.connection import ControlProgramConnection

INTERLOCK_EXPECTED_SEQUENCE = [
    "upstream_ready",
    "load_request",
    "load_complete",
    "downstream_ack",
]


def _add_control_program_args(subparser: argparse.ArgumentParser) -> None:
    """C# 제어 프로그램(CC-Link 마스터 보유)과의 TCP 연동 옵션. 둘 다 지정하면
    실제 TCP 클라이언트를, 아니면 Mock을 사용한다."""
    subparser.add_argument(
        "--control-program-host",
        default=None,
        help="C# 제어 프로그램 TCP 호스트 (미지정 시 Mock 사용)",
    )
    subparser.add_argument("--control-program-port", type=int, default=None)


def _control_program_connection(args: argparse.Namespace) -> ControlProgramConnection | None:
    if args.control_program_host and args.control_program_port:
        return ControlProgramConnection(args.control_program_host, args.control_program_port)
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aoi-hw-check")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pc_check = subparsers.add_parser("pc-check", help="PC 동작 Check 실행")
    pc_check.add_argument("--equipment-id", required=True)
    pc_check.add_argument("--db", default="aoi_hw_check.sqlite3")

    motion_check = subparsers.add_parser("motion-hw-check", help="모션 H/W Check 실행")
    motion_check.add_argument("--equipment-id", required=True)
    motion_check.add_argument("--db", default="aoi_hw_check.sqlite3")
    motion_check.add_argument("--criteria", default="motion_hw_check_criteria.json")
    motion_check.add_argument(
        "--seed-example-criteria",
        action="store_true",
        help="개발/테스트용 예시 기준 범위를 등록한 뒤 실행 (실제 출하 DATA 아님)",
    )

    optical_check = subparsers.add_parser(
        "optical-comm-check", help="광학 부품 동작·통신 확인 실행"
    )
    optical_check.add_argument("--equipment-id", required=True)
    optical_check.add_argument("--db", default="aoi_hw_check.sqlite3")

    io_check = subparsers.add_parser("io-check", help="I/O Check 실행")
    io_check.add_argument("--equipment-id", required=True)
    io_check.add_argument("--db", default="aoi_hw_check.sqlite3")
    io_check.add_argument(
        "--danger-list",
        default="config/io_check_danger_list.example.json",
        help="위험 출력 목록 설정 파일 경로",
    )
    io_check.add_argument(
        "--approve-dangerous",
        default="",
        help="작업자가 확인·승인한 위험 출력 io_id 목록 (쉼표로 구분)",
    )
    _add_control_program_args(io_check)

    single_unit_check = subparsers.add_parser(
        "single-unit-check", help="설비 단동 동작 확인 실행"
    )
    single_unit_check.add_argument("--equipment-id", required=True)
    single_unit_check.add_argument("--db", default="aoi_hw_check.sqlite3")
    single_unit_check.add_argument(
        "--supervised",
        action="store_true",
        help="최초 구동을 작업자가 감독하며 승인했음을 명시",
    )
    _add_control_program_args(single_unit_check)

    interlock_check = subparsers.add_parser(
        "interlock-check", help="설비 연동 동작 Test 실행"
    )
    interlock_check.add_argument("--equipment-id", required=True)
    interlock_check.add_argument("--db", default="aoi_hw_check.sqlite3")
    interlock_check.add_argument("--criteria", default="interlock_check_criteria.json")
    interlock_check.add_argument(
        "--seed-example-criteria",
        action="store_true",
        help="개발/테스트용 예시 지연 기준을 등록한 뒤 실행 (실제 운영 로그 실측치 아님)",
    )
    _add_control_program_args(interlock_check)

    action_items = subparsers.add_parser(
        "action-items", help="셋업 착수 전 조치 대상 목록 출력"
    )
    action_items.add_argument("--equipment-id", required=True)
    action_items.add_argument("--db", default="aoi_hw_check.sqlite3")

    c_class_scan = subparsers.add_parser(
        "c-class-scan",
        help="C분류 6항목 실행 (기준 시료 1회 Scan을 공유하는 AF Z맵/스캔영상 파이프라인)",
    )
    c_class_scan.add_argument("--equipment-id", required=True)
    c_class_scan.add_argument("--db", default="aoi_hw_check.sqlite3")
    c_class_scan.add_argument("--dof-criteria", default="c_class_dof_criteria.json")
    c_class_scan.add_argument("--focus-criteria", default="c_class_focus_criteria.json")
    c_class_scan.add_argument("--flatness-criteria", default="c_class_flatness_criteria.json")
    c_class_scan.add_argument("--gantry-criteria", default="c_class_gantry_criteria.json")
    c_class_scan.add_argument(
        "--seed-example-criteria",
        action="store_true",
        help="개발/테스트용 예시 기준(DOF/초점비율/평탄도/직각도)을 등록한 뒤 실행",
    )
    c_class_scan.add_argument("--max-scan-attempts", type=int, default=3)

    motion_tuning_check = subparsers.add_parser(
        "motion-tuning-check", help="모션 Tuning 상태 확인 실행"
    )
    motion_tuning_check.add_argument("--equipment-id", required=True)
    motion_tuning_check.add_argument("--db", default="aoi_hw_check.sqlite3")
    motion_tuning_check.add_argument(
        "--criteria", default="motion_tuning_check_criteria.json"
    )
    motion_tuning_check.add_argument(
        "--seed-example-criteria",
        action="store_true",
        help="개발/테스트용 예시 허용 배수를 등록한 뒤 실행 (동종 설비 실측 분포 기반 아님)",
    )

    criteria_gate = subparsers.add_parser(
        "criteria-gate", help="기준(Criteria)의 Gate 상태를 한 단계 전진시킨다"
    )
    criteria_gate.add_argument("--store", required=True, help="JSON 기준 저장소 파일 경로")
    criteria_gate.add_argument("--check-item", required=True)
    criteria_gate.add_argument("--key", required=True)
    criteria_gate.add_argument(
        "--target", required=True, choices=[status.value for status in GateStatus]
    )

    return parser


def _print_result(result: CheckResult) -> None:
    print(f"[{result.verdict.value}] {result.check_item} - {result.detail}")
    for mismatch in result.deviation:
        print(
            f"  - {mismatch.field_path}: "
            f"baseline={mismatch.baseline_value} current={mismatch.current_value}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "pc-check":
        store = SQLiteResultStore(args.db)
        result = run_pc_check(MockPCStateCollector(), store, args.equipment_id)
    elif args.command == "motion-hw-check":
        store = SQLiteResultStore(args.db)
        criteria_store = JSONCriteriaStore(args.criteria)
        if args.seed_example_criteria:
            seed_example_motion_criteria(criteria_store)
        result = run_motion_hw_check(
            MockMotionHWCollector(), criteria_store, store, args.equipment_id
        )
    elif args.command == "optical-comm-check":
        store = SQLiteResultStore(args.db)
        result = run_optical_comm_check(
            MockOpticalCommCollector(), store, args.equipment_id
        )
    elif args.command == "io-check":
        store = SQLiteResultStore(args.db)
        dangerous_ids = load_dangerous_io_ids(args.danger_list)
        approved_ids = {
            io_id.strip() for io_id in args.approve_dangerous.split(",") if io_id.strip()
        }
        connection = _control_program_connection(args)
        client = TCPPLCTestModeClient(connection) if connection else MockPLCTestModeClient()
        result = run_io_check(
            client,
            DEFAULT_IO_MAP,
            dangerous_ids,
            approved_ids,
            store,
            args.equipment_id,
        )
    elif args.command == "single-unit-check":
        store = SQLiteResultStore(args.db)
        connection = _control_program_connection(args)
        runner = (
            TCPSingleUnitSequenceRunner(connection)
            if connection
            else MockSingleUnitSequenceRunner()
        )
        result = run_single_unit_check(
            runner,
            store,
            args.equipment_id,
            supervised=args.supervised,
        )
    elif args.command == "interlock-check":
        store = SQLiteResultStore(args.db)
        criteria_store = JSONCriteriaStore(args.criteria)
        if args.seed_example_criteria:
            seed_example_interlock_criteria(criteria_store)
        connection = _control_program_connection(args)
        runner = TCPInterlockTestRunner(connection) if connection else MockInterlockTestRunner()
        result = run_interlock_check(
            runner,
            INTERLOCK_EXPECTED_SEQUENCE,
            criteria_store,
            store,
            args.equipment_id,
        )
    elif args.command == "action-items":
        store = SQLiteResultStore(args.db)
        items = build_action_item_list(store, args.equipment_id)
        if not items:
            print(f"{args.equipment_id}: 조치 대상 없음")
            return 0
        print(f"{args.equipment_id} 조치 대상 목록 ({len(items)}건)")
        for item in items:
            print(f"  [{item.verdict.value}] {item.check_item}: {item.detail}")
        return 1
    elif args.command == "c-class-scan":
        store = SQLiteResultStore(args.db)
        dof_store = JSONCriteriaStore(args.dof_criteria)
        focus_store = JSONCriteriaStore(args.focus_criteria)
        flatness_store = JSONCriteriaStore(args.flatness_criteria)
        gantry_store = JSONCriteriaStore(args.gantry_criteria)
        if args.seed_example_criteria:
            seed_example_dof_criteria(dof_store)
            seed_example_focus_criteria(focus_store)
            seed_example_flatness_criteria(flatness_store)
            seed_example_gantry_criteria(gantry_store)
        outcome = run_c_class_pipeline(
            MockScanCollector(),
            dof_store,
            focus_store,
            flatness_store,
            gantry_store,
            store,
            args.equipment_id,
            max_scan_attempts=args.max_scan_attempts,
        )
        print(outcome.detail)
        for item in outcome.results:
            _print_result(item)
        if outcome.escalated:
            return 1
        return 0 if outcome.all_passed else 1
    elif args.command == "motion-tuning-check":
        store = SQLiteResultStore(args.db)
        criteria_store = JSONCriteriaStore(args.criteria)
        if args.seed_example_criteria:
            seed_example_motion_tuning_criteria(criteria_store)
        result = run_motion_tuning_check(
            MockMotionTuningRunner(), criteria_store, store, args.equipment_id
        )
    elif args.command == "criteria-gate":
        criteria_store = JSONCriteriaStore(args.store)
        try:
            criteria = criteria_store.advance_criteria_gate(
                args.check_item, args.key, GateStatus(args.target)
            )
        except (KeyError, InvalidGateTransition) as exc:
            print(f"오류: {exc}")
            return 1
        print(
            f"{criteria.check_item} / {criteria.key}: gate_status -> "
            f"{criteria.gate_status.value} (v{criteria.version}, "
            f"[{criteria.min_value}, {criteria.max_value}])"
        )
        return 0
    else:
        return 1

    _print_result(result)
    return 0 if result.verdict != Verdict.FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
