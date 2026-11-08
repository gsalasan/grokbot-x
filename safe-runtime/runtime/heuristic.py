#!/usr/bin/env python3
"""View/follower ratio and reply competition as ranking hints.

A low ratio or a crowded thread stays a valid manual candidate. Nothing here
returns a hard reject, and nothing here clears or blocks a draft.
"""
from __future__ import annotations

import math


def _ratio_hint(ratio: float) -> float:
    return 0.05 + 0.90 * (1.0 - math.exp(-max(ratio, 0.0) / 18.0))


def _competition_hint(reply_count: int) -> float:
    return 1.0 / (1.0 + max(reply_count, 0) / 40.0)


def _band(ratio: float) -> str:
    if ratio >= 12:
        return "higher_reach_parent"
    if ratio >= 5:
        return "mid_parent"
    return "closer_to_follower_count"


def priority(features: dict | None) -> dict:
    features = features or {}
    hints: list[float] = []
    out: dict = {
        "role": "ranking_hint",
        "hard_reject": False,
        "empty_niche_gate": False,
        "viral_ratio_hint": None,
        "viral_ratio_band": "unknown",
        "reply_competition_hint": None,
        "priority": None,
    }
    raw_ratio = features.get("viral_ratio")
    if raw_ratio is None and features.get("parent_views") not in (None, "") and features.get("parent_followers") not in (None, "", 0):
        raw_ratio = float(features["parent_views"]) / float(features["parent_followers"])
    if raw_ratio is not None:
        ratio = float(raw_ratio)
        hint = _ratio_hint(ratio)
        hints.append(hint)
        out["viral_ratio"] = round(ratio, 4)
        out["viral_ratio_hint"] = round(hint, 4)
        out["viral_ratio_band"] = _band(ratio)
    raw_replies = features.get("parent_reply_count")
    if raw_replies is None:
        raw_replies = features.get("reply_count")
    if raw_replies is not None:
        replies = int(raw_replies)
        hint = _competition_hint(replies)
        hints.append(hint)
        out["parent_reply_count"] = replies
        out["reply_competition_hint"] = round(hint, 4)
    if hints:
        out["priority"] = round(sum(hints) / len(hints), 4)
    out["note"] = (
        "Hints rank a parent for a human. A small account, a low view/follower "
        "ratio, or a busy reply thread does not forbid an on-niche manual reply."
    )
    return out
