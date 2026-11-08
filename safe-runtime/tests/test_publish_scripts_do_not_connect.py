#!/usr/bin/env python3
"""Upstream publish helpers must exit before any socket when credentials are absent.

If a .env file exists, this test refuses to launch the helpers at all.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = sys.executable


GUARD = textwrap.dedent(
    """
    import socket
    import sys

    class BlockedSocket:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("network blocked")

    socket.socket = BlockedSocket
    socket.create_connection = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network blocked"))
    sys.argv = sys.argv[1:]
    runpy_target = sys.argv[0]
    sys.argv = sys.argv[1:]
    import runpy
    runpy.run_path(runpy_target, run_name="__main__")
    """
)


class PublishGuardTests(unittest.TestCase):
    def test_env_file_is_absent(self):
        self.assertFalse((REPO / ".env").exists(), "refusing the publish probe while .env exists")

    def _run(self, script: str, extra: list[str]) -> subprocess.CompletedProcess:
        env = {key: value for key, value in os.environ.items() if not key.startswith("YOUR_")}
        env["YOUR_TYPEFULLY_API_KEY"] = ""
        env["YOUR_TYPEFULLY_SOCIAL_SET_ID"] = ""
        env["YOUR_SOCIAL_SET_ID"] = ""
        return subprocess.run(
            [PY, "-c", GUARD, str(REPO / "scripts" / script), script, *extra],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            cwd=str(REPO),
        )

    def test_publish_original_exits_before_network(self):
        if (REPO / ".env").exists():
            self.skipTest(".env exists")
        result = self._run("publish_original.py", ["--text", "local probe"])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("YOUR_TYPEFULLY_API_KEY", result.stderr)
        self.assertNotIn("network blocked", result.stderr)
        self.assertNotIn("network blocked", result.stdout)

    def test_reply_draft_exits_before_network(self):
        if (REPO / ".env").exists():
            self.skipTest(".env exists")
        result = self._run(
            "create_reply_draft.py",
            ["--text", "local probe", "--reply-to", "https://x.com/example/status/1"],
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("YOUR_TYPEFULLY_API_KEY", result.stderr)
        self.assertNotIn("network blocked", result.stderr)


class RuntimeSourceTests(unittest.TestCase):
    def test_safe_runtime_has_no_publish_client(self):
        runtime = REPO / "safe-runtime" / "runtime"
        banned = ("urllib.request", "api.typefully.com", "api.x.com", "requests", "http.client", "playwright", "made_with_ai")
        for path in runtime.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in banned:
                self.assertNotIn(token, text, f"{path.name} contains {token}")


if __name__ == "__main__":
    unittest.main()
