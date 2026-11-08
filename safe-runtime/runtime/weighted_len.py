#!/usr/bin/env python3
"""Local X weighted-length check. No network.

Weights come from safe-runtime/config/twitter_text_v3.json, copied from
twitter-text config v3 (max 280, scale 100, default weight 200, URLs 23).

This counter sums Unicode code points. twitter-text can collapse a ZWJ emoji
into one emoji (displayed length 2). Summing code points over-counts those
sequences, so a long emoji chain can fail here while X would still accept it.
Explicit http(s) URLs count as 23. Other text, including www links without a
scheme, counts per code point, which is longer than X for a missed URL.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "twitter_text_v3.json"
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
TRAILING = ".,!?:;)]}\"'`"


@lru_cache(maxsize=1)
def config() -> dict:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    ranges = tuple((int(r["start"]), int(r["end"]), int(r["weight"])) for r in data["ranges"])
    return {
        "max": int(data["maxWeightedTweetLength"]),
        "scale": int(data["scale"]),
        "default": int(data["defaultWeight"]),
        "url_length": int(data["transformedURLLength"]),
        "ranges": ranges,
        "emoji_parsing_in_upstream_config": bool(data.get("emojiParsingEnabled")),
        "emoji_collapsed_here": False,
    }


def _weight(codepoint: int, cfg: dict) -> int:
    for start, end, weight in cfg["ranges"]:
        if start <= codepoint <= end:
            return weight
    return cfg["default"]


def _text_weight(text: str, cfg: dict) -> int:
    return sum(_weight(ord(ch), cfg) for ch in text)


def weighted_length(text: str) -> int:
    cfg = config()
    total = 0
    cursor = 0
    for match in URL_RE.finditer(text):
        total += _text_weight(text[cursor:match.start()], cfg)
        raw = match.group(0)
        trimmed = raw
        while trimmed and trimmed[-1] in TRAILING:
            trimmed = trimmed[:-1]
        total += cfg["url_length"] * cfg["scale"]
        total += _text_weight(raw[len(trimmed):], cfg)
        cursor = match.end()
    total += _text_weight(text[cursor:], cfg)
    scale = cfg["scale"]
    length = total // scale
    if total % scale:
        length += 1
    return length


def fits(text: str, limit: int | None = None) -> dict:
    cfg = config()
    cap = cfg["max"] if limit is None else limit
    length = weighted_length(text)
    return {
        "weighted": length,
        "limit": cap,
        "ok": length <= cap,
        "method": "twitter-text-v3-codepoints-urls-23-zwj-not-collapsed",
        "emoji_parsing_in_upstream_config": cfg["emoji_parsing_in_upstream_config"],
        "emoji_collapsed_here": False,
    }
