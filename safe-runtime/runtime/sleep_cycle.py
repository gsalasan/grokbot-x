#!/usr/bin/env python3
"""Append-only local log and outcome scorer. No network. No skill evaluation.

The score is a function of operator-reported post metrics. It does not read
best_skill.md, does not apply edits, and does not rerun a candidate skill on
held-out tasks. `gate accept` is refused so a receipt cannot be mistaken for
that evaluation.

Sample rows (provenance "sample", upstream ex_* fixtures, notes marked FAKE)
are excluded from real means. They are not account data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
from pathlib import Path

BUCKET_ORDER = ("t_night", "t24h", "t6h", "t1h", "t20m")
SECRET_RE = re.compile(
    r"(api[_-]?key\s*[:=]|bearer\s+\S|sk-[A-Za-z0-9]{10,}|xox[baprs]-|YOUR_TYPEFULLY)",
    re.IGNORECASE,
)
FAKE_RE = re.compile(r"\b(FAKE|synthetic|example only|not a live)\b", re.IGNORECASE)
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
TYPES = {"original", "reply", "sources_reply"}
SPLITS = {"train", "val"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def allowed_data_root() -> Path:
    return repo_root() / "safe-runtime" / "local-data"


def resolve_root(cli_root: str | None) -> Path:
    if cli_root:
        root = Path(cli_root).expanduser().resolve()
    else:
        env = os.environ.get("SKILLOPT_DIR", "").strip()
        root = Path(env).expanduser().resolve() if env else allowed_data_root()
    repo = repo_root().resolve()
    try:
        root.relative_to(repo)
        inside = True
    except ValueError:
        inside = False
    if inside:
        allowed = allowed_data_root().resolve()
        try:
            root.relative_to(allowed)
        except ValueError:
            if root != allowed:
                raise SystemExit(
                    json.dumps(
                        {
                            "ok": False,
                            "error": "protected_root",
                            "root": str(root),
                            "detail": (
                                "Refusing to read or write a data root inside the repo "
                                "except safe-runtime/local-data. Upstream skillopt/, "
                                "examples/, scripts/, skills/, and docs/ stay untouched."
                            ),
                        }
                    )
                )
    root.mkdir(parents=True, exist_ok=True)
    return root


def paths(root: Path) -> dict[str, Path]:
    return {
        "root": root,
        "traj": root / "trajectories.jsonl",
        "updates": root / "updates.jsonl",
        "held": root / "held_out.json",
        "rej": root / "rejected_edits.md",
        "epochs": root / "epochs",
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(
                json.dumps({"ok": False, "error": "bad_jsonl", "path": str(path), "line": lineno, "detail": str(exc)})
            )
    return rows


def append_line(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def parse_ts(value: str) -> dt.datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def is_sample(row: dict) -> bool:
    if row.get("provenance") == "sample":
        return True
    if str(row.get("id", "")).startswith("ex_"):
        return True
    notes = str(row.get("notes") or "")
    if FAKE_RE.search(notes):
        return True
    url = str(row.get("url") or "")
    if "yourhandle" in url or "/status/ex_" in url:
        return True
    return False


def latest_metrics(row: dict, updates: list[dict]) -> dict:
    merged: dict[str, dict] = {}
    base = row.get("metrics") or {}
    if isinstance(base, dict):
        for key, value in base.items():
            if isinstance(value, dict) and "views" in value:
                merged[key] = dict(value)
    for event in updates:
        if event.get("id") != row.get("id"):
            continue
        buckets = event.get("metrics") or {}
        if isinstance(buckets, dict):
            for key, value in buckets.items():
                if isinstance(value, dict) and "views" in value:
                    merged[key] = dict(value)
    for key in BUCKET_ORDER:
        if key in merged:
            return merged[key]
    for value in merged.values():
        if isinstance(value, dict) and "views" in value:
            return value
    return {}


def merged_features(row: dict, updates: list[dict]) -> dict:
    features = dict(row.get("features") or {})
    for event in updates:
        if event.get("id") != row.get("id"):
            continue
        patch = event.get("features") or {}
        if isinstance(patch, dict):
            features.update(patch)
    return features


def outcome_score(metrics: dict, features: dict) -> float | None:
    """Operator-reported outcome. Independent of any skill markdown file."""
    if "views" not in metrics:
        return None
    views = int(metrics.get("views") or 0)
    eng = int(metrics.get("likes") or 0) + int(metrics.get("replies") or 0) + int(metrics.get("bookmarks") or 0)
    base = math.log1p(views) + 0.75 * math.log1p(eng)
    if features.get("author_replied") is True:
        base *= 1.5
    if features.get("hard_open") is True:
        base *= 1.1
    return round(base / 10.0, 4)


def upstream_style_score(row_type: str, metrics: dict, features: dict) -> float | None:
    """Fork formula, kept for comparison tests. Not used as a gate.

    Multiplies replies by parent viral_ratio and penalises a 'dead diary'.
    That bakes a niche cutoff into the number. The safe status path does not
    call this.
    """
    if "views" not in metrics:
        return None
    views = int(metrics.get("views") or 0)
    eng = int(metrics.get("likes") or 0) + int(metrics.get("replies") or 0) + int(metrics.get("bookmarks") or 0)
    base = math.log1p(views) + 0.75 * math.log1p(eng)
    ratio = float(features.get("viral_ratio") or 0)
    if row_type == "reply" and ratio >= 20:
        base *= 1.35
    elif row_type == "reply" and ratio >= 12:
        base *= 1.15
    if features.get("viral_signal") == "weak_dead_diary":
        base *= 0.4
    if features.get("hard_open") is True:
        base *= 1.1
    if features.get("author_replied") is True:
        base *= 1.5
    if row_type == "reply" and ratio and ratio < 5:
        base *= 0.7
    return round(base / 10.0, 4)


def load_held(path: Path) -> dict:
    if not path.exists():
        return {
            "val_ids": [],
            "learning_rate_max_edits": 4,
            "min_real_trajectories_before_report": 8,
            "edit_accept": "disabled",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def mean(scores: list[float]) -> float | None:
    if not scores:
        return None
    return round(sum(scores) / len(scores), 4)


def scored_rows(rows: list[dict], updates: list[dict], held: dict) -> list[dict]:
    val_ids = set(held.get("val_ids") or [])
    prepared = []
    for row in rows:
        features = merged_features(row, updates)
        metrics = latest_metrics(row, updates)
        split = row.get("split")
        if split not in SPLITS:
            split = "val" if row.get("id") in val_ids else "train"
        prepared.append(
            {
                "id": row.get("id"),
                "type": row.get("type"),
                "split": split,
                "sample": is_sample(row),
                "provenance": "sample" if is_sample(row) else row.get("provenance"),
                "score": outcome_score(metrics, features),
                "metrics_present": "views" in metrics,
                "notes": row.get("notes"),
            }
        )
    return prepared


def cmd_status(p: dict[str, Path]) -> int:
    held = load_held(p["held"])
    before = {
        "traj": p["traj"].read_bytes() if p["traj"].exists() else None,
        "updates": p["updates"].read_bytes() if p["updates"].exists() else None,
        "rej": p["rej"].read_bytes() if p["rej"].exists() else None,
    }
    rows = read_jsonl(p["traj"])
    updates = read_jsonl(p["updates"])
    prepared = scored_rows(rows, updates, held)
    real = [r for r in prepared if not r["sample"]]
    sample = [r for r in prepared if r["sample"]]

    def take(pool: list[dict], split: str) -> list[float]:
        return [float(r["score"]) for r in pool if r["split"] == split and r["score"] is not None]

    real_scored = [r for r in real if r["score"] is not None]
    report = {
        "ok": True,
        "evaluation_of_skill_edits": False,
        "bookkeeping_only": True,
        "sample_rows_are_account_data": False,
        "means_are": "operator_reported_outcome_scores_unverified",
        "n_real": len(real),
        "n_sample": len(sample),
        "n_real_scored": len(real_scored),
        "real_train_mean": mean(take(real, "train")),
        "real_val_mean": mean(take(real, "val")),
        "sample_train_mean": mean(take(sample, "train")),
        "sample_val_mean": mean(take(sample, "val")),
        "min_real_before_report": int(held.get("min_real_trajectories_before_report", held.get("min_trajectories_before_edit", 8))),
        "ready_for_edit": False,
        "edit_gate": "accept_disabled",
        "learning_rate_max_edits": held.get("learning_rate_max_edits", 4),
        "files_written": False,
        "skill_file_read": False,
        "top_real": sorted(
            [{"id": r["id"], "score": r["score"], "type": r["type"]} for r in real if r["score"] is not None],
            key=lambda item: -float(item["score"]),
        )[:5],
    }
    after = {
        "traj": p["traj"].read_bytes() if p["traj"].exists() else None,
        "updates": p["updates"].read_bytes() if p["updates"].exists() else None,
        "rej": p["rej"].read_bytes() if p["rej"].exists() else None,
    }
    if before != after:
        report["ok"] = False
        report["files_written"] = True
        report["error"] = "status_mutated_files"
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


def _reject(detail: str, **extra) -> None:
    body = {"ok": False, "error": detail, **extra}
    print(json.dumps(body, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(2)


def validate_trajectory(obj: dict, existing_ids: set[str]) -> dict:
    if not isinstance(obj, dict):
        _reject("trajectory_must_be_object")
    if SECRET_RE.search(json.dumps(obj)):
        _reject("secret_like_text_refused")
    row_id = obj.get("id")
    if not isinstance(row_id, str) or not ID_RE.fullmatch(row_id):
        _reject("bad_id")
    if row_id in existing_ids:
        _reject("duplicate_id", id=row_id)
    if obj.get("type") not in TYPES:
        _reject("bad_type")
    if obj.get("provenance") not in {"real", "sample"}:
        _reject("bad_provenance")
    if obj.get("split") not in SPLITS:
        _reject("bad_split")
    text = obj.get("text")
    if not isinstance(text, str) or not text.strip():
        _reject("missing_text")
    try:
        parse_ts(str(obj.get("ts")))
    except (TypeError, ValueError):
        _reject("bad_ts")
    if is_sample(obj) and obj.get("provenance") == "real":
        _reject("sample_shape_cannot_be_real", id=row_id)
    if obj.get("provenance") == "real":
        if obj.get("human_confirmed") is not True:
            _reject("real_requires_human_confirmed")
        if FAKE_RE.search(str(obj.get("notes") or "")):
            _reject("real_notes_look_synthetic")
    else:
        if obj.get("human_confirmed") is True:
            _reject("sample_cannot_be_human_confirmed")
    url = obj.get("url")
    if url is not None:
        if not isinstance(url, str) or not (url.startswith("https://x.com/") or url.startswith("https://twitter.com/")):
            _reject("url_must_be_https_x_or_twitter_or_omitted")
    clean = {
        "id": row_id,
        "ts": obj["ts"],
        "type": obj["type"],
        "provenance": obj["provenance"],
        "human_confirmed": bool(obj.get("human_confirmed")),
        "text": text,
        "split": obj["split"],
        "features": obj.get("features") or {},
        "notes": obj.get("notes") or "",
        "logged_by": "operator_report",
        "verified_by_runtime": False,
    }
    if url:
        clean["url"] = url
    if obj.get("metrics"):
        clean["metrics"] = obj["metrics"]
    return clean


def cmd_append(p: dict[str, Path], payload: str) -> int:
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError as exc:
        _reject("bad_json", detail=str(exc))
    existing = read_jsonl(p["traj"])
    clean = validate_trajectory(obj, {str(r.get("id")) for r in existing})
    before = p["traj"].read_text(encoding="utf-8") if p["traj"].exists() else ""
    append_line(p["traj"], clean)
    after = p["traj"].read_text(encoding="utf-8")
    if not after.startswith(before):
        _reject("append_rewrote_history")
    print(json.dumps({"ok": True, "appended": clean["id"], "provenance": clean["provenance"], "files": "append_only"}, indent=2))
    return 0


def _metric_bucket(value: dict) -> dict:
    if not isinstance(value, dict):
        _reject("metric_bucket_must_be_object")
    out = {}
    for key in ("views", "likes", "replies", "bookmarks"):
        if key not in value:
            _reject("metric_bucket_missing_field", field=key)
        number = value[key]
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            _reject("metric_must_be_non_negative_int", field=key)
        out[key] = number
    return out


def cmd_append_update(p: dict[str, Path], payload: str) -> int:
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError as exc:
        _reject("bad_json", detail=str(exc))
    if SECRET_RE.search(json.dumps(obj)):
        _reject("secret_like_text_refused")
    row_id = obj.get("id")
    rows = read_jsonl(p["traj"])
    known = {r.get("id"): r for r in rows}
    if row_id not in known:
        _reject("unknown_id", id=row_id)
    try:
        parse_ts(str(obj.get("ts")))
    except (TypeError, ValueError):
        _reject("bad_ts")
    clean: dict = {"id": row_id, "ts": obj["ts"], "verified_by_runtime": False}
    if obj.get("metrics"):
        clean["metrics"] = {name: _metric_bucket(bucket) for name, bucket in obj["metrics"].items()}
    if obj.get("features"):
        if not isinstance(obj["features"], dict):
            _reject("features_must_be_object")
        allowed = {}
        for key in ("author_replied", "hard_open", "viral_ratio", "parent_views", "parent_followers", "parent_reply_count", "topic"):
            if key in obj["features"]:
                allowed[key] = obj["features"][key]
        clean["features"] = allowed
    if "metrics" not in clean and "features" not in clean:
        _reject("update_needs_metrics_or_features")
    before = p["updates"].read_text(encoding="utf-8") if p["updates"].exists() else ""
    traj_before = p["traj"].read_bytes()
    append_line(p["updates"], clean)
    after = p["updates"].read_text(encoding="utf-8")
    if not after.startswith(before) or p["traj"].read_bytes() != traj_before:
        _reject("update_rewrote_history")
    print(json.dumps({"ok": True, "updated": row_id, "trajectory_bytes_unchanged": True}, indent=2))
    return 0


def cmd_gate(p: dict[str, Path], result: str, summary: str, edits: list[str]) -> int:
    if result == "accept":
        print(
            json.dumps(
                {
                    "accepted": False,
                    "evaluation": "not_available",
                    "reason": "score_is_not_a_function_of_skill_text",
                    "detail": (
                        "Refusing to accept a skill edit. This process scores logged "
                        "view and engagement counts. It does not execute candidate "
                        "skill text on held-out tasks, so a higher val mean would not "
                        "be evidence that the edit works. No epoch file was written."
                    ),
                    "summary_ignored": summary,
                    "edits_ignored": edits,
                },
                indent=2,
            )
        )
        return 3
    if result == "reject" and len(edits) > int(load_held(p["held"]).get("learning_rate_max_edits", 4)):
        _reject("too_many_edits", max=load_held(p["held"]).get("learning_rate_max_edits", 4))
    p["epochs"].mkdir(parents=True, exist_ok=True)
    now = stamp()
    receipt = {
        "accepted": False,
        "evaluation": "not_run",
        "reason": "operator_recorded_a_rejection" if result == "reject" else "operator_recorded_a_skip",
        "summary": summary,
        "edits": edits,
        "ts": now,
    }
    path = p["epochs"] / f"{now}_{result}.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if result == "reject":
        if not p["rej"].exists():
            p["rej"].write_text(
                "# Rejected ideas\n\n"
                "These are notes the operator chose not to adopt. "
                "A note here is not a failed held-out experiment.\n",
                encoding="utf-8",
            )
        with p["rej"].open("a", encoding="utf-8") as handle:
            handle.write(f"\n## {now}\n{summary}\n")
            for edit in edits:
                handle.write(f"- {edit}\n")
            handle.flush()
            os.fsync(handle.fileno())
    print(json.dumps({"ok": True, "recorded": result, "evaluation": "not_run", "path": str(path)}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Non-publishing append-only outcome log")
    parser.add_argument("--root", default=None, help="Data directory. Defaults to safe-runtime/local-data or SKILLOPT_DIR.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    ap = sub.add_parser("append")
    ap.add_argument("--json", required=True)
    up = sub.add_parser("append-update")
    up.add_argument("--json", required=True)
    gp = sub.add_parser("gate")
    gp.add_argument("result", choices=("accept", "reject", "skip"))
    gp.add_argument("--summary", required=True)
    gp.add_argument("--edit", action="append", default=[])
    args = parser.parse_args(argv)
    p = paths(resolve_root(args.root))
    if args.cmd == "status":
        return cmd_status(p)
    if args.cmd == "append":
        return cmd_append(p, args.json)
    if args.cmd == "append-update":
        return cmd_append_update(p, args.json)
    if args.cmd == "gate":
        return cmd_gate(p, args.result, args.summary, args.edit)
    return 2


if __name__ == "__main__":
    sys.exit(main())
