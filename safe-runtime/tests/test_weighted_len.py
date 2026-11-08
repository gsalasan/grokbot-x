#!/usr/bin/env python3
"""Weighted-length unit tests. No network."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

import weighted_len


class WeightedLenTests(unittest.TestCase):
    def test_ascii_280_fits_and_281_does_not(self):
        self.assertEqual(weighted_len.weighted_length("a" * 280), 280)
        self.assertEqual(weighted_len.weighted_length("a" * 281), 281)
        self.assertTrue(weighted_len.fits("a" * 280)["ok"])
        self.assertFalse(weighted_len.fits("a" * 281)["ok"])

    def test_emoji_counts_as_two_and_is_not_collapsed(self):
        self.assertEqual(weighted_len.weighted_length("😀"), 2)
        self.assertEqual(weighted_len.weighted_length("a" * 278 + "😀"), 280)
        self.assertEqual(weighted_len.weighted_length("a" * 279 + "😀"), 281)

    def test_url_counts_as_23_and_trailing_period_is_separate(self):
        self.assertEqual(weighted_len.weighted_length("https://example.com/a/b/c/d/e"), 23)
        self.assertEqual(weighted_len.weighted_length("ab https://example.com/foo."), 27)

    def test_config_matches_vendored_v3_limits(self):
        cfg = weighted_len.config()
        self.assertEqual(cfg["max"], 280)
        self.assertEqual(cfg["scale"], 100)
        self.assertEqual(cfg["default"], 200)
        self.assertEqual(cfg["url_length"], 23)
        self.assertFalse(cfg["emoji_collapsed_here"])


if __name__ == "__main__":
    unittest.main()
