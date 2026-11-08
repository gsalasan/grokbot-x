---
name: X draft shape
description: >-
  Shape @gsalasan drafts: Indonesian casual saya, at most 280 X-weighted
  characters, a short closing question, and a separate sources reply. Keep at
  least two thirds of weekly originals on XRP.
---
# X draft shape

Write the main post in casual Indonesian, pronoun `saya`, with technical
English terms where they are the real name of the thing (XRPL, AMM, AI).
End the main post with a short question, at most 12 words.

## Length and split

- Main text is at most 280 weighted characters, using twitter-text v3 weights:
  most Latin letters count as 1, characters outside those ranges count as 2,
  and an `http` or `https` URL counts as 23.
- The local counter does not collapse ZWJ emoji, so emoji-heavy lines can look
  longer here than they will on X.
- The sources reply is always a second post. Links and `Sumber:` lines go there.
- For an original, build the sources intent only after the main status id exists.
- For a reply, the main reply and the sources reply stay two composers.

## Weekly mix

At least two thirds of original posts in a rolling week are about XRP.
Replies do not fill that quota. Count only rows the operator logged as
`provenance: real`. Sample fixtures and the upstream ecommerce examples are
not this account.

The local ledger starts empty in this VM. Until the parent backfills real
rows, the checker reports the mix as not yet enforced.

## Banned in the draft

Price forecasts, price targets, "will pump", `dijamin`, `guaranteed`,
`10x` / `100x`, and hype (`cuan`, `moon`, `gem`, `wagmi`). A negation such as
"bukan prediksi harga" is allowed. No fabricated statistics and no promise of
follower or view growth.

## Heuristics

Parent view/follower ratio and reply-thread size are ranking hints from
`runtime/heuristic.py`. A low ratio or a busy thread does not by itself drop
an on-niche candidate. The parent's 32/40 scan threshold stays the parent's
rule.
