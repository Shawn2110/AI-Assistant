"""APScheduler wrapper that runs enabled workflows on their cron schedules.

Scheduler lifecycle is owned by the daemon:

    daemon starts -> WorkflowScheduler.start()
                       |
                       v
                  BackgroundScheduler registers one CronTrigger per
                  enabled workflow whose schedule != "manual"
                       |
                       v
    at trigger time -> manager.run_now(id, sandbox)

When a workflow fails, we log the event and optionally fire a Windows
toast notification via the `on_failure` callback the daemon injects.
"""

from __future__ import annotations

from typing import Callable

from src.core.logger import get_logger
from src.workflows.manager import WorkflowManager, WorkflowRunResult
from src.workflows.sandbox import Sandbox

log = get_logger(__name__)


class WorkflowScheduler:
    """Schedules enabled workflows via APScheduler's BackgroundScheduler."""

    def __init__(
        self,
        manager: WorkflowManager,
        sandbox: Sandbox | None = None,
        on_failure: Callable[[str, WorkflowRunResult], None] | None = None,
        on_success: Callable[[str, WorkflowRunResult], None] | None = None,
    ):
        self.manager = manager
        self.sandbox = sandbox or Sandbox()
        self.on_failure = on_failure
        self.on_success = on_success
        self._scheduler = None

    # ─── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        """Create the scheduler and register every enabled workflow."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError:
            log.warning("workflow.scheduler.apscheduler_missing")
            return

        self._scheduler = BackgroundScheduler()
        self._register_all()
        self._scheduler.start()
        log.info("workflow.scheduler.started", jobs=len(self._scheduler.get_jobs()))

    def stop(self, wait: bool = False) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=wait)
            self._scheduler = None
            log.info("workflow.scheduler.stopped")

    # ─── Job management ────────────────────────────────────────────

    def _register_all(self) -> None:
        from apscheduler.triggers.cron import CronTrigger

        assert self._scheduler is not None
        for w in self.manager.list():
            if not w.enabled or w.schedule == "manual":
                continue
            try:
                trigger = CronTrigger.from_crontab(w.schedule)
            except Exception as e:
                log.warning(
                    "workflow.scheduler.bad_schedule",
                    id=w.id, schedule=w.schedule, error=str(e),
                )
                continue
            self._scheduler.add_job(
                self._run_workflow,
                trigger=trigger,
                args=[w.id],
                id=w.id,
                replace_existing=True,
            )

    def reload(self) -> None:
        """Re-sync scheduled jobs with the current index (call after create/delete)."""
        if self._scheduler is None:
            return
        self._scheduler.remove_all_jobs()
        self._register_all()

    def _run_workflow(self, workflow_id: str) -> None:
        """APScheduler entrypoint for a single workflow execution."""
        try:
            result = self.manager.run_now(workflow_id, sandbox=self.sandbox)
        except Exception as e:
            log.error("workflow.scheduler.run_crashed", id=workflow_id, error=str(e))
            return

        log.info(
            "workflow.scheduler.ran",
            id=workflow_id, status=result.status,
        )
        if result.status == "failed" and self.on_failure:
            try:
                self.on_failure(workflow_id, result)
            except Exception as e:
                log.warning("workflow.scheduler.on_failure_error", error=str(e))
        elif result.status == "success" and self.on_success:
            try:
                self.on_success(workflow_id, result)
            except Exception as e:
                log.warning("workflow.scheduler.on_success_error", error=str(e))
