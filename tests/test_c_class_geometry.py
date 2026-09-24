from __future__ import annotations

import math
import unittest

from aoi_hw_check.checks.c_class_scan.geometry import (
    angle_between_directions_deg,
    fit_line_direction_deg,
    fit_plane,
    plane_z_range,
    tilt_direction_deg,
    tilt_magnitude_deg,
)


class FitPlaneTest(unittest.TestCase):
    def test_recovers_exact_plane_coefficients(self) -> None:
        points = [
            (x, y, 2 * x + 3 * y + 5)
            for x in (0.0, 1.0, 2.0)
            for y in (0.0, 1.0, 2.0)
        ]

        a, b, c = fit_plane(points)

        self.assertAlmostEqual(a, 2.0, places=6)
        self.assertAlmostEqual(b, 3.0, places=6)
        self.assertAlmostEqual(c, 5.0, places=6)

    def test_flat_plane_has_zero_tilt(self) -> None:
        points = [(x, y, 10.0) for x in (0.0, 1.0, 2.0) for y in (0.0, 1.0, 2.0)]

        a, b, _ = fit_plane(points)

        self.assertAlmostEqual(tilt_magnitude_deg(a, b), 0.0, places=6)

    def test_too_few_points_raises(self) -> None:
        with self.assertRaises(ValueError):
            fit_plane([(0.0, 0.0, 0.0), (1.0, 0.0, 1.0)])


class TiltMagnitudeDirectionTest(unittest.TestCase):
    def test_45_degree_slope_along_x(self) -> None:
        # z = x → 기울기 크기 45도, 방향은 +X (0도)
        self.assertAlmostEqual(tilt_magnitude_deg(1.0, 0.0), 45.0, places=6)
        self.assertAlmostEqual(tilt_direction_deg(1.0, 0.0), 0.0, places=6)

    def test_slope_along_y(self) -> None:
        self.assertAlmostEqual(tilt_direction_deg(0.0, 1.0), 90.0, places=6)


class PlaneZRangeTest(unittest.TestCase):
    def test_range_matches_actual_height_span(self) -> None:
        points = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
        a, b, c = 1.0, 0.0, 0.0  # z = x

        self.assertAlmostEqual(plane_z_range(a, b, c, points), 10.0, places=6)


class FitLineDirectionTest(unittest.TestCase):
    def test_horizontal_line_is_zero_degrees(self) -> None:
        points = [(0.0, 5.0), (1.0, 5.0), (2.0, 5.0)]

        self.assertAlmostEqual(fit_line_direction_deg(points), 0.0, places=6)

    def test_vertical_line_is_ninety_degrees(self) -> None:
        points = [(3.0, 0.0), (3.0, 1.0), (3.0, 2.0)]

        self.assertAlmostEqual(abs(fit_line_direction_deg(points)), 90.0, places=6)

    def test_45_degree_line(self) -> None:
        points = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]

        self.assertAlmostEqual(fit_line_direction_deg(points), 45.0, places=6)

    def test_too_few_points_raises(self) -> None:
        with self.assertRaises(ValueError):
            fit_line_direction_deg([(0.0, 0.0)])


class AngleBetweenDirectionsTest(unittest.TestCase):
    def test_perpendicular_lines(self) -> None:
        self.assertAlmostEqual(angle_between_directions_deg(0.0, 90.0), 90.0, places=6)

    def test_parallel_lines(self) -> None:
        self.assertAlmostEqual(angle_between_directions_deg(30.0, 30.0), 0.0, places=6)

    def test_wraps_around_180(self) -> None:
        self.assertAlmostEqual(angle_between_directions_deg(-89.0, 89.0), 2.0, places=6)


if __name__ == "__main__":
    unittest.main()
