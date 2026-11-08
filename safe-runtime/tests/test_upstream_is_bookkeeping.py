#!/usr/bin/env python3
"""Show the upstream fork scores posts and records gates without reading the skill.

Runs only against temp copies. Does not touch /workspace/skillopt or call a network.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UPSTREAM = REPO / "skillopt" / "sleep_cycle.py"
EXAMPLE = REPO / "examples" / "trajectories.example.jsonl"
HELD = REPO / "skillopt" / "held_out.example.json"
PY = sys.executable


def status(root: Path) -> dict:
    result = subprocess.run(
        [PY, str(UPSTREAM), "--root", str(root), "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class UpstreamBookkeepingTests(unittest.TestCase):
    def test_status_rewrites_scores_and_skill_text_does_not_change_val(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            traj = root / "trajectories.jsonl"
            skill = root / "best_skill.md"
            shutil.copy(EXAMPLE, traj)
            shutil.copy(HELD, root / "held_out.json")
            skill.write_text("ORIGINAL SKILL\n", encoding="utf-8")
            before = [json.loads(line) for line in traj.read_text(encoding="utf-8").splitlines()]
            first = status(root)
            after = [json.loads(line) for line in traj.read_text(encoding="utf-8").splitlines()]
            rewritten = {row["id"]: row["score"] for row in after}
            stored = {row["id"]: row["score"] for row in before}
            self.assertNotEqual(stored["ex_002"], rewritten["ex_002"])
            self.assertEqual(rewritten["ex_001"], 0.2287)
            self.assertEqual(rewritten["ex_002"], 1.0325)
            self.assertEqual(rewritten["ex_003"], 0.0308)
            self.assertEqual(rewritten["ex_004"], 0.858)
            self.assertEqual(rewritten["ex_005"], 0.1792)
            self.assertEqual(first["val_mean"], 0.9452)
            self.assertEqual(first["train_mean"], 0.1462)
            self.assertFalse(first["ready_for_edit"])
            self.assertEqual(first["n"], 5)
            skill.write_text("A completely different candidate skill\n", encoding="utf-8")
            second = status(root)
            self.assertEqual(second["val_mean"], first["val_mean"])
            self.assertEqual(second["train_mean"], first["train_mean"])
            self.assertIn("different candidate skill", skill.read_text(encoding="utf-8"))

    def test_gate_accept_succeeds_without_a_score_check_or_skill_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / "best_skill.md"
            skill.write_text("UNCHANGED\n", encoding="utf-8")
            (root / "rejected_edits.md").write_text("# rej\n", encoding="utf-8")
            (root / "trajectories.jsonl").write_text("", encoding="utf-8")
            result = subprocess.run(
                [
                    PY,
                    str(UPSTREAM),
                    "--root",
                    str(root),
                    "gate",
                    "accept",
                    "--summary",
                    "claimed improvement with no rows",
                    "--edit",
                    "always post",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(skill.read_text(encoding="utf-8"), "UNCHANGED\n")
            receipt = json.loads(next((root / "epochs").glob("*accept.json")).read_text(encoding="utf-8"))
            self.assertTrue(receipt["accepted"])
            self.assertNotIn("val", receipt)

    def test_eight_fake_rows_flip_ready_for_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [json.loads(line) for line in EXAMPLE.read_text(encoding="utf-8").splitlines()]
            padded = []
            for index in range(8):
                row = dict(rows[index % len(rows)])
                row["id"] = f"fake_{index}"
                padded.append(json.dumps(row))
            (root / "trajectories.jsonl").write_text("\n".join(padded) + "\n", encoding="utf-8")
            shutil.copy(HELD, root / "held_out.json")
            report = status(root)
            self.assertEqual(report["n"], 8)
            self.assertTrue(report["ready_for_edit"])


if __name__ == "__main__":
    unittest.main()
