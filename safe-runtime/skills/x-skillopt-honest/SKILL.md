---
name: X SkillOpt honest log
description: >-
  Log real posts only after the operator confirms them, score operator-reported
  metrics, and refuse skill-edit acceptance. Sample trajectories are not
  account data. This loop does not evaluate a candidate skill on held-out tasks.
---
# Honest log, not a SkillOpt training run

Microsoft SkillOpt accepts a skill edit when the edited skill is executed on
held-out tasks and that selection score strictly improves. The fork's
`skillopt/sleep_cycle.py` does not do that. It scores metrics already stored
on a row, rewrites the log, and records accept/reject receipts without reading
`best_skill.md`.

Use `safe-runtime/runtime/sleep_cycle.py` instead.

## What the safe commands do

- `status` prints means and writes nothing. Real and sample rows are separate.
  `ready_for_edit` stays false.
- `append` adds one real or sample row to the end of `trajectories.jsonl`.
- `append-update` adds a later metric or feature observation. It does not edit
  the original line.
- `gate reject` and `gate skip` store a note that nobody evaluated a skill.
- `gate accept` exits with a refusal and writes no receipt.

## Real rows

A real row requires `provenance: real` and `human_confirmed: true`, plus the
operator's statement that the post is theirs. The runtime does not fetch the
URL and does not treat the row as verified. Sample rows, `ex_*` ids, and notes
marked FAKE never count as @gsalasan data, even if there are more than eight
of them.

Leave metrics empty until the operator types numbers they actually saw.
Missing metrics stay missing. Do not copy the upstream example scores.

## Skill files

Do not rewrite a skill because a val mean moved. A val mean here is an average
of reported view and engagement counts. Editing prose cannot change it.
A real evaluation would draft with the candidate skill on held-out prompts and
score those drafts with a judge that looks at the text. That harness is not
in this bundle. Until it exists, skill changes stay a human edit with no
acceptance claim.
