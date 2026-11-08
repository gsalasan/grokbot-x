#!/usr/bin/env python3
"""Ratio and reply competition stay hints. No network."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

import heuristic


class HeuristicTests(unittest.TestCase):
    def test_low_ratio_and_crowded_thread_are_not_rejects(self):
        low = heuristic.priority({"viral_ratio": 0.2, "parent_reply_count": 400})
        self.assertFalse(low["hard_reject"])
        self.assertFalse(low["empty_niche_gate"])
        self.assertGreater(low["priority"], 0)
        self.assertLess(low["reply_competition_hint"], 0.2)
        self.assertEqual(low["viral_ratio_band"], "closer_to_follower_count")

    def test_unknown_inputs_stay_unknown(self):
        unknown = heuristic.priority({})
        self.assertIsNone(unknown["priority"])
        self.assertEqual(unknown["viral_ratio_band"], "unknown")
        self.assertFalse(unknown["hard_reject"])

    def test_higher_ratio_ranks_above_a_small_parent_without_zeroing_it(self):
        small = heuristic.priority({"parent_views": 40, "parent_followers": 22, "parent_reply_count": 3})
        wide = heuristic.priority({"viral_ratio": 22, "parent_reply_count": 3})
        self.assertFalse(small["hard_reject"])
        self.assertGreater(wide["priority"], small["priority"])
        self.assertGreater(small["priority"], 0.2)

    def test_hint_is_smooth_rather_than_a_step_at_12x(self):
        just_below = heuristic.priority({"viral_ratio": 11.9})["viral_ratio_hint"]
        just_above = heuristic.priority({"viral_ratio": 12.1})["viral_ratio_hint"]
        self.assertLess(abs(just_above - just_below), 0.02)


if __name__ == "__main__":
    unittest.main()
