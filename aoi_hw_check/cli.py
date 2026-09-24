from __future__ import annotations

import argparse

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
from aoi_hw_check.checks.optical_comm_check.collector import MockOpticalCommCollector
from aoi_hw_check.checks.optical_comm_check.judge import run_optical_comm_check
from aoi_hw_check.checks.pc_check.collector import MockPCStateCollector
from aoi_hw_check.checks.pc_check.judge import run_pc_check
from aoi_hw_check.checks.single_unit_check.judge import run_single_unit_check
from aoi_hw_check.checks.single_unit_check.runner import MockSingleUnitSequenceRunner
from aoi_hw_check.core.models import CheckResult, Verdict
from aoi_hw_check.core.report import build_action_item_list
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore

INTERLOCK_EXPECTED_SEQUENCE = [
    "upstream_ready",
    "load_request",
    "load_complete",
    "downstream_ack",
]


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

    action_items = subparsers.add_parser(
        "action-items", help="셋업 착수 전 조치 대상 목록 출력"
    )
    action_items.add_argument("--equipment-id", required=True)
    action_items.add_argument("--db", default="aoi_hw_check.sqlite3")

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
        result = run_io_check(
            MockPLCTestModeClient(),
            DEFAULT_IO_MAP,
            dangerous_ids,
            approved_ids,
            store,
            args.equipment_id,
        )
    elif args.command == "single-unit-check":
        store = SQLiteResultStore(args.db)
        result = run_single_unit_check(
            MockSingleUnitSequenceRunner(),
            store,
            args.equipment_id,
            supervised=args.supervised,
        )
    elif args.command == "interlock-check":
        store = SQLiteResultStore(args.db)
        criteria_store = JSONCriteriaStore(args.criteria)
        if args.seed_example_criteria:
            seed_example_interlock_criteria(criteria_store)
        result = run_interlock_check(
            MockInterlockTestRunner(),
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
    else:
        return 1

    _print_result(result)
    return 0 if result.verdict != Verdict.FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
