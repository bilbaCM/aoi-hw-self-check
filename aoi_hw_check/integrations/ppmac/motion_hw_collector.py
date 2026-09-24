from __future__ import annotations

from aoi_hw_check.checks.motion_hw_check.collector import MotionHWCollector
from aoi_hw_check.checks.motion_hw_check.models import MotionHWState
from aoi_hw_check.integrations.ppmac.connection import PmacAsciiConnection


class PPMACMotionHWCollector(MotionHWCollector):
    """PPMAC(Power PMAC)에서 축별 Encoder/PWM/I/O 값을 조회한다.

    axis_variable_map: {axis_id: {field_name: PMAC 글로벌 변수명}}.
    """

    def __init__(
        self, connection: PmacAsciiConnection, axis_variable_map: dict[str, dict[str, str]]
    ):
        self._connection = connection
        self._axis_variable_map = axis_variable_map

    def collect(self) -> MotionHWState:
        axes: dict[str, dict[str, float]] = {}
        for axis_id, fields in self._axis_variable_map.items():
            axes[axis_id] = {
                field: self._connection.query(variable) for field, variable in fields.items()
            }
        return MotionHWState(axes=axes)
