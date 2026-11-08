# Deployment handoff for the parent Grok Bot

This VM studied `gsalasan/grokbot-x` and added a separate non-publishing
bundle. It did not install skills, routines, or memory on a parent bot.
It did not connect an account, create a credential, call X, or call Typefully.

Upstream commit that was read: `cade7d95e2b60c2c60c53648d4d10ba87ae18443`
on `main` (2026-08-26, "Polish README GitHub topics line for discovery").
The bundle on this branch is the commit that adds `safe-runtime/`.
`main` was not modified.

## Verdict

SkillOpt in this fork does **not** evaluate candidate skill changes on
held-out data. It keeps a bookkeeping log. Microsoft SkillOpt does the
other thing: it runs the frozen agent with the edited skill on a held-out
selection split and accepts the edit only when that selection score
strictly improves
([training loop, stage 6](https://github.com/microsoft/SkillOpt/blob/main/docs/guide/training-loop.md)).

What this fork actually does, from `skillopt/sleep_cycle.py`:

- `rescore` (lines 76-97) uses views, likes, replies, bookmarks, parent
  `viral_ratio`, `viral_signal`, `hard_open`, and `author_replied`.
- `paths()` records `best_skill.md` (line 38). No command reads or writes
  that file. Replacing the skill text leaves `val_mean` unchanged.
- `status` rewrites `trajectories.jsonl` in place (lines 127-131).
- `gate accept` writes a receipt with `"accepted": true` and does not
  compare scores (lines 166-183). It also ignores
  `min_trajectories_before_edit`. An empty log still accepts.
- The docstring says the script adopts edits into `best_skill.md`. The
  body never does.

The five rows in `examples/trajectories.example.jsonl` are synthetic
ecommerce posts. Notes in the file say `FAKE example`. They are not
@gsalasan posts, not XRP posts, and not a measurement of 22 followers or
20-50 views. Those follower and view figures came from the study brief.
This VM did not read the account. `content-operator/voice.md`,
`findings.md`, and `drafts*.json` were not in this workspace.

Stored example scores also disagree with the scorer. Running `status` on
a temp copy rewrote them:

| id | score in the example file | after upstream `status` | safe outcome score |
|---|---:|---:|---:|
| ex_001 | 0.208 | 0.2287 | 0.2287 |
| ex_002 | 0.71 | 1.0325 | 0.7648 |
| ex_003 | 0.04 | 0.0308 | 0.1099 |
| ex_004 | 0.82 | 0.858 | 0.6355 |
| ex_005 | 0.18 | 0.1792 | 0.1792 |

Upstream means after that rewrite: train `0.1462`, val `0.9452`, `n=5`,
`ready_for_edit=false`. After the skill file was replaced with different
text, both means stayed the same. Padding the same fake rows to 8 flipped
upstream `ready_for_edit` to true. The safe scorer on 8 sample rows keeps
`n_real=0` and `ready_for_edit=false`.

Safe `status` on the five sample rows, read-only: `n_real=0`,
`n_sample=5`, `real_val_mean=null`, `sample_train_mean=0.1726`,
`sample_val_mean=0.7002`, `evaluation_of_skill_edits=false`.

The safe outcome score is `log1p(views) + 0.75 * log1p(likes+replies+bookmarks)`,
divided by 10, with `author_replied` ×1.5 and `hard_open` ×1.1. It does
not multiply by viral ratio and it does not apply the 0.4 dead-diary
penalty. Ratio and reply count go through `heuristic.py` as a smooth
priority. `hard_reject` is always false.

`gate accept` in the safe runtime exits 3, prints
`evaluation: not_available`, and writes no file. A higher average of old
view counts would still not show that a skill edit works. A real
evaluation would draft with the candidate skill on held-out prompts and
score the drafts. That harness is not in this bundle. Do not describe a
reject note or a metric delta as a passed gate.

## What was not deployed

The upstream claim that Typefully OAuth plus `made_with_ai: false` stops
X from applying an AI label is unsupported here. The repo asserts it in
`docs/PUBLISH.md`, `docs/x-publish-no-ai-label.md`, and
`skills/x-publish-no-ai-label/SKILL.md`. It cites no reproducible check,
and this VM did not publish anything that could test it. Those
instructions are not in the safe skills. Do not install them. Do not run
delete-and-repost loops to probe a label.

Also leave these unused for this account:

- `scripts/publish_original.py` posts through Typefully when a key is set.
- `scripts/create_reply_draft.py` creates a Typefully draft when a key is set.
- `skills/x-skillopt-learn/SKILL.md` tells the bot to ship without asking.
- `skills/x-human-cadence/SKILL.md` includes bot-browser likes and bookmarks.
- `skillopt/best_skill.md` hard-bans low-ratio parents and tells the bot
  to follow about 15-20 accounts a day and to publish via Typefully.
- `docs/BRAND-BIBLE.template.md` is an ecommerce-ops template. It is not
  the voice of an Indonesian XRP and AI account.

Typefully stays optional. This runtime never calls it. The operator path
is a manual `https://x.com/intent/post` link after exact approval of that
specific text. A standing "you may post" is not approval of a later draft.

## Account constraints encoded for review

Parent voice still wins. This VM could not read it.

- Casual Indonesian, pronoun `saya`. Technical English names stay
  (XRPL, AMM, AI). `gue`, `gw`, `aku`, `lo`, and `lu` fail the checker.
- No price forecast and no hype lexicon (`dijamin`, `guaranteed`, `10x`,
  `cuan`, `moon`, `gem`, `wagmi`, and the phrases in `draft_packet.py`).
  A nearby negation (`tidak`, `bukan`, `tanpa`, `jangan`, `no`, `not`,
  `never`) keeps a phrase such as "bukan prediksi harga".
- Main text at most 280 weighted characters. Weights are the vendored
  twitter-text v3 table: scale 100, default weight 200, ranges copied
  into `config/twitter_text_v3.json` on 2026-11-08, `http(s)` URLs as 23.
  ZWJ emoji are not collapsed, so some emoji lines fail here while X
  would still accept them. That bias is toward refusing a long post.
- Main ends with a question of 1 to 12 words.
- Links and `Sumber:` / `Source:` lines belong in a second post. The
  packet withholds the sources intent until `--sources-reply-to` has the
  status id of the post it should hang from.
- At least two thirds of original posts in a rolling 168 hours are XRP.
  Replies do not count. Sample rows do not count. With an empty ledger
  the check is reported and not enforced, because this VM has no backfill
  of the live week. After at least one real original is logged, a draft
  that would push the projected share under 2/3 fails. Exactly 2/3 passes.
- View/follower ratio and reply-thread size are hints. A parent at about
  40 views and 22 followers (ratio about 1.8, the brief's scale, not a
  live reading) still produces a priority and does not fail the packet.
  The parent's existing scan threshold of 32/40 stays the parent's rule.
- Existing clock, Asia/Jakarta, left as the parent already runs it:
  scan every 3 hours, morning 08:00, evening 19:00, weekly Sunday 18:00.
  07:00 and 12:30 WIB are reported helpful composer windows, not new
  crons. This bundle installs no scheduler.
- One original in an hour, no catch-up burst, no bot likes, follows, or DMs.

There is no growth target in the config. None of the scores predict
followers or views.

## Dependencies and commands

Tested in this VM: Python 3.12.3. No virtualenv and no pip install.
`safe-runtime/requirements.txt` is a comment, not a package list.

```bash
python3 --version
python3 -m unittest discover -s safe-runtime/tests -v
```

Parent data directory, outside the upstream `skillopt/` folder:

```bash
mkdir -p "$HOME/gsalasan-x-log"
cp safe-runtime/config/held_out.example.json "$HOME/gsalasan-x-log/held_out.json"
python3 safe-runtime/runtime/sleep_cycle.py --root "$HOME/gsalasan-x-log" status
python3 safe-runtime/runtime/draft_packet.py \
  --main "MAIN TEXT" \
  --sources "SOURCES TEXT" \
  --topic xrp \
  --kind original \
  --ledger "$HOME/gsalasan-x-log/trajectories.jsonl"
```

Exit codes for the safe tools:

| code | meaning |
|---|---|
| 0 | status ok, or draft checks passed and intent URLs are in the JSON |
| 2 | bad input, duplicate id, secret-like text, or a protected path |
| 3 | `gate accept` refused |
| 4 | draft checks failed; `intent` is null |

`status` and `append` refuse a data root inside the repo except
`safe-runtime/local-data/`. That keeps a trial run from rewriting
`skillopt/` or `examples/`.

Log a post only after the operator confirms it happened:

```bash
python3 safe-runtime/runtime/sleep_cycle.py --root "$HOME/gsalasan-x-log" append --json '{
  "id": "local_001",
  "ts": "2026-11-08T01:00:00Z",
  "type": "original",
  "provenance": "real",
  "human_confirmed": true,
  "text": "the text that was actually posted",
  "split": "train",
  "features": {"topic": "xrp"},
  "url": "https://x.com/gsalasan/status/STATUS_ID"
}'
```

Later counts are a new line in `updates.jsonl`, not an edit of the
original line:

```bash
python3 safe-runtime/runtime/sleep_cycle.py --root "$HOME/gsalasan-x-log" append-update --json '{
  "id": "local_001",
  "ts": "2026-11-08T02:00:00Z",
  "metrics": {"t1h": {"views": 30, "likes": 1, "replies": 0, "bookmarks": 0}}
}'
```

The runtime does not fetch that URL. `verified_by_runtime` stays false.
Means are labeled `operator_reported_outcome_scores_unverified`.

## Tests executed in this VM

Command: `python3 -m unittest discover -s safe-runtime/tests -v`

Result: **29 tests, OK, 0.575s**, Python 3.12.3. `py_compile` on the
runtime and test modules also succeeded. No `.env` file was present.
No package was installed.

| module | what it checked |
|---|---|
| `tests/test_weighted_len.py` | 280 vs 281, emoji weight 2, URL weight 23, v3 limits |
| `tests/test_heuristic.py` | low ratio and 400 replies stay non-rejecting; 12x is not a step |
| `tests/test_sleep_cycle.py` | read-only status, append-only history, sample rows excluded, accept writes nothing, reject labeled `not_run`, protected roots refused |
| `tests/test_draft_packet.py` | separate intent links, forecast and hype blocked, negation allowed, weekly mix ignores sample rows, low ratio still passes |
| `tests/test_upstream_is_bookkeeping.py` | temp copy only: status mutates scores, skill text does not move val, fake n=8 sets `ready_for_edit`, gate accept writes a receipt |
| `tests/test_publish_scripts_do_not_connect.py` | with a socket constructor that raises, both upstream helpers exit 2 on a missing key and never hit the guard. Safe runtime sources contain no `urllib.request`, Typefully host, or `made_with_ai` |

A sample original used only as a fixture (not posted) weighed 143, got
priority `0.5228` at 40 views / 22 followers / 4 replies, `published:
false`, `network_calls: 0`, and a main intent URL. The sources intent
stayed null until a reply target was supplied.

Re-run the same unittest command on the parent box after copying the
directory. This VM run is not that installation.

## What the parent bot does with this

1. Read this file and the five `safe-runtime/skills/*/SKILL.md` files.
2. Merge them with the parent `voice.md`. Where they disagree, keep the
   parent voice, and keep the bans on publishing, credentials, price
   forecasts, and unsupported label claims.
3. Copy the five safe skills into the parent skill directory only after
   that read. Do not also install `skills/` from the repo root.
4. Leave the existing 3-hour, 08:00, 19:00, and Sunday 18:00 routines in
   place. Do not add a SkillOpt cron that accepts edits.
5. Point the log at a private directory. Append a row only when the
   operator confirms a real post. Keep using the manual intent link.

## Risks and limitations

- Upstream publish scripts are still in the tree. A Typefully key would
  make them post or create a remote draft. Do not configure that key for
  this adoption.
- Intent links are still a composer. The operator can submit text the
  checker rejected if they copy it by hand. Failed packets set `intent`
  to null so the happy path does not offer the link.
- X can change intent parameters. The operator has to see the right body
  and the right reply parent in the composer. URL length over 1800
  characters drops the link and leaves the text in the packet.
- The weighted-length check is a local subset of twitter-text v3, not the
  library itself. Missed URLs count long. ZWJ sequences count long.
- The forecast list is a lexicon. New slang gets through. Ordinary words
  on the list (`moon`, `gem`, `cuan`) fail closed.
- The weekly mix is a rolling 168 hours on logged timestamps, not the
  Sunday 18:00 WIB week, and it is blind until real originals are logged.
- Outcome scores reward reported attention. They confound topic, timing,
  and luck. They are not a skill A/B test.
- `gate reject` is a notebook entry. It is not evidence that an idea was
  tried.
- Append is single-writer. Two processes can race the duplicate-id check.
- Nothing here measured the live account, promised reach, or created an
  external account.

## Path index

Copy and review:

- `/workspace/safe-runtime/HANDOFF.md`
- `/workspace/safe-runtime/README.md`
- `/workspace/safe-runtime/requirements.txt`
- `/workspace/safe-runtime/.gitignore`
- `/workspace/safe-runtime/local-data/.gitkeep`
- `/workspace/safe-runtime/config/account.example.json`
- `/workspace/safe-runtime/config/held_out.example.json`
- `/workspace/safe-runtime/config/routine.parent.json`
- `/workspace/safe-runtime/config/twitter_text_v3.json`
- `/workspace/safe-runtime/runtime/draft_packet.py`
- `/workspace/safe-runtime/runtime/heuristic.py`
- `/workspace/safe-runtime/runtime/sleep_cycle.py`
- `/workspace/safe-runtime/runtime/weighted_len.py`
- `/workspace/safe-runtime/skills/x-intent-approval/SKILL.md`
- `/workspace/safe-runtime/skills/x-human-cadence/SKILL.md`
- `/workspace/safe-runtime/skills/x-draft-shape/SKILL.md`
- `/workspace/safe-runtime/skills/x-unslop-id-xrp/SKILL.md`
- `/workspace/safe-runtime/skills/x-skillopt-honest/SKILL.md`
- `/workspace/safe-runtime/fixtures/README.md`
- `/workspace/safe-runtime/fixtures/sample_trajectories.jsonl`
- `/workspace/safe-runtime/tests/test_weighted_len.py`
- `/workspace/safe-runtime/tests/test_heuristic.py`
- `/workspace/safe-runtime/tests/test_sleep_cycle.py`
- `/workspace/safe-runtime/tests/test_draft_packet.py`
- `/workspace/safe-runtime/tests/test_upstream_is_bookkeeping.py`
- `/workspace/safe-runtime/tests/test_publish_scripts_do_not_connect.py`

Read as evidence of the fork, and do not install as the live loop:

- `/workspace/README.md`
- `/workspace/.env.example`
- `/workspace/.gitignore`
- `/workspace/LICENSE`
- `/workspace/docs/OPERATOR.md`
- `/workspace/docs/PLAYBOOK.md`
- `/workspace/docs/PUBLISH.md`
- `/workspace/docs/SKILLOPT.md`
- `/workspace/docs/BRAND-BIBLE.template.md`
- `/workspace/docs/x-article-intent-engine.md`
- `/workspace/docs/x-human-cadence.md`
- `/workspace/docs/x-publish-no-ai-label.md`
- `/workspace/examples/best_skill.starter.md`
- `/workspace/examples/trajectories.example.jsonl`
- `/workspace/scripts/create_reply_draft.py`
- `/workspace/scripts/publish_original.py`
- `/workspace/skillopt/best_skill.md`
- `/workspace/skillopt/held_out.example.json`
- `/workspace/skillopt/rejected_edits.md`
- `/workspace/skillopt/sleep_cycle.py`
- `/workspace/skillopt/epochs/.gitkeep`
- `/workspace/skills/x-human-cadence/SKILL.md`
- `/workspace/skills/x-publish-no-ai-label/SKILL.md`
- `/workspace/skills/x-skillopt-learn/SKILL.md`
- `/workspace/skills/x-unslop-humanizer/SKILL.md`
- `/workspace/skills/x-unslop-humanizer-2/SKILL.md`

Absent on this VM, present only on the parent box per the study brief:

- `/workspace/content-operator/voice.md`
- `/workspace/content-operator/findings.md`
- `/workspace/content-operator/drafts*.json`
