"""`assistant workflow ...` CLI subcommands.

Invoked by `src.cli.main` when ``sys.argv[1] == "workflow"``. Each
subcommand is a thin wrapper over ``WorkflowManager`` — keep logic out
of here so the manager stays unit-testable.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.core.config import get_settings
from src.core.logger import get_logger

log = get_logger(__name__)

WORKFLOWS_DIR = Path("workflows")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assistant workflow",
        description="Manage code-as-policy workflows",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Create a new workflow from a description")
    p_create.add_argument("description", help="Natural-language description")
    p_create.add_argument(
        "--schedule", default=None,
        help="Cron expression for recurrence, e.g. '0 9 * * MON' (default: manual)",
    )

    sub.add_parser("list", help="List all workflows with status")

    p_run = sub.add_parser("run", help="Run a workflow now (one-shot)")
    p_run.add_argument("id", help="Workflow id")
    p_run.add_argument(
        "--timeout", type=int, default=60,
        help="Wall-clock timeout in seconds (default: 60)",
    )

    for name, help_ in (
        ("enable", "Enable a workflow"),
        ("disable", "Disable a workflow"),
        ("delete", "Delete a workflow and its script"),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("id", help="Workflow id")

    p_regen = sub.add_parser(
        "regenerate", help="Re-run the generator for an existing workflow",
    )
    p_regen.add_argument("id", help="Workflow id")
    p_regen.add_argument("--feedback", default=None, help="Optional feedback for the generator")

    p_logs = sub.add_parser("logs", help="Show the most recent run log for a workflow")
    p_logs.add_argument("id", help="Workflow id")
    p_logs.add_argument(
        "-n", "--lines", type=int, default=50,
        help="Tail N lines from the most recent log (default: 50)",
    )

    return parser


def _make_manager():
    from src.ai.providers import create_provider
    from src.workflows.generator import WorkflowGenerator
    from src.workflows.manager import WorkflowManager

    settings = get_settings()

    def llm_factory():
        name, config = settings.get_provider_for_task()
        return create_provider(name, config)

    return WorkflowManager(
        workflows_dir=WORKFLOWS_DIR,
        generator=WorkflowGenerator(llm_factory=llm_factory),
    )


def _format_row(w) -> str:
    enabled = "on " if w.enabled else "off"
    status = w.last_status or "never"
    last = w.last_run.strftime("%Y-%m-%d %H:%M") if w.last_run else "-"
    return f"  {w.id:<30}  {enabled}  {status:<7}  last={last}  schedule={w.schedule}"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    manager = _make_manager()

    if args.cmd == "create":
        try:
            w = manager.create(args.description, schedule=args.schedule)
        except Exception as e:
            print(f"Failed to create workflow: {e}", file=sys.stderr)
            return 1
        print(f"Created workflow '{w.id}' -> {w.script_path}")
        if w.schedule != "manual":
            print(f"  schedule: {w.schedule}  (will run when daemon is up)")
        return 0

    if args.cmd == "list":
        workflows = manager.list()
        if not workflows:
            print("No workflows. Create one with `assistant workflow create \"...\"`.")
            return 0
        print(f"  {'ID':<30}  STATE  STATUS   LAST RUN          SCHEDULE")
        for w in workflows:
            print(_format_row(w))
        return 0

    if args.cmd == "run":
        from src.workflows.sandbox import Sandbox
        try:
            result = manager.run_now(args.id, sandbox=Sandbox(), timeout=args.timeout)
        except KeyError:
            print(f"No workflow with id '{args.id}'", file=sys.stderr)
            return 1
        print(f"Status: {result.status}")
        if result.output:
            print(f"Output: {result.output}")
        if result.error:
            print(f"Error:  {result.error}")
        return 0 if result.status == "success" else 1

    if args.cmd in ("enable", "disable"):
        try:
            getattr(manager, args.cmd)(args.id)
        except KeyError:
            print(f"No workflow with id '{args.id}'", file=sys.stderr)
            return 1
        print(f"{args.cmd}d '{args.id}'")
        return 0

    if args.cmd == "delete":
        try:
            manager.delete(args.id)
        except KeyError:
            print(f"No workflow with id '{args.id}'", file=sys.stderr)
            return 1
        print(f"Deleted '{args.id}'")
        return 0

    if args.cmd == "regenerate":
        try:
            w = manager.regenerate(args.id, feedback=args.feedback)
        except KeyError:
            print(f"No workflow with id '{args.id}'", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Regenerate failed: {e}", file=sys.stderr)
            return 1
        print(f"Regenerated '{w.id}' -> {w.script_path}")
        return 0

    if args.cmd == "logs":
        log_dir = WORKFLOWS_DIR / "logs" / args.id
        if not log_dir.is_dir():
            print(f"No logs for '{args.id}' yet.")
            return 0
        files = sorted(log_dir.glob("*.log"))
        if not files:
            print(f"No logs for '{args.id}' yet.")
            return 0
        latest = files[-1]
        print(f"--- {latest.name} ---")
        content = latest.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in content[-args.lines:]:
            print(line)
        return 0

    parser.error(f"unknown command: {args.cmd}")
    return 2
