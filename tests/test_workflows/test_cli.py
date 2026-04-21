"""Smoke tests for `assistant workflow ...` subcommands.

These exercise the dispatch surface end-to-end with a tmp workflows dir
and an in-process fake generator. Nothing hits the LLM.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.workflows import cli as workflow_cli


class _FakeGenerator:
    SCRIPT = (
        "def run():\n"
        "    return {'status': 'success', 'output': 'hi', 'error': None}\n"
    )

    def generate(self, description: str) -> str:
        return self.SCRIPT


@pytest.fixture
def wf_dir(tmp_path: Path, monkeypatch):
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(workflow_cli, "WORKFLOWS_DIR", tmp_path)

    def _make_manager():
        from src.workflows.manager import WorkflowManager
        return WorkflowManager(workflows_dir=tmp_path, generator=_FakeGenerator())

    monkeypatch.setattr(workflow_cli, "_make_manager", _make_manager)
    return tmp_path


class TestListEmpty:
    def test_list_empty_prints_hint(self, wf_dir, capsys):
        rc = workflow_cli.main(["list"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "No workflows" in out


class TestCreate:
    def test_create_writes_script(self, wf_dir, capsys):
        rc = workflow_cli.main(["create", "summarize my week"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Created workflow" in out
        assert any(wf_dir.glob("*.py"))

    def test_create_with_schedule(self, wf_dir, capsys):
        rc = workflow_cli.main([
            "create", "post a monday digest", "--schedule", "0 9 * * MON",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "schedule" in out.lower()


class TestList:
    def test_list_shows_created(self, wf_dir, capsys):
        workflow_cli.main(["create", "task one"])
        workflow_cli.main(["create", "task two"])
        capsys.readouterr()  # drain

        rc = workflow_cli.main(["list"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "task_one" in out
        assert "task_two" in out


class TestRun:
    def test_run_executes_script(self, wf_dir, capsys):
        workflow_cli.main(["create", "hello"])
        capsys.readouterr()
        # Patch sandbox to avoid subprocess overhead
        with patch("src.workflows.cli.Sandbox", autospec=False) if False else patch.object(  # noqa: SIM108
            __import__("src.workflows.sandbox", fromlist=["Sandbox"]), "Sandbox"
        ) as MockSandbox:
            MockSandbox.return_value.execute.return_value = {
                "status": "success", "output": "ran", "error": None,
            }
            rc = workflow_cli.main(["run", "hello"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "success" in out.lower()


class TestEnableDisable:
    def test_disable_then_enable(self, wf_dir, capsys):
        workflow_cli.main(["create", "toggle"])
        capsys.readouterr()

        rc = workflow_cli.main(["disable", "toggle"])
        assert rc == 0

        rc = workflow_cli.main(["enable", "toggle"])
        assert rc == 0


class TestDelete:
    def test_delete_removes(self, wf_dir, capsys):
        workflow_cli.main(["create", "goner"])
        capsys.readouterr()

        rc = workflow_cli.main(["delete", "goner"])
        assert rc == 0

        # Now list shows nothing
        rc = workflow_cli.main(["list"])
        assert "No workflows" in capsys.readouterr().out

    def test_delete_unknown(self, wf_dir, capsys):
        rc = workflow_cli.main(["delete", "never_existed"])
        assert rc == 1


class TestLogs:
    def test_no_logs_yet(self, wf_dir, capsys):
        workflow_cli.main(["create", "empty"])
        capsys.readouterr()

        rc = workflow_cli.main(["logs", "empty"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "No logs" in out


class TestRegenerate:
    def test_regenerate_rewrites_script(self, wf_dir, capsys):
        workflow_cli.main(["create", "v1_task"])
        capsys.readouterr()

        rc = workflow_cli.main(["regenerate", "v1_task"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Regenerated" in out
