---
name: X intent approval
description: >-
  Use before any X account action for @gsalasan. Deliver a manual intent link
  and wait for exact approval of that text. Do not post, reply, like, follow,
  DM, or change the profile.
---
# X intent approval

Account actions stay with the human operator. This skill prepares text and a
link. It does not perform the action.

## Required path

1. Read the parent voice file and findings before drafting. On the parent box
   those live at `content-operator/voice.md` and `content-operator/findings.md`.
   This study VM did not contain them.
2. Run the local draft packet in `safe-runtime/runtime/draft_packet.py`.
3. Show the packet: main text, sources text, check results, heuristic hints,
   and the intent URL when every blocking check passed.
4. Wait for an exact approval of that specific text. A general "you can post"
   is not approval of a later draft.
5. The operator opens `https://x.com/intent/post?...` and submits it themselves.

## Account actions that stay manual

Posting, replying, liking, following, unfollowing, bookmarking, reposting,
sending a DM, and editing the profile. Each one needs its own exact approval.
This runtime has no function for those actions.

## Typefully

Typefully is optional and unused here. Do not create a Typefully draft, do not
ask for an API key, and do not put a key in a skill, a routine, or a log.

## Labels

Do not claim that a client, a flag, or a browser choice removes an AI label.
Do not delete and repost in order to test a label. If a label is visible, tell
the operator and stop.
