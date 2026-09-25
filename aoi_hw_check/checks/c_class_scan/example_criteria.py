from __future__ import annotations

from aoi_hw_check.checks.c_class_scan.constants import DOF_CHECK_ITEM
from aoi_hw_check.checks.gantry_squareness_check.judge import CHECK_ITEM as GANTRY_CHECK_ITEM
from aoi_hw_check.checks.optical_subsystem_check.judge import check_item_name
from aoi_hw_check.checks.pin_pad_flatness_check.judge import (
    CHECK_ITEM as FLATNESS_CHECK_ITEM,
)
from aoi_hw_check.core.thresholds import CriteriaStore

# 개발/테스트용 예시 값 — 실제 값은 광학계 설계 스펙(DOF), 계측 요구정밀도,
# Glass 사양 등에서 확보 후 교체 필요 (TBD). 인스펙터 카메라 대수는 설비마다
# 다르므로, 여기서는 Mock이 흉내 내는 3대(INS1~INS3)를 대표로 예시값을 등록한다
# — 실제 등록은 그 설비의 실제 인스펙터 번호 기준으로 Gate 관리 화면에서 한다.
_EXAMPLE_DOF_UM: dict[str, float] = {
    "INS1": 5.0,
    "INS2": 15.0,
    "INS3": 8.0,
}

_EXAMPLE_FOCUS_RATIO_RANGE: dict[str, tuple[float, float]] = {
    "INS1": (0.85, 1.15),
    "INS2": (0.85, 1.15),
    "INS3": (0.85, 1.15),
}

_EXAMPLE_FLATNESS_MAX_UM = 5.0
_EXAMPLE_GANTRY_MAX_DEVIATION_DEG = 0.05


def seed_example_dof_criteria(criteria_store: CriteriaStore) -> None:
    for inspector_id, dof_um in _EXAMPLE_DOF_UM.items():
        criteria_store.save_criteria(DOF_CHECK_ITEM, inspector_id, 0.0, dof_um)


def seed_example_focus_criteria(criteria_store: CriteriaStore) -> None:
    for inspector_id, (lo, hi) in _EXAMPLE_FOCUS_RATIO_RANGE.items():
        criteria_store.save_criteria(check_item_name(inspector_id), "focus_ratio", lo, hi)


def seed_example_flatness_criteria(criteria_store: CriteriaStore) -> None:
    criteria_store.save_criteria(
        FLATNESS_CHECK_ITEM, "pin_height_deviation_um", 0.0, _EXAMPLE_FLATNESS_MAX_UM
    )


def seed_example_gantry_criteria(criteria_store: CriteriaStore) -> None:
    criteria_store.save_criteria(
        GANTRY_CHECK_ITEM,
        "perpendicularity_deviation_deg",
        0.0,
        _EXAMPLE_GANTRY_MAX_DEVIATION_DEG,
    )
