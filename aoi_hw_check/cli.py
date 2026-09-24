from __future__ import annotations

import argparse

from aoi_hw_check.checks.motion_hw_check.collector import MockMotionHWCollector
from aoi_hw_check.checks.motion_hw_check.example_criteria import seed_example_criteria
from aoi_hw_check.checks.motion_hw_check.judge import run_motion_hw_check
from aoi_hw_check.checks.optical_comm_check.collector import MockOpticalCommCollector
from aoi_hw_check.checks.optical_comm_check.judge import run_optical_comm_check
from aoi_hw_check.checks.pc_check.collector import MockPCStateCollector
from aoi_hw_check.checks.pc_check.judge import run_pc_check
from aoi_hw_check.core.models import CheckResult, Verdict
from aoi_hw_check.core.storage import SQLiteResultStore
from aoi_hw_check.core.thresholds import JSONCriteriaStore


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
            seed_example_criteria(criteria_store)
        result = run_motion_hw_check(
            MockMotionHWCollector(), criteria_store, store, args.equipment_id
        )
    elif args.command == "optical-comm-check":
        store = SQLiteResultStore(args.db)
        result = run_optical_comm_check(
            MockOpticalCommCollector(), store, args.equipment_id
        )
    else:
        return 1

    _print_result(result)
    return 0 if result.verdict != Verdict.FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
