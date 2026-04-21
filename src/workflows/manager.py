"""Workflow registry and lifecycle management.

The manager owns the on-disk workflow store:

    workflows/
        index.json          -- serialized list of Workflow records
        <slug>.py           -- generated Python scripts
        logs/<slug>/...     -- per-run log files (written by sandbox)

`index.json` is the single source of truth for what workflows exist.
Scripts on disk without an index entry are ignored; index entries whose
script file is missing surface as a warning when the manager loads.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from src.core.logger import get_logger

log = get_logger(__name__)

WorkflowStatus = Literal["success", "failed", "never", "skipped"]


class Workflow(BaseModel):
    id: str
    description: str
    script_path: Path
    schedule: str = "manual"
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_run: datetime | None = None
    last_status: WorkflowStatus | None = "never"


class WorkflowRunResult(BaseModel):
    status: Literal["success", "failed", "skipped"]
    output: str = ""
    error: str | None = None
    ran_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GeneratorProtocol(Protocol):
    def generate(self, description: str) -> str: ...


class SandboxProtocol(Protocol):
    def execute(self, script_path: Path, timeout: int = 60) -> dict[str, Any]: ...


# ─── Helpers ────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, max_len: int = 40) -> str:
    """Collapse arbitrary text into a URL-safe lowercase slug."""
    s = _SLUG_RE.sub("_", text.lower().strip()).strip("_")
    if not s:
        s = "workflow"
    return s[:max_len]


# ─── Manager ────────────────────────────────────────────────────────

class WorkflowManager:
    """CRUD + execute over persistent workflows."""

    INDEX_FILE = "index.json"

    def __init__(
        self,
        workflows_dir: Path,
        generator: GeneratorProtocol,
    ):
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        (self.workflows_dir / "logs").mkdir(exist_ok=True)
        self.generator = generator
        self._index_path = self.workflows_dir / self.INDEX_FILE
        self._index: dict[str, Workflow] = self._load_index()

    # ─── Persistence ───────────────────────────────────────────────

    def _load_index(self) -> dict[str, Workflow]:
        if not self._index_path.exists():
            return {}
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            log.warning("workflow.index.corrupt", error=str(e))
            return {}
        out: dict[str, Workflow] = {}
        for entry in raw.get("workflows", []):
            try:
                w = Workflow.model_validate(entry)
                out[w.id] = w
            except Exception as e:
                log.warning("workflow.index.invalid_entry", error=str(e))
        return out

    def _save_index(self) -> None:
        data = {
            "version": 1,
            "workflows": [json.loads(w.model_dump_json()) for w in self._index.values()],
        }
        self._index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ─── CRUD ──────────────────────────────────────────────────────

    def _allocate_id(self, description: str) -> str:
        base = _slugify(description)
        if base not in self._index:
            return base
        i = 2
        while f"{base}_{i}" in self._index:
            i += 1
        return f"{base}_{i}"

    def create(self, description: str, schedule: str | None = None) -> Workflow:
        """Generate a script from `description` and register the workflow."""
        wid = self._allocate_id(description)
        script = self.generator.generate(description)
        script_path = self.workflows_dir / f"{wid}.py"
        script_path.write_text(script, encoding="utf-8")

        w = Workflow(
            id=wid,
            description=description,
            script_path=script_path,
            schedule=schedule or "manual",
        )
        self._index[wid] = w
        self._save_index()
        log.info("workflow.created", id=wid, schedule=w.schedule)
        return w

    def list(self) -> list[Workflow]:
        return list(self._index.values())

    def get(self, workflow_id: str) -> Workflow:
        if workflow_id not in self._index:
            raise KeyError(workflow_id)
        return self._index[workflow_id]

    def enable(self, workflow_id: str) -> None:
        w = self.get(workflow_id)
        w.enabled = True
        self._index[workflow_id] = w
        self._save_index()

    def disable(self, workflow_id: str) -> None:
        w = self.get(workflow_id)
        w.enabled = False
        self._index[workflow_id] = w
        self._save_index()

    def delete(self, workflow_id: str) -> None:
        w = self.get(workflow_id)
        if w.script_path.exists():
            w.script_path.unlink()
        log_dir = self.workflows_dir / "logs" / workflow_id
        if log_dir.exists():
            shutil.rmtree(log_dir, ignore_errors=True)
        del self._index[workflow_id]
        self._save_index()
        log.info("workflow.deleted", id=workflow_id)

    def regenerate(self, workflow_id: str, feedback: str | None = None) -> Workflow:
        """Re-run the generator on the original description, keeping the id."""
        w = self.get(workflow_id)
        description = w.description
        if feedback:
            description = f"{description}\n\nAdditional feedback: {feedback}"
        script = self.generator.generate(description)
        w.script_path.write_text(script, encoding="utf-8")
        self._save_index()
        log.info("workflow.regenerated", id=workflow_id)
        return w

    # ─── Execution ─────────────────────────────────────────────────

    def run_now(
        self,
        workflow_id: str,
        sandbox: SandboxProtocol,
        timeout: int = 60,
    ) -> WorkflowRunResult:
        """Execute a workflow synchronously via the sandbox."""
        w = self.get(workflow_id)

        if not w.enabled:
            return WorkflowRunResult(status="skipped", output="", error="workflow disabled")

        result_dict = sandbox.execute(w.script_path, timeout=timeout)
        status = result_dict.get("status", "failed")
        if status not in ("success", "failed"):
            status = "failed"

        result = WorkflowRunResult(
            status=status,  # type: ignore[arg-type]
            output=str(result_dict.get("output", "")),
            error=result_dict.get("error"),
        )

        w.last_run = result.ran_at
        w.last_status = result.status
        self._index[workflow_id] = w
        self._save_index()
        return result
