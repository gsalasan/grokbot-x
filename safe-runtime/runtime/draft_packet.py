#!/usr/bin/env python3
"""Build a local draft packet and, when checks pass, X intent links.

Does not post, reply, like, follow, DM, upload media, or call X or Typefully.
Intent links are for a person to open after they approve that exact text.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

import heuristic
import weighted_len

SHORT_QUESTION_WORDS = 12
XRP_SHARE = 2 / 3
WINDOW = dt.timedelta(days=7)
ID_MARKERS = re.compile(
    r"\b(yang|untuk|ini|itu|dengan|dari|ke|di|saya|karena|atau|tidak|lagi|kalau|apa|mana|sama|baca)\b",
    re.IGNORECASE,
)
SAYA_RE = re.compile(r"\bsaya\b", re.IGNORECASE)
BANNED_PRONOUN = re.compile(r"\b(gue|gw|aku|loe|lo|lu)\b", re.IGNORECASE)
EM_DASH = re.compile(r"[—–]|--")
LINK_RE = re.compile(r"https?://", re.IGNORECASE)
SOURCE_LABEL = re.compile(r"(?im)^\s*(sumber|source|sources)\s*:")
NEGATION = re.compile(r"\b(tidak|bukan|tanpa|jangan|no|not|never)\b", re.IGNORECASE)
STATUS_RE = re.compile(r"/status/(\d+)")
FORECAST = re.compile(
    r"("
    r"\bakan\s+(naik|turun|pump|moon|meledak|tembus)\b|"
    r"\bharga\s+(akan|target|besok|minggu\s+depan)\b|"
    r"\btarget\s+harga\b|"
    r"\bprediksi\s+harga\b|"
    r"\bprice\s+target\b|"
    r"\bwill\s+(pump|moon|dump|hit|reach)\b|"
    r"\bto\s+the\s+moon\b|"
    r"\b(10x|100x|1000x)\b|"
    r"\bbeli\s+sekarang\b|"
    r"\bbuy\s+now\b|"
    r"\bguaranteed\b|"
    r"\bdijamin\b|"
    r"\bpasti\s+(naik|cuan|profit|untung)\b|"
    r"\bakan\s+viral\b|"
    r"\bgame[- ]changer\b|"
    r"\bseamless\b|"
    r"\bunlock\s+your\s+potential\b|"
    r"\bwagmi\b|"
    r"\bcuan\b|"
    r"\bmoon\b|"
    r"\bgem\b"
    r")",
    re.IGNORECASE,
)


def parse_ts(value: str) -> dt.datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def status_id(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    match = STATUS_RE.search(raw)
    if match:
        return match.group(1)
    if re.fullmatch(r"\d{5,25}", raw):
        return raw
    raise ValueError(f"reply target must be a status id or an x.com status URL, got {raw!r}")


def forecast_hits(text: str) -> list[str]:
    hits = []
    for match in FORECAST.finditer(text):
        window = text[max(0, match.start() - 32):match.start()]
        if NEGATION.search(window):
            continue
        hits.append(match.group(0))
    return hits


def question_check(text: str) -> dict:
    stripped = text.strip()
    if not stripped.endswith("?"):
        return {"ok": False, "detail": "Main text has to end with a question mark."}
    body = stripped[:-1]
    parts = re.split(r"[.!?]\s+|\n+", body)
    question = (parts[-1].strip() + "?") if parts else stripped
    words = re.findall(r"\S+", question)
    ok = 1 <= len(words) <= SHORT_QUESTION_WORDS
    return {
        "ok": ok,
        "question": question,
        "words": len(words),
        "max_words": SHORT_QUESTION_WORDS,
        "detail": "Ending question is short enough." if ok else "Ending question needs 1 to 12 words.",
    }


def load_ledger(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def xrp_share(rows: list[dict], topic: str, kind: str, now: dt.datetime) -> dict:
    real = []
    ignored = 0
    for row in rows:
        if row.get("provenance") != "real" or row.get("type") != "original":
            ignored += 1
            continue
        try:
            when = parse_ts(str(row.get("ts")))
        except (TypeError, ValueError):
            ignored += 1
            continue
        if now - when > WINDOW:
            continue
        real.append(str((row.get("features") or {}).get("topic") or row.get("topic") or "").lower())
    base_n = len(real)
    base_xrp = sum(1 for item in real if item == "xrp")
    if kind != "original":
        return {
            "ok": True,
            "enforced": False,
            "applies_to": "originals_only",
            "real_originals_in_window": base_n,
            "xrp_originals_in_window": base_xrp,
            "ignored_non_real_or_non_original": ignored,
            "detail": "Replies and source replies do not change the weekly original mix.",
        }
    projected_n = base_n + 1
    projected_xrp = base_xrp + (1 if topic == "xrp" else 0)
    share = projected_xrp / projected_n
    enforced = base_n >= 1
    ok = (not enforced) or share + 1e-9 >= XRP_SHARE
    return {
        "ok": ok,
        "enforced": enforced,
        "projected_share": round(share, 4),
        "minimum": round(XRP_SHARE, 4),
        "real_originals_in_window": base_n,
        "xrp_originals_in_window": base_xrp,
        "window": "rolling_168h_from_logged_ts",
        "ignored_non_real_or_non_original": ignored,
        "detail": (
            "Local ledger only. Sample rows are ignored. An empty ledger does not "
            "prove the live week already meets the mix."
            if not enforced
            else ("Projected weekly original mix stays at or above 2/3 XRP." if ok else "Projected weekly original mix would fall under 2/3 XRP.")
        ),
    }


def intent_url(text: str, in_reply_to: str | None) -> dict:
    query = {"text": text}
    if in_reply_to:
        query["in_reply_to"] = in_reply_to
    url = "https://x.com/intent/post?" + urlencode(query)
    if len(url) > 1800:
        return {"url": None, "reason": "intent_url_longer_than_1800_use_the_text_field"}
    return {"url": url, "reason": None}


def build_packet(
    main: str,
    sources: str | None,
    topic: str,
    kind: str,
    reply_to: str | None = None,
    sources_reply_to: str | None = None,
    ledger_rows: list[dict] | None = None,
    parent_views: float | None = None,
    parent_followers: float | None = None,
    parent_reply_count: int | None = None,
    now: dt.datetime | None = None,
) -> dict:
    topic_norm = topic.strip().lower()
    checks = []
    features = {}
    if parent_views is not None:
        features["parent_views"] = parent_views
    if parent_followers is not None:
        features["parent_followers"] = parent_followers
    if parent_reply_count is not None:
        features["parent_reply_count"] = parent_reply_count
    hints = heuristic.priority(features)

    length = weighted_len.fits(main)
    checks.append({"name": "weighted_length", **length})

    q = question_check(main)
    checks.append({"name": "short_question", **q})

    pronoun_ok = True
    pronoun_detail = "Main uses saya."
    if BANNED_PRONOUN.search(main):
        pronoun_ok = False
        pronoun_detail = "Use saya. gue, gw, aku, lo, and lu fail this check."
    elif not SAYA_RE.search(main):
        pronoun_ok = False
        pronoun_detail = "Main is Indonesian casual and includes saya. Technical English terms can sit inside that sentence."
    elif not ID_MARKERS.search(main):
        pronoun_ok = False
        pronoun_detail = "Main needs ordinary Indonesian around saya."
    checks.append({"name": "indonesian_saya", "ok": pronoun_ok, "detail": pronoun_detail})

    dash_ok = EM_DASH.search(main) is None
    checks.append({
        "name": "no_em_dash",
        "ok": dash_ok,
        "detail": "No em dash, en dash, or double hyphen in the main text." if dash_ok else "Remove em dashes, en dashes, and double hyphens from the main text.",
    })

    forecast = forecast_hits(main) + (forecast_hits(sources) if sources else [])
    checks.append({
        "name": "no_price_forecast_or_hype",
        "ok": not forecast,
        "matches": forecast,
        "detail": "No price forecast or hype phrase." if not forecast else "Rewrite without the matched forecast or hype phrase.",
    })

    link_in_main = LINK_RE.search(main) is not None or SOURCE_LABEL.search(main) is not None
    sources_text = (sources or "").strip()
    separate_ok = not link_in_main
    separate_detail = "Main has no source link. Sources stay a second post."
    if link_in_main:
        separate_ok = False
        separate_detail = "Move links and sumber/source lines into the sources reply."
    if sources_text and sources_text == main.strip():
        separate_ok = False
        separate_detail = "Sources text has to be a different post from the main text."
    if sources_text and sources_text in main:
        separate_ok = False
        separate_detail = "Sources text is still inside the main text."
    checks.append({
        "name": "sources_separate",
        "ok": separate_ok,
        "has_sources": bool(sources_text),
        "detail": separate_detail,
    })

    topic_ok = topic_norm in {"xrp", "ai", "other"}
    checks.append({
        "name": "topic",
        "ok": topic_ok,
        "topic": topic_norm,
        "detail": "Topic is xrp, ai, or other." if topic_ok else "Topic must be xrp, ai, or other.",
    })

    try:
        reply_id = status_id(reply_to)
        sources_id = status_id(sources_reply_to)
        reply_target_ok = kind != "reply" or bool(reply_id)
        reply_detail = "Reply target present." if reply_target_ok else "A reply needs --reply-to with a status id."
    except ValueError as exc:
        reply_id = None
        sources_id = None
        reply_target_ok = False
        reply_detail = str(exc)
    checks.append({"name": "reply_target", "ok": reply_target_ok, "detail": reply_detail})

    share = xrp_share(ledger_rows or [], topic_norm if topic_ok else "other", kind, now or dt.datetime.now(dt.timezone.utc))
    checks.append({"name": "weekly_xrp_share", **share})

    # Hints never become a failing check.
    blocking = [c for c in checks if not c.get("ok")]
    packet_ok = not blocking and topic_ok

    intent = None
    if packet_ok:
        main_target = reply_id if kind == "reply" else None
        intent = {
            "main": intent_url(main, main_target),
            "sources": intent_url(sources_text, sources_id) if sources_text and sources_id else None,
            "sources_followup": (
                "After the main post exists, run this command again with --sources-reply-to set to that status id. Keep the sources text out of the main post."
                if sources_text and not sources_id
                else "Sources intent is a separate composer from the main text."
            ),
        }
    return {
        "ok": packet_ok,
        "published": False,
        "network_calls": 0,
        "approval": "Open an intent link only after you approve this exact text. This packet does not perform that approval.",
        "kind": kind,
        "topic": topic_norm,
        "main": main,
        "sources": sources_text or None,
        "checks": checks,
        "heuristic": hints,
        "intent": intent,
        "growth_claim": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local non-publishing draft packet")
    parser.add_argument("--main", required=True)
    parser.add_argument("--sources", default=None)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--kind", choices=("original", "reply"), default="original")
    parser.add_argument("--reply-to", default=None)
    parser.add_argument("--sources-reply-to", default=None)
    parser.add_argument("--ledger", default=None, help="Optional trajectories.jsonl. Sample rows are ignored.")
    parser.add_argument("--parent-views", type=float, default=None)
    parser.add_argument("--parent-followers", type=float, default=None)
    parser.add_argument("--parent-replies", type=int, default=None)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args(argv)
    ledger_path = Path(args.ledger).expanduser().resolve() if args.ledger else None
    packet = build_packet(
        main=args.main,
        sources=args.sources,
        topic=args.topic,
        kind=args.kind,
        reply_to=args.reply_to,
        sources_reply_to=args.sources_reply_to,
        ledger_rows=load_ledger(ledger_path),
        parent_views=args.parent_views,
        parent_followers=args.parent_followers,
        parent_reply_count=args.parent_replies,
    )
    rendered = json.dumps(packet, indent=2, ensure_ascii=False)
    if args.json_out:
        out = Path(args.json_out).expanduser().resolve()
        repo = Path(__file__).resolve().parents[2]
        try:
            out.relative_to(repo)
            inside = True
        except ValueError:
            inside = False
        allowed = repo / "safe-runtime" / "local-data"
        if inside:
            try:
                out.relative_to(allowed)
            except ValueError:
                print(json.dumps({"ok": False, "error": "refusing_to_write_packet_into_repo", "path": str(out)}), file=sys.stderr)
                return 2
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if packet["ok"] else 4


if __name__ == "__main__":
    sys.exit(main())
