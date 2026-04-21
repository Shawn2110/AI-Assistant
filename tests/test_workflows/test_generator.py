"""Tests for the workflow code generator + validator.

The generator produces Python source via an LLM. The validator is the
security-critical layer: before any generated code hits disk or runs in
the sandbox, it must be parsed and screened. The validator is pure and
tested here without any LLM calls.
"""

from __future__ import annotations

import pytest

from src.workflows.generator import (
    GeneratorValidationError,
    WorkflowGenerator,
    strip_code_fences,
    validate_script,
)


class TestStripFences:
    def test_unwrapped_unchanged(self):
        src = "def run():\n    pass\n"
        assert strip_code_fences(src) == src

    def test_removes_python_fence(self):
        src = "```python\ndef run():\n    pass\n```\n"
        out = strip_code_fences(src)
        assert "```" not in out
        assert "def run()" in out

    def test_removes_plain_fence(self):
        src = "```\nx = 1\n```"
        assert strip_code_fences(src).strip() == "x = 1"


class TestValidateScriptHappy:
    def test_minimal_valid_script_passes(self):
        src = (
            "def run():\n"
            "    return {'status': 'success', 'output': '', 'error': None}\n"
        )
        validate_script(src)  # must not raise

    def test_whitelisted_imports_ok(self):
        src = (
            "import datetime\n"
            "import json\n"
            "import os\n"
            "import requests\n"
            "def run():\n"
            "    return {'status': 'success', 'output': '', 'error': None}\n"
        )
        validate_script(src)

    def test_src_integrations_import_ok(self):
        src = (
            "from src.integrations.system.apps import open_application\n"
            "def run():\n"
            "    return {'status': 'success', 'output': '', 'error': None}\n"
        )
        validate_script(src)


class TestValidateScriptRejects:
    def test_missing_run_function(self):
        src = "x = 1\n"
        with pytest.raises(GeneratorValidationError, match="run"):
            validate_script(src)

    def test_syntax_error(self):
        src = "def run(:\n"
        with pytest.raises(GeneratorValidationError, match="syntax"):
            validate_script(src)

    @pytest.mark.parametrize("banned", [
        "import subprocess",
        "from subprocess import Popen",
        "import socket",
        "import ctypes",
        "import pickle",
        "import shutil",
        "import importlib",
    ])
    def test_banned_imports_rejected(self, banned):
        src = f"{banned}\ndef run():\n    return {{'status': 'success', 'output': '', 'error': None}}\n"
        with pytest.raises(GeneratorValidationError, match=r"(?i)banned|import"):
            validate_script(src)

    @pytest.mark.parametrize("banned_call", [
        "eval('1+1')",
        "exec('x=1')",
        "compile('x=1','<s>','exec')",
        "__import__('os')",
        "open('/etc/passwd').read()",
    ])
    def test_banned_calls_rejected(self, banned_call):
        src = (
            "def run():\n"
            f"    {banned_call}\n"
            "    return {'status': 'success', 'output': '', 'error': None}\n"
        )
        with pytest.raises(GeneratorValidationError):
            validate_script(src)

    def test_rejects_long_scripts(self):
        body = "\n".join(f"x{i} = {i}" for i in range(200))
        src = f"{body}\ndef run():\n    return {{'status': 'success', 'output': '', 'error': None}}\n"
        with pytest.raises(GeneratorValidationError, match=r"(?i)length|lines"):
            validate_script(src)


class TestGeneratorWithFakeLLM:
    class _FakeLLM:
        def __init__(self, content: str):
            self.content = content
            self.calls: list[str] = []

        def invoke(self, prompt):
            self.calls.append(str(prompt))
            from langchain_core.messages import AIMessage
            return AIMessage(content=self.content)

    def test_generate_strips_fences_and_validates(self):
        llm = self._FakeLLM(
            "```python\n"
            "import json\n"
            "def run():\n"
            "    return {'status': 'success', 'output': 'hi', 'error': None}\n"
            "```"
        )
        gen = WorkflowGenerator(llm_factory=lambda: llm, tool_docs="(none)")
        out = gen.generate("say hi once")
        assert "```" not in out
        assert "def run()" in out
        assert llm.calls and "say hi once" in llm.calls[0]

    def test_generate_rejects_banned_output(self):
        llm = self._FakeLLM(
            "import subprocess\n"
            "def run():\n"
            "    return {'status': 'success', 'output': '', 'error': None}\n"
        )
        gen = WorkflowGenerator(llm_factory=lambda: llm, tool_docs="(none)")
        with pytest.raises(GeneratorValidationError):
            gen.generate("malicious idea")
