#!/usr/bin/env python3
"""Append-only log, sample exclusion, and the disabled accept gate."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RUNTIME))

import sleep_cycle

SCRIPT = RUNTIME / "sleep_cycle.py"
FIXTURE = REPO / "safe-runtime" / "fixtures" / "sample_trajectories.jsonl"
PY = sys.executable


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


class SleepCycleTests(unittest.TestCase):
    def test_formula_locks_known_rows(self):
        rows = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines()]
        by_id = {row["id"]: row for row in rows}
        score = sleep_cycle.outcome_score
        self.assertEqual(score(by_id["ex_001"]["metrics"]["t_night"], by_id["ex_001"]["features"]), 0.2287)
        self.assertEqual(score(by_id["ex_002"]["metrics"]["t_night"], by_id["ex_002"]["features"]), 0.7648)
        self.assertEqual(score(by_id["ex_003"]["metrics"]["t_night"], by_id["ex_003"]["features"]), 0.1099)
        self.assertEqual(score(by_id["ex_005"]["metrics"]["t_night"], by_id["ex_005"]["features"]), 0.1792)
        upstream = sleep_cycle.upstream_style_score(
            "reply",
            by_id["ex_002"]["metrics"]["t_night"],
            by_id["ex_002"]["features"],
        )
        self.assertEqual(upstream, 1.0325)
        self.assertNotEqual(upstream, 0.7648)

    def test_sample_status_is_read_only_and_not_account_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            traj = root / "trajectories.jsonl"
            shutil.copy(FIXTURE, traj)
            before = traj.read_bytes()
            result = run(root, "status")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(traj.read_bytes(), before)
            report = json.loads(result.stdout)
            self.assertFalse(report["evaluation_of_skill_edits"])
            self.assertFalse(report["sample_rows_are_account_data"])
            self.assertFalse(report["ready_for_edit"])
            self.assertEqual(report["edit_gate"], "accept_disabled")
            self.assertEqual(report["n_real"], 0)
            self.assertEqual(report["n_sample"], 5)
            self.assertIsNone(report["real_val_mean"])
            self.assertIsNotNone(report["sample_val_mean"])
            self.assertFalse(report["files_written"])
            self.assertFalse(report["skill_file_read"])

    def test_append_is_append_only_and_blocks_fake_real_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = {
                "id": "local_001",
                "ts": "2026-11-08T01:00:00Z",
                "type": "original",
                "provenance": "real",
                "human_confirmed": True,
                "text": "Saya catat satu hal tentang ledger.",
                "split": "train",
                "features": {"topic": "xrp"},
                "notes": "operator typed this after posting",
            }
            first = run(root, "append", "--json", json.dumps(good))
            self.assertEqual(first.returncode, 0, first.stderr)
            original = (root / "trajectories.jsonl").read_text(encoding="utf-8")
            duplicate = run(root, "append", "--json", json.dumps(good))
            self.assertEqual(duplicate.returncode, 2)
            self.assertEqual((root / "trajectories.jsonl").read_text(encoding="utf-8"), original)
            fake = dict(good, id="ex_live", notes="FAKE example")
            blocked = run(root, "append", "--json", json.dumps(fake))
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("sample_shape_cannot_be_real", blocked.stderr)
            unconfirmed = dict(good, id="local_002", human_confirmed=False)
            denied = run(root, "append", "--json", json.dumps(unconfirmed))
            self.assertEqual(denied.returncode, 2)
            self.assertEqual((root / "trajectories.jsonl").read_text(encoding="utf-8"), original)

    def test_metric_update_does_not_rewrite_the_trajectory_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = {
                "id": "local_010",
                "ts": "2026-11-08T01:00:00Z",
                "type": "reply",
                "provenance": "real",
                "human_confirmed": True,
                "text": "Saya jawab satu hal.",
                "split": "val",
                "url": "https://x.com/gsalasan/status/1",
            }
            self.assertEqual(run(root, "append", "--json", json.dumps(good)).returncode, 0)
            before = (root / "trajectories.jsonl").read_bytes()
            update = {
                "id": "local_010",
                "ts": "2026-11-08T02:00:00Z",
                "metrics": {"t1h": {"views": 30, "likes": 1, "replies": 0, "bookmarks": 0}},
            }
            result = run(root, "append-update", "--json", json.dumps(update))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "trajectories.jsonl").read_bytes(), before)
            status = json.loads(run(root, "status").stdout)
            self.assertEqual(status["n_real"], 1)
            self.assertEqual(status["n_sample"], 0)
            self.assertEqual(status["real_val_mean"], 0.3954)
            self.assertFalse(status["ready_for_edit"])

    def test_eight_sample_rows_still_do_not_open_the_edit_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lines = FIXTURE.read_text(encoding="utf-8").splitlines()
            extra = []
            for index, line in enumerate(lines):
                row = json.loads(line)
                row["id"] = f"sample_{index}"
                row["notes"] = "FAKE extra sample"
                extra.append(json.dumps(row, ensure_ascii=False))
            (root / "trajectories.jsonl").write_text("\n".join(lines + extra) + "\n", encoding="utf-8")
            report = json.loads(run(root, "status").stdout)
            self.assertGreaterEqual(report["n_sample"], 8)
            self.assertEqual(report["n_real"], 0)
            self.assertFalse(report["ready_for_edit"])

    def test_gate_accept_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "rejected_edits.md").write_text("keep\n", encoding="utf-8")
            result = run(root, "gate", "accept", "--summary", "claimed improvement", "--edit", "post every hour")
            self.assertEqual(result.returncode, 3, result.stdout)
            body = json.loads(result.stdout)
            self.assertFalse(body["accepted"])
            self.assertEqual(body["evaluation"], "not_available")
            self.assertFalse((root / "epochs").exists())
            self.assertEqual((root / "rejected_edits.md").read_text(encoding="utf-8"), "keep\n")

    def test_gate_reject_is_labeled_as_not_an_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run(root, "gate", "reject", "--summary", "operator declined", "--edit", "ban small accounts")
            self.assertEqual(result.returncode, 0, result.stderr)
            body = json.loads(result.stdout)
            self.assertEqual(body["evaluation"], "not_run")
            receipt = json.loads(next((root / "epochs").glob("*.json")).read_text(encoding="utf-8"))
            self.assertFalse(receipt["accepted"])
            self.assertEqual(receipt["evaluation"], "not_run")
            self.assertIn("ban small accounts", (root / "rejected_edits.md").read_text(encoding="utf-8"))

    def test_protected_repo_roots_are_refused(self):
        result = run(REPO / "skillopt", "status")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("protected_root", result.stderr)


if __name__ == "__main__":
    unittest.main()
