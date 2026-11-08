#!/usr/bin/env python3
"""Draft packet checks. Intent links only after checks pass. No network."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

import draft_packet

MAIN = (
    "Saya lagi baca bedanya payment channel di XRPL sama antrian biasa. "
    "Kalau settlement-nya on-ledger, bagian mana yang masih sering disalahpahami?"
)
SOURCES = "Dokumen XRPL payment channels: https://xrpl.org/docs/concepts/payment-channels"
NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


class DraftPacketTests(unittest.TestCase):
    def test_good_original_gets_two_slots_and_no_publish_flag(self):
        packet = draft_packet.build_packet(
            main=MAIN,
            sources=SOURCES,
            topic="XRP",
            kind="original",
            parent_views=40,
            parent_followers=22,
            parent_reply_count=4,
            now=NOW,
        )
        self.assertTrue(packet["ok"], packet["checks"])
        self.assertFalse(packet["published"])
        self.assertEqual(packet["network_calls"], 0)
        self.assertIsNone(packet["growth_claim"])
        self.assertIn("https://x.com/intent/post?text=", packet["intent"]["main"]["url"])
        self.assertIsNone(packet["intent"]["sources"])
        self.assertFalse(packet["heuristic"]["hard_reject"])
        self.assertGreater(packet["heuristic"]["priority"], 0)
        self.assertLess(packet["checks"][0]["weighted"], 280)
        share = next(item for item in packet["checks"] if item["name"] == "weekly_xrp_share")
        self.assertFalse(share["enforced"])

    def test_sources_intent_is_a_separate_reply_link(self):
        packet = draft_packet.build_packet(
            main=MAIN,
            sources=SOURCES,
            topic="xrp",
            kind="original",
            sources_reply_to="https://x.com/gsalasan/status/1234567890123456789",
            now=NOW,
        )
        self.assertTrue(packet["ok"], packet["checks"])
        sources_url = packet["intent"]["sources"]["url"]
        main_url = packet["intent"]["main"]["url"]
        self.assertIn("in_reply_to=1234567890123456789", sources_url)
        self.assertNotIn("in_reply_to=", main_url)
        self.assertNotIn("xrpl.org", main_url)
        self.assertIn("xrpl.org", sources_url)

    def test_low_ratio_does_not_fail_an_on_niche_draft(self):
        packet = draft_packet.build_packet(
            main=MAIN,
            sources=None,
            topic="xrp",
            kind="reply",
            reply_to="99887766",
            parent_views=30,
            parent_followers=400,
            parent_reply_count=80,
            now=NOW,
        )
        self.assertTrue(packet["ok"], packet["checks"])
        self.assertEqual(packet["heuristic"]["viral_ratio_band"], "closer_to_follower_count")
        self.assertFalse(packet["heuristic"]["hard_reject"])
        self.assertIn("in_reply_to=99887766", packet["intent"]["main"]["url"])

    def test_forecast_hype_missing_question_and_merged_sources_block_intent(self):
        forecast = draft_packet.build_packet(
            main="Saya yakin harga XRP akan naik ke target minggu ini, setuju?",
            sources=None,
            topic="xrp",
            kind="original",
            now=NOW,
        )
        self.assertFalse(forecast["ok"])
        self.assertIsNone(forecast["intent"])
        negated = draft_packet.build_packet(
            main="Saya tidak membuat prediksi harga. Yang saya lihat cuma beda field di ledger, bagian mana?",
            sources=None,
            topic="xrp",
            kind="original",
            now=NOW,
        )
        self.assertTrue(negated["ok"], negated["checks"])
        hype = draft_packet.build_packet(
            main="Saya rasa ini dijamin cuan kalau kalian masuk sekarang, mau?",
            sources=None,
            topic="xrp",
            kind="original",
            now=NOW,
        )
        self.assertFalse(hype["ok"])
        no_question = draft_packet.build_packet(
            main="Saya mencatat bedanya ledger XRPL dan sidechain hari ini.",
            sources=None,
            topic="xrp",
            kind="original",
            now=NOW,
        )
        self.assertFalse(no_question["ok"])
        merged = draft_packet.build_packet(
            main=MAIN + " Sumber: https://xrpl.org/docs",
            sources=None,
            topic="xrp",
            kind="original",
            now=NOW,
        )
        self.assertFalse(merged["ok"])
        pronoun = draft_packet.build_packet(
            main="Gue lagi lihat XRPL AMM, menurut lo kenapa?",
            sources=None,
            topic="xrp",
            kind="original",
            now=NOW,
        )
        self.assertFalse(pronoun["ok"])

    def test_weekly_mix_blocks_only_from_real_originals(self):
        rows = [
            {"id": "a", "ts": "2026-11-07T00:00:00Z", "type": "original", "provenance": "real", "features": {"topic": "xrp"}},
            {"id": "c", "ts": "2026-11-07T02:00:00Z", "type": "original", "provenance": "sample", "features": {"topic": "other"}},
            {"id": "d", "ts": "2026-11-07T03:00:00Z", "type": "reply", "provenance": "real", "features": {"topic": "other"}},
        ]
        blocked = draft_packet.build_packet(main=MAIN, sources=None, topic="ai", kind="original", ledger_rows=rows, now=NOW)
        self.assertFalse(blocked["ok"])
        allowed = draft_packet.build_packet(main=MAIN, sources=None, topic="xrp", kind="original", ledger_rows=rows, now=NOW)
        self.assertTrue(allowed["ok"], allowed["checks"])
        exact = [
            {"id": "a", "ts": "2026-11-07T00:00:00Z", "type": "original", "provenance": "real", "features": {"topic": "xrp"}},
            {"id": "b", "ts": "2026-11-07T01:00:00Z", "type": "original", "provenance": "real", "features": {"topic": "xrp"}},
        ]
        at_floor = draft_packet.build_packet(main=MAIN, sources=None, topic="ai", kind="original", ledger_rows=exact, now=NOW)
        self.assertTrue(at_floor["ok"], at_floor["checks"])

    def test_overlong_main_has_no_intent(self):
        long_main = "Saya " + ("ledger " * 80) + "bagian mana?"
        packet = draft_packet.build_packet(main=long_main, sources=None, topic="xrp", kind="original", now=NOW)
        self.assertFalse(packet["ok"])
        self.assertIsNone(packet["intent"])
        length = next(item for item in packet["checks"] if item["name"] == "weighted_length")
        self.assertGreater(length["weighted"], 280)


if __name__ == "__main__":
    unittest.main()
