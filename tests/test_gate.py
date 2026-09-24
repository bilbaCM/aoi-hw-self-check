from __future__ import annotations

import unittest

from aoi_hw_check.core.gate import InvalidGateTransition, transition
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


if __name__ == "__main__":
    unittest.main()
