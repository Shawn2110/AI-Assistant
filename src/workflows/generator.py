"""LLM-backed workflow script generator with strict validation.

Flow:

    description  -->  LLM  -->  source code
                                    |
                                    v
                     strip_code_fences (``` removal)
                                    |
                                    v
                     validate_script (ast parse + whitelist)
                                    |
                             (raises on violation)
                                    |
                                    v
                               source code

The validator is pure. Every generated script is required to:

1. Parse as valid Python.
2. Define a top-level `run()` callable.
3. Only import from an explicit module allowlist.
4. Avoid banned calls (``eval``, ``exec``, ``compile``, ``open``,
   ``__import__``).
5. Stay under a configurable line count (default 150).

Violations raise ``GeneratorValidationError`` and the script never
reaches disk.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Callable

from src.core.logger import get_logger

log = get_logger(__name__)


class GeneratorValidationError(ValueError):
    """Raised when generated code fails security / correctness checks."""


# ─── Policy ────────────────────────────────────────────────────────

ALLOWED_IMPORT_PREFIXES = (
    "os",
    "os.path",
    "sys",
    "json",
    "datetime",
    "pathlib",
    "re",
    "math",
    "time",
    "collections",
    "itertools",
    "functools",
    "typing",
    "dataclasses",
    "requests",
    "urllib",
    "urllib.parse",
    "urllib.request",
    "src.integrations",
)

BANNED_IMPORT_PREFIXES = (
    "subprocess",
    "socket",
    "ctypes",
    "pickle",
    "shutil",
    "importlib",
    "multiprocessing",
    "threading",
    "asyncio",
    "builtins",
)

BANNED_CALLS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "input",
}

MAX_SCRIPT_LINES = 150


# ─── Fence stripping ───────────────────────────────────────────────

_FENCE_RE = re.compile(r"^```(?:python)?\n(.*?)\n```\s*$", re.DOTALL)


def strip_code_fences(text: str) -> str:
    """Remove a single surrounding ```python ... ``` fence if present."""
    t = text.strip()
    m = _FENCE_RE.match(t)
    if m:
        return m.group(1)
    return text


# ─── Validator ─────────────────────────────────────────────────────

def validate_script(source: str) -> None:
    """Raise ``GeneratorValidationError`` if `source` violates policy."""
    lines = source.splitlines()
    if len(lines) > MAX_SCRIPT_LINES:
        raise GeneratorValidationError(
            f"script exceeds max length of {MAX_SCRIPT_LINES} lines ({len(lines)} given)"
        )

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise GeneratorValidationError(f"syntax error: {e}") from e

    _check_has_run(tree)
    _check_imports(tree)
    _check_calls(tree)


def _check_has_run(tree: ast.Module) -> None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run":
            return
    raise GeneratorValidationError("script must define a top-level `run()` function")


def _import_module_allowed(module: str) -> bool:
    if any(module == p or module.startswith(p + ".") for p in BANNED_IMPORT_PREFIXES):
        return False
    return any(module == p or module.startswith(p + ".") for p in ALLOWED_IMPORT_PREFIXES)


def _check_imports(tree: ast.Module) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _import_module_allowed(alias.name):
                    raise GeneratorValidationError(
                        f"banned or non-whitelisted import: {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if not _import_module_allowed(mod):
                raise GeneratorValidationError(
                    f"banned or non-whitelisted import from: {mod}"
                )


def _check_calls(tree: ast.Module) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name and name in BANNED_CALLS:
                raise GeneratorValidationError(f"banned call: {name}()")


# ─── Generator ─────────────────────────────────────────────────────

PROMPT_TEMPLATE = """\
You are generating a Python script for a personal assistant workflow.

REQUIREMENTS
- Define a top-level function ``run()`` that returns a dict:
  ``{{"status": "success" | "failed", "output": str, "error": str | None}}``.
- Import ONLY from: {allowed_imports}.
- Never use ``subprocess``, ``eval``, ``exec``, ``compile``, ``open``, or ``__import__``.
- Handle your own errors - never let an exception escape ``run()``.
- Keep the total script under {max_lines} lines.
- Use the ``logging`` standard library via ``import logging; logger = logging.getLogger(__name__)``
  for any progress messages.

AVAILABLE TOOLS (for reference - import as shown):
{tool_docs}

USER REQUEST:
{description}

Return only the Python code. No markdown fences. No commentary. No prose.
"""


class WorkflowGenerator:
    """Generate + validate a workflow script for a natural-language request."""

    def __init__(
        self,
        llm_factory: Callable[[], Any],
        tool_docs: str = "",
        max_lines: int = MAX_SCRIPT_LINES,
    ):
        self.llm_factory = llm_factory
        self.tool_docs = tool_docs or "(no tools available)"
        self.max_lines = max_lines

    def _build_prompt(self, description: str) -> str:
        return PROMPT_TEMPLATE.format(
            allowed_imports=", ".join(ALLOWED_IMPORT_PREFIXES),
            max_lines=self.max_lines,
            tool_docs=self.tool_docs,
            description=description.strip(),
        )

    def generate(self, description: str) -> str:
        llm = self.llm_factory()
        prompt = self._build_prompt(description)
        log.info("workflow.generator.invoke", description=description[:80])
        response = llm.invoke(prompt)
        raw = getattr(response, "content", response)
        if not isinstance(raw, str):
            raw = str(raw)
        source = strip_code_fences(raw)
        validate_script(source)
        return source
