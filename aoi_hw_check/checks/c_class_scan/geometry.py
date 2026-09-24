from __future__ import annotations

import math


def fit_plane(points: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    """(x, y, z) 점들에 최소자승으로 평면 z = a*x + b*y + c 를 피팅해 (a, b, c)를 반환한다."""
    n = len(points)
    if n < 3:
        raise ValueError("평면 피팅에는 최소 3개 점이 필요합니다")

    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_z = sum(p[2] for p in points)
    sum_xx = sum(p[0] ** 2 for p in points)
    sum_yy = sum(p[1] ** 2 for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_xz = sum(p[0] * p[2] for p in points)
    sum_yz = sum(p[1] * p[2] for p in points)

    m = [
        [sum_xx, sum_xy, sum_x],
        [sum_xy, sum_yy, sum_y],
        [sum_x, sum_y, float(n)],
    ]
    v = [sum_xz, sum_yz, sum_z]

    return _solve_3x3(m, v)


def _det3(m: list[list[float]]) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def _solve_3x3(m: list[list[float]], v: list[float]) -> tuple[float, float, float]:
    det = _det3(m)
    if abs(det) < 1e-12:
        raise ValueError("평면을 피팅할 수 없습니다 (점들이 한 직선 위에 있거나 부족함)")

    def replace_col(col: int) -> float:
        mm = [row[:] for row in m]
        for i in range(3):
            mm[i][col] = v[i]
        return _det3(mm)

    a = replace_col(0) / det
    b = replace_col(1) / det
    c = replace_col(2) / det
    return a, b, c


def tilt_magnitude_deg(a: float, b: float) -> float:
    """평면 z = a*x + b*y + c의 기울기 크기를 각도(도)로 반환한다."""
    return math.degrees(math.atan(math.hypot(a, b)))


def tilt_direction_deg(a: float, b: float) -> float:
    """기울기 방향(가장 가파르게 내려가는 방향)을 X축 기준 각도(도)로 반환한다."""
    return math.degrees(math.atan2(b, a))


def plane_z_range(
    a: float, b: float, c: float, points: list[tuple[float, float, float]]
) -> float:
    """측정된 (x, y) 범위에 걸쳐 피팅된 평면이 예측하는 Z 값의 최대-최소 폭을 반환한다.

    Tilt로 인해 실제 측정 영역에서 발생하는 높이 변화량 — 초점 이탈량의 근사치로 쓴다.
    """
    zs = [a * p[0] + b * p[1] + c for p in points]
    return max(zs) - min(zs)


def fit_line_direction_deg(points: list[tuple[float, float]]) -> float:
    """(x, y) 점들에 최소자승 직선을 피팅해 X축 기준 방향각(도, -90~90)을 반환한다.

    수직선(x가 거의 일정)도 특이점 없이 다루기 위해 y=mx+c 형태 대신
    공분산 행렬의 주축 방향(PCA)을 사용한다.
    """
    n = len(points)
    if n < 2:
        raise ValueError("직선 피팅에는 최소 2개 점이 필요합니다")

    mean_x = sum(p[0] for p in points) / n
    mean_y = sum(p[1] for p in points) / n
    cov_xx = sum((p[0] - mean_x) ** 2 for p in points)
    cov_yy = sum((p[1] - mean_y) ** 2 for p in points)
    cov_xy = sum((p[0] - mean_x) * (p[1] - mean_y) for p in points)

    theta = 0.5 * math.atan2(2 * cov_xy, cov_xx - cov_yy)
    return math.degrees(theta)


def angle_between_directions_deg(theta1_deg: float, theta2_deg: float) -> float:
    """두 직선의 방향각으로부터 사잇각(도, 0~90)을 계산한다."""
    diff = abs(theta1_deg - theta2_deg) % 180.0
    return min(diff, 180.0 - diff)
