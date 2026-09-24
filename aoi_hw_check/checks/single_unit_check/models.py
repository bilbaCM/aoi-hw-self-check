from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SequenceStepResult:
    step_id: str
    completed: bool
    abnormal_stop: bool
    detail: str = ""
