"""Code-as-policy workflows.

Recurring or multi-step automations are generated once as Python scripts
and then executed deterministically — no LLM in the run-loop. The LLM
only gets called again if the user asks to regenerate or patch a script.

Public API:
    WorkflowManager  - CRUD + execute workflows
    Workflow         - pydantic model for a single workflow
    WorkflowScheduler - APScheduler-backed cron scheduler
"""

from src.workflows.manager import Workflow, WorkflowManager, WorkflowRunResult
from src.workflows.scheduler import WorkflowScheduler

__all__ = [
    "Workflow",
    "WorkflowManager",
    "WorkflowRunResult",
    "WorkflowScheduler",
]
