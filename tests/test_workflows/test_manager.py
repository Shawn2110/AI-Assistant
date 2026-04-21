"""Tests for WorkflowManager — the persistent registry + run orchestration."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.workflows.manager import Workflow, WorkflowManager


@pytest.fixture
def workflows_dir(tmp_path: Path) -> Path:
    (tmp_path / "logs").mkdir()
    return tmp_path


@pytest.fixture
def manager(workflows_dir: Path) -> WorkflowManager:
    return WorkflowManager(workflows_dir=workflows_dir, generator=_FakeGenerator())


# ─── Fakes ──────────────────────────────────────────────────────────

class _FakeGenerator:
    """Generates a no-op script that just returns success."""

    SCRIPT = (
        "def run():\n"
        "    return {'status': 'success', 'output': 'ok', 'error': None}\n"
    )

    def generate(self, description: str) -> str:
        return self.SCRIPT


class _FakeSandbox:
    def __init__(self, status: str = "success"):
        self.status = status
        self.calls: list[Path] = []

    def execute(self, script_path: Path, timeout: int = 60) -> dict:
        self.calls.append(script_path)
        return {"status": self.status, "output": "", "error": None}


# ─── Tests ──────────────────────────────────────────────────────────

class TestCreate:
    def test_creates_workflow_with_slug(self, manager):
        w = manager.create("remind me to drink water every hour")
        assert isinstance(w, Workflow)
        assert w.id
        assert w.description.startswith("remind me")
        assert w.last_status == "never"

    def test_writes_script_file(self, manager, workflows_dir):
        w = manager.create("summarize my calendar weekly")
        assert w.script_path.exists()
        assert w.script_path.parent == workflows_dir

    def test_registers_workflow_in_index(self, manager):
        w = manager.create("morning standup reminder")
        listed = manager.list()
        assert any(x.id == w.id for x in listed)

    def test_collision_resolves_with_suffix(self, manager):
        w1 = manager.create("daily digest")
        w2 = manager.create("daily digest")
        assert w1.id != w2.id

    def test_explicit_schedule_stored(self, manager):
        w = manager.create("weekly report", schedule="0 9 * * MON")
        assert w.schedule == "0 9 * * MON"

    def test_default_schedule_is_manual(self, manager):
        w = manager.create("one-shot task")
        assert w.schedule == "manual"


class TestList:
    def test_empty_when_nothing_created(self, manager):
        assert manager.list() == []

    def test_persists_across_instances(self, workflows_dir):
        m1 = WorkflowManager(workflows_dir=workflows_dir, generator=_FakeGenerator())
        m1.create("task one")
        m1.create("task two")

        m2 = WorkflowManager(workflows_dir=workflows_dir, generator=_FakeGenerator())
        assert len(m2.list()) == 2


class TestGet:
    def test_returns_workflow(self, manager):
        w = manager.create("find me")
        found = manager.get(w.id)
        assert found.id == w.id

    def test_missing_raises(self, manager):
        with pytest.raises(KeyError):
            manager.get("does-not-exist")


class TestEnableDisable:
    def test_disable_then_enable(self, manager):
        w = manager.create("toggle me")
        assert w.enabled is True

        manager.disable(w.id)
        assert manager.get(w.id).enabled is False

        manager.enable(w.id)
        assert manager.get(w.id).enabled is True


class TestDelete:
    def test_removes_workflow_and_script(self, manager):
        w = manager.create("delete me")
        script_path = w.script_path
        assert script_path.exists()

        manager.delete(w.id)

        assert script_path.exists() is False
        with pytest.raises(KeyError):
            manager.get(w.id)


class TestRunNow:
    def test_updates_last_run_and_status_on_success(self, manager, workflows_dir):
        w = manager.create("run me")
        sandbox = _FakeSandbox(status="success")
        result = manager.run_now(w.id, sandbox=sandbox)

        assert result.status == "success"
        after = manager.get(w.id)
        assert after.last_status == "success"
        assert isinstance(after.last_run, datetime)

    def test_marks_failure(self, manager):
        w = manager.create("will fail")
        sandbox = _FakeSandbox(status="failed")
        manager.run_now(w.id, sandbox=sandbox)
        assert manager.get(w.id).last_status == "failed"

    def test_disabled_workflow_does_not_run(self, manager):
        w = manager.create("disabled")
        manager.disable(w.id)
        sandbox = _FakeSandbox()
        result = manager.run_now(w.id, sandbox=sandbox)
        assert result.status == "skipped"
        assert sandbox.calls == []


class TestRegenerate:
    def test_replaces_script_keeps_id(self, manager):
        w = manager.create("v1")
        original_id = w.id
        w2 = manager.regenerate(w.id)
        assert w2.id == original_id
        assert w2.script_path.exists()
