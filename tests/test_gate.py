from __future__ import annotations

import unittest

from aoi_hw_check.core.gate import InvalidGateTransition, next_status, transition
from aoi_hw_check.core.models import GateStatus


class GateTransitionTest(unittest.TestCase):
    def test_sequential_forward_transitions_are_allowed(self) -> None:
        self.assertEqual(transition(GateStatus.GENERATED, GateStatus.TRIAL), GateStatus.TRIAL)
        self.assertEqual(transition(GateStatus.TRIAL, GateStatus.OPTIMIZED), GateStatus.OPTIMIZED)
        self.assertEqual(
            transition(GateStatus.OPTIMIZED, GateStatus.VALIDATED), GateStatus.VALIDATED
        )
        self.assertEqual(
            transition(GateStatus.VALIDATED, GateStatus.APPLIED), GateStatus.APPLIED
        )

    def test_skipping_a_stage_is_rejected(self) -> None:
        with self.assertRaises(InvalidGateTransition):
            transition(GateStatus.GENERATED, GateStatus.OPTIMIZED)

    def test_backward_transition_is_rejected(self) -> None:
        with self.assertRaises(InvalidGateTransition):
            transition(GateStatus.TRIAL, GateStatus.GENERATED)

    def test_staying_at_the_same_stage_is_rejected(self) -> None:
        with self.assertRaises(InvalidGateTransition):
            transition(GateStatus.TRIAL, GateStatus.TRIAL)

    def test_advancing_past_applied_is_rejected(self) -> None:
        with self.assertRaises(InvalidGateTransition):
            transition(GateStatus.APPLIED, GateStatus.GENERATED)


class NextStatusTest(unittest.TestCase):
    def test_returns_the_immediate_next_stage(self) -> None:
        self.assertEqual(next_status(GateStatus.GENERATED), GateStatus.TRIAL)
        self.assertEqual(next_status(GateStatus.TRIAL), GateStatus.OPTIMIZED)
        self.assertEqual(next_status(GateStatus.OPTIMIZED), GateStatus.VALIDATED)
        self.assertEqual(next_status(GateStatus.VALIDATED), GateStatus.APPLIED)

    def test_returns_none_when_already_at_the_final_stage(self) -> None:
        self.assertIsNone(next_status(GateStatus.APPLIED))


if __name__ == "__main__":
    unittest.main()
