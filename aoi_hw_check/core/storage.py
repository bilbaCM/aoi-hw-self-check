from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aoi_hw_check.core.models import CheckResult, FieldMismatch, GateStatus, Verdict


class ResultStore(ABC):
    """측정값/판정/이탈량 저장소. 설비 단위 저장과 설비 간 비교 조회를 지원한다."""

    @abstractmethod
    def save_result(self, result: CheckResult) -> None: ...

    @abstractmethod
    def list_results(
        self, equipment_id: str | None = None, check_item: str | None = None
    ) -> list[CheckResult]: ...

    @abstractmethod
    def get_baseline(self, equipment_id: str, check_item: str) -> dict[str, Any] | None:
        """설비/항목의 가장 최근 baseline 스냅샷을 반환한다."""

    @abstractmethod
    def save_baseline(self, equipment_id: str, check_item: str, snapshot: dict[str, Any]) -> None:
        """새 baseline을 이력으로 추가한다 (기존 이력은 덮어쓰지 않음)."""

    @abstractmethod
    def list_baseline_history(
        self, equipment_id: str, check_item: str
    ) -> list[dict[str, Any]]: ...


class SQLiteResultStore(ResultStore):
    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id TEXT NOT NULL,
                    check_item TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    deviation TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    measured_at TEXT NOT NULL,
                    gate_status TEXT NOT NULL,
                    criteria_version TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS baseline_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_id TEXT NOT NULL,
                    check_item TEXT NOT NULL,
                    snapshot TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def save_result(self, result: CheckResult) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO results
                    (equipment_id, check_item, verdict, deviation, detail,
                     measured_at, gate_status, criteria_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.equipment_id,
                    result.check_item,
                    result.verdict.value,
                    json.dumps([m.__dict__ for m in result.deviation], default=str),
                    result.detail,
                    result.measured_at.isoformat(),
                    result.gate_status.value,
                    result.criteria_version,
                ),
            )

    def list_results(
        self, equipment_id: str | None = None, check_item: str | None = None
    ) -> list[CheckResult]:
        query = "SELECT * FROM results WHERE 1=1"
        params: list[Any] = []
        if equipment_id is not None:
            query += " AND equipment_id = ?"
            params.append(equipment_id)
        if check_item is not None:
            query += " AND check_item = ?"
            params.append(check_item)
        query += " ORDER BY measured_at"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_result(row) for row in rows]

    def get_baseline(self, equipment_id: str, check_item: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT snapshot FROM baseline_history
                WHERE equipment_id = ? AND check_item = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (equipment_id, check_item),
            ).fetchone()
        return json.loads(row["snapshot"]) if row else None

    def save_baseline(self, equipment_id: str, check_item: str, snapshot: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO baseline_history (equipment_id, check_item, snapshot, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    equipment_id,
                    check_item,
                    json.dumps(snapshot, default=str),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def list_baseline_history(
        self, equipment_id: str, check_item: str
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT snapshot, created_at FROM baseline_history
                WHERE equipment_id = ? AND check_item = ?
                ORDER BY created_at ASC, id ASC
                """,
                (equipment_id, check_item),
            ).fetchall()
        return [
            {"snapshot": json.loads(row["snapshot"]), "created_at": row["created_at"]}
            for row in rows
        ]

    @staticmethod
    def _row_to_result(row: sqlite3.Row) -> CheckResult:
        deviation = [FieldMismatch(**m) for m in json.loads(row["deviation"])]
        return CheckResult(
            equipment_id=row["equipment_id"],
            check_item=row["check_item"],
            verdict=Verdict(row["verdict"]),
            deviation=deviation,
            detail=row["detail"],
            measured_at=datetime.fromisoformat(row["measured_at"]),
            gate_status=GateStatus(row["gate_status"]),
            criteria_version=row["criteria_version"],
        )
