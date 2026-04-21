"""Tests for the subprocess sandbox.

These tests actually launch real Python subprocesses. They're fast
(small scripts, short timeouts) but they do write to tmp files.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.workflows.sandbox import ENV_ALLOWLIST, Sandbox


@pytest.fixture
def sandbox_dir(tmp_path: Path) -> Path:
    d = tmp_path / "workflows"
    d.mkdir()
    (d / "logs").mkdir()
    return d


def _write_script(dir: Path, name: str, body: str) -> Path:
    p = dir / f"{name}.py"
    p.write_text(body, encoding="utf-8")
    return p


class TestSuccessfulRun:
    def test_success_returns_parsed_result(self, sandbox_dir):
        script = _write_script(
            sandbox_dir, "happy",
            "def run():\n"
            "    return {'status': 'success', 'output': 'hello', 'error': None}\n",
        )
        result = Sandbox(logs_dir=sandbox_dir / "logs").execute(script)
        assert result == {"status": "success", "output": "hello", "error": None}

    def test_writes_log_file(self, sandbox_dir):
        script = _write_script(
            sandbox_dir, "logged",
            "def run():\n"
            "    print('some stdout')\n"
            "    return {'status': 'success', 'output': '', 'error': None}\n",
        )
        Sandbox(logs_dir=sandbox_dir / "logs").execute(script)
        log_dir = sandbox_dir / "logs" / "logged"
        assert log_dir.is_dir()
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1
        content = log_files[0].read_text(encoding="utf-8")
        assert "some stdout" in content


class TestFailure:
    def test_exception_in_run_marks_failed(self, sandbox_dir):
        script = _write_script(
            sandbox_dir, "boom",
            "def run():\n"
            "    raise RuntimeError('pop')\n",
        )
        result = Sandbox(logs_dir=sandbox_dir / "logs").execute(script)
        assert result["status"] == "failed"
        assert "pop" in (result.get("error") or "")

    def test_missing_run_function(self, sandbox_dir):
        script = _write_script(
            sandbox_dir, "no_run",
            "x = 1\n",
        )
        result = Sandbox(logs_dir=sandbox_dir / "logs").execute(script)
        assert result["status"] == "failed"

    def test_non_dict_return_marks_failed(self, sandbox_dir):
        script = _write_script(
            sandbox_dir, "bad_return",
            "def run():\n"
            "    return 'not a dict'\n",
        )
        result = Sandbox(logs_dir=sandbox_dir / "logs").execute(script)
        assert result["status"] == "failed"

    def test_syntax_error_marks_failed(self, sandbox_dir):
        script = _write_script(
            sandbox_dir, "bad_syntax",
            "def run(\n",
        )
        result = Sandbox(logs_dir=sandbox_dir / "logs").execute(script)
        assert result["status"] == "failed"


class TestTimeout:
    def test_timeout_returns_failed(self, sandbox_dir):
        script = _write_script(
            sandbox_dir, "slow",
            "import time\n"
            "def run():\n"
            "    time.sleep(10)\n"
            "    return {'status': 'success', 'output': '', 'error': None}\n",
        )
        t0 = time.monotonic()
        result = Sandbox(logs_dir=sandbox_dir / "logs").execute(script, timeout=2)
        elapsed = time.monotonic() - t0

        assert result["status"] == "failed"
        assert "timeout" in (result.get("error") or "").lower()
        # Generous upper bound - subprocess spin-up + teardown
        assert elapsed < 8, f"Sandbox took {elapsed:.1f}s, expected near 2s"


class TestEnvAllowlist:
    def test_allowed_var_passes_through(self, sandbox_dir, monkeypatch):
        monkeypatch.setenv("PATH", "/fake/path")
        script = _write_script(
            sandbox_dir, "env_path",
            "import os\n"
            "def run():\n"
            "    return {'status': 'success', 'output': os.environ.get('PATH',''), 'error': None}\n",
        )
        result = Sandbox(logs_dir=sandbox_dir / "logs").execute(script)
        assert result["status"] == "success"
        assert "/fake/path" in result["output"]

    def test_non_allowlisted_var_is_filtered(self, sandbox_dir, monkeypatch):
        monkeypatch.setenv("TOP_SECRET", "leaked_value")
        script = _write_script(
            sandbox_dir, "env_leak",
            "import os\n"
            "def run():\n"
            "    return {'status': 'success', 'output': os.environ.get('TOP_SECRET','<unset>'), 'error': None}\n",
        )
        result = Sandbox(logs_dir=sandbox_dir / "logs").execute(script)
        assert result["status"] == "success"
        assert result["output"] == "<unset>"

    def test_allowlist_covers_home_and_path(self):
        for required in ("PATH", "USERPROFILE", "HOME", "TEMP"):
            assert required in ENV_ALLOWLIST


class TestLogLocation:
    def test_default_log_location_is_sibling_of_script(self, tmp_path):
        wf = tmp_path / "workflows"
        wf.mkdir()
        script = _write_script(
            wf, "inline",
            "def run():\n"
            "    return {'status': 'success', 'output': '', 'error': None}\n",
        )
        Sandbox().execute(script)
        assert (wf / "logs" / "inline").is_dir()
