from __future__ import annotations

import json
from pathlib import Path


def load_dangerous_io_ids(path: str | Path) -> set[str]:
    """위험 출력 목록(설정 파일)을 로드한다. 파일이 없으면 빈 집합을 반환한다.

    이 목록은 사람이 정의한다 — 프로그램은 이 목록 밖의 I/O만 무인 자동 시험하고,
    목록 안의 항목은 작업자 확인(승인) 없이는 시험하지 않는다.
    """
    p = Path(path)
    if not p.exists():
        return set()
    return set(json.loads(p.read_text(encoding="utf-8")))
