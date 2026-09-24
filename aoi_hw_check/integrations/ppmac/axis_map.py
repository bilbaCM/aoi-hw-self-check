from __future__ import annotations

import json
from pathlib import Path


def load_axis_variable_map(path: str | Path) -> dict[str, dict[str, str]]:
    """축별 {필드명: PMAC 글로벌 변수명} 매핑을 로드한다.

    실제 변수명(예: 어느 Motor 번호가 X축인지, PWM/I/O가 어느 Gate 채널에
    있는지)은 설비 PPMAC 설정마다 다르므로 이 파일은 사람이 정의한다.
    config/ppmac_axis_map.example.json은 형식만 보여주는 예시다 (TBD).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {axis_id: fields for axis_id, fields in data.items() if not axis_id.startswith("_")}
