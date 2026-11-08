# Non-publishing runtime

Local checks and an append-only log for a human who posts manually.
No credentials, no X client, no Typefully client, no cron installer.

Read [HANDOFF.md](HANDOFF.md) before copying anything onto the parent bot.
This directory is the adaptation. The skills and scripts at the repo root
are the upstream kit and are not the install set.

```bash
python3 -m unittest discover -s safe-runtime/tests -v
python3 safe-runtime/runtime/sleep_cycle.py --root /tmp/gsalasan-x-log status
python3 safe-runtime/runtime/draft_packet.py --help
```

Python 3.11+ standard library only. `requirements.txt` lists no packages.
