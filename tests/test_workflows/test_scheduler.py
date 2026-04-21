"""Tests for WorkflowScheduler — APScheduler wrapper."""

from __future__ import annotations

from pathlib import Path


from src.workflows.manager import Workflow, WorkflowRunResult
from src.workflows.scheduler import WorkflowScheduler


class _FakeManager:
    """Minimal manager stand-in — list() returns canned workflows, run_now records calls."""

    def __init__(self, workflows: list[Workflow]):
        self._workflows = {w.id: w for w in workflows}
        self.run_calls: list[str] = []
        self.next_result = WorkflowRunResult(status="success", output="", error=None)

    def list(self) -> list[Workflow]:
        return list(self._workflows.values())

    def run_now(self, workflow_id: str, sandbox=None, timeout=60) -> WorkflowRunResult:
        self.run_calls.append(workflow_id)
        return self.next_result


def _wf(id: str, schedule: str = "manual", enabled: bool = True) -> Workflow:
    return Workflow(
        id=id, description=f"desc-{id}",
        script_path=Path("/tmp/never-used.py"),
        schedule=schedule, enabled=enabled,
    )


class TestRegistration:
    def test_registers_only_scheduled_workflows(self):
        wfs = [
            _wf("scheduled_a", schedule="* * * * *"),
            _wf("manual_b", schedule="manual"),
            _wf("disabled_c", schedule="* * * * *", enabled=False),
        ]
        mgr = _FakeManager(wfs)
        sched = WorkflowScheduler(manager=mgr)
        sched.start()
        try:
            ids = {j.id for j in sched._scheduler.get_jobs()}
            assert ids == {"scheduled_a"}
        finally:
            sched.stop()

    def test_invalid_cron_is_skipped_not_crash(self):
        wfs = [
            _wf("good", schedule="0 9 * * *"),
            _wf("bad",  schedule="not-a-cron"),
        ]
        mgr = _FakeManager(wfs)
        sched = WorkflowScheduler(manager=mgr)
        sched.start()
        try:
            ids = {j.id for j in sched._scheduler.get_jobs()}
            assert ids == {"good"}
        finally:
            sched.stop()


class TestReload:
    def test_reload_replaces_jobs(self):
        wfs = [_wf("one", schedule="0 9 * * *")]
        mgr = _FakeManager(wfs)
        sched = WorkflowScheduler(manager=mgr)
        sched.start()
        try:
            assert {j.id for j in sched._scheduler.get_jobs()} == {"one"}
            mgr._workflows = {w.id: w for w in [_wf("two", schedule="0 9 * * *")]}
            sched.reload()
            assert {j.id for j in sched._scheduler.get_jobs()} == {"two"}
        finally:
            sched.stop()


class TestRunWorkflow:
    def test_calls_manager_run_now(self):
        mgr = _FakeManager([_wf("x", schedule="manual")])
        sched = WorkflowScheduler(manager=mgr)
        sched._run_workflow("x")
        assert mgr.run_calls == ["x"]

    def test_on_failure_fires_on_failed_result(self):
        mgr = _FakeManager([_wf("x", schedule="manual")])
        mgr.next_result = WorkflowRunResult(status="failed", error="boom")
        fires: list[tuple[str, WorkflowRunResult]] = []
        sched = WorkflowScheduler(
            manager=mgr,
            on_failure=lambda wid, r: fires.append((wid, r)),
        )
        sched._run_workflow("x")
        assert len(fires) == 1
        assert fires[0][0] == "x"
        assert fires[0][1].error == "boom"

    def test_on_success_fires_on_success_result(self):
        mgr = _FakeManager([_wf("x", schedule="manual")])
        mgr.next_result = WorkflowRunResult(status="success")
        fires: list[str] = []
        sched = WorkflowScheduler(
            manager=mgr,
            on_success=lambda wid, r: fires.append(wid),
        )
        sched._run_workflow("x")
        assert fires == ["x"]

    def test_on_failure_exception_does_not_propagate(self):
        mgr = _FakeManager([_wf("x", schedule="manual")])
        mgr.next_result = WorkflowRunResult(status="failed")
        def bad_cb(wid, r):
            raise RuntimeError("callback crashed")
        sched = WorkflowScheduler(manager=mgr, on_failure=bad_cb)
        # Must not raise
        sched._run_workflow("x")


class TestLifecycle:
    def test_start_and_stop(self):
        mgr = _FakeManager([])
        sched = WorkflowScheduler(manager=mgr)
        sched.start()
        assert sched._scheduler is not None
        sched.stop()
        assert sched._scheduler is None
        # Idempotent stop
        sched.stop()

    def test_stop_without_start_is_noop(self):
        sched = WorkflowScheduler(manager=_FakeManager([]))
        sched.stop()  # must not raise
