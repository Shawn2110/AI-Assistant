"""Subprocess sandbox for running generated workflow scripts.

Each run:
  - launches `python <script>` in a subprocess (never in-process)
  - applies a wall-clock timeout (default 60s)
  - passes only a small, explicit allowlist of env vars
  - captures stdout + stderr to `workflows/logs/<id>/<timestamp>.log`
  - parses the final JSON status line that the script's run() should print

The generator-side contract: every generated script's `run()` returns a
dict `{status, output, error}`, and the script's entry point prints that
dict as JSON to stdout on the final line. The sandbox parses that and
returns it to the caller.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.logger import get_logger

log = get_logger(__name__)


# Env vars that are safe to forward. Keep this list short and explicit.
ENV_ALLOWLIST = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "HOMEDRIVE",
    "HOMEPATH",
    "LANG",
    "LC_ALL",
    "PYTHONPATH",
    "PYTHONUTF8",
}


class Sandbox:
    """Run generated workflow scripts in an isolated subprocess."""

    def __init__(self, logs_dir: Path | None = None, python_exe: str | None = None):
        self.python_exe = python_exe or sys.executable
        # Logs default to <project>/workflows/logs; callers can override for tests.
        self.logs_dir = Path(logs_dir) if logs_dir else None

    def _log_path(self, script_path: Path) -> Path:
        base = self.logs_dir or (script_path.parent / "logs")
        wf_dir = base / script_path.stem
        wf_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return wf_dir / f"{ts}.log"

    def _build_env(self) -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if k in ENV_ALLOWLIST}

    def execute(self, script_path: Path, timeout: int = 60) -> dict[str, Any]:
        """Run `script_path` and return {status, output, error}."""
        script_path = Path(script_path)
        log_path = self._log_path(script_path)

        entry = (
            "import json, sys\n"
            "try:\n"
            f"    sys.path.insert(0, {str(script_path.parent)!r})\n"
            "    from runpy import run_path\n"
            f"    mod = run_path({str(script_path)!r})\n"
            "    result = mod['run']() if 'run' in mod else None\n"
            "    if not isinstance(result, dict):\n"
            "        result = {'status': 'failed', 'output': '', "
            "'error': 'run() did not return a dict'}\n"
            "    print('__WF_RESULT__' + json.dumps(result))\n"
            "except Exception as e:\n"
            "    print('__WF_RESULT__' + json.dumps({"
            "'status': 'failed', 'output': '', 'error': repr(e)}))\n"
        )

        try:
            proc = subprocess.run(
                [self.python_exe, "-c", entry],
                capture_output=True, text=True, timeout=timeout,
                env=self._build_env(), cwd=str(script_path.parent),
            )
        except subprocess.TimeoutExpired:
            log.warning("workflow.sandbox.timeout", script=str(script_path), timeout=timeout)
            log_path.write_text(
                f"TIMEOUT after {timeout}s\n", encoding="utf-8",
            )
            return {"status": "failed", "output": "", "error": f"timeout after {timeout}s"}

        # Persist full captured output to the per-run log.
        log_path.write_text(
            f"=== STDOUT ===\n{proc.stdout}\n=== STDERR ===\n{proc.stderr}\n",
            encoding="utf-8",
        )

        parsed = _parse_result(proc.stdout)
        if parsed is not None:
            return parsed

        return {
            "status": "failed",
            "output": proc.stdout,
            "error": proc.stderr.strip() or "no result returned",
        }


_RESULT_RE = re.compile(r"^__WF_RESULT__(.+)$", re.MULTILINE)


def _parse_result(stdout: str) -> dict[str, Any] | None:
    """Pull the final `__WF_RESULT__<json>` line out of captured stdout."""
    matches = _RESULT_RE.findall(stdout)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None
