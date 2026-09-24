from __future__ import annotations

import argparse

from aoi_hw_check.checks.pc_check.collector import MockPCStateCollector
from aoi_hw_check.checks.pc_check.judge import run_pc_check
from aoi_hw_check.core.models import Verdict
from aoi_hw_check.core.storage import SQLiteResultStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aoi-hw-check")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pc_check = subparsers.add_parser("pc-check", help="PC 동작 Check 실행")
    pc_check.add_argument("--equipment-id", required=True)
    pc_check.add_argument("--db", default="aoi_hw_check.sqlite3")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "pc-check":
        store = SQLiteResultStore(args.db)
        collector = MockPCStateCollector()
        result = run_pc_check(collector, store, args.equipment_id)
        print(f"[{result.verdict.value}] {result.check_item} - {result.detail}")
        for mismatch in result.deviation:
            print(
                f"  - {mismatch.field_path}: "
                f"baseline={mismatch.baseline_value} current={mismatch.current_value}"
            )
        return 0 if result.verdict != Verdict.FAIL else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
