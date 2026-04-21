"""End-to-end integration tests for the router + AssistantAgent.

The LLM is fully mocked - these tests assert graph behavior, not model
quality. Each tool echoes its args into its return string, so assertions
on the response text also verify dispatch arguments.

Covers the spec's acceptance criteria:

- "open spotify" resolves via regex, direct-tool dispatch, no LLM call.
- "summarize my last 5 emails" falls through to the ReAct agent.
- Regex-tier latency stays under 100ms.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from src.ai.agent import AssistantAgent
from src.ai.router import IntentRouter
from src.core.config import AIConfig, ProviderConfig, RouterConfig, Settings


# ─── Tool fixtures - each echoes args so assertions on response verify dispatch ──

@tool
def open_application(name: str) -> str:
    """Open an application."""
    return f"Opened {name}."


@tool
def close_application(name: str) -> str:
    """Close an application."""
    return f"Closed {name}."


@tool
def set_volume(level: int) -> str:
    """Set system volume."""
    return f"Volume set to {level}."


@tool
def power_control(action: str) -> str:
    """Execute a power action."""
    return f"Power action: {action}."


@tool
def set_reminder(message: str, minutes: int = 0) -> str:
    """Set a reminder."""
    return f"Reminder: '{message}' in {minutes}m."


@tool
def get_system_info() -> str:
    """Return system info."""
    return "System info here."


# ─── Helpers ────────────────────────────────────────────────────────

def _make_settings() -> Settings:
    """Settings with a fake 'mock' provider enabled, so the agent will try it."""
    return Settings(
        ai=AIConfig(active_provider="mock", fallback_chain=[]),
        providers={
            "mock": ProviderConfig(
                enabled=True, model="mock-1", api_key_env="",
            ),
        },
        router=RouterConfig(enabled=True, classifier_enabled=False),
    )


def _make_agent(tools: list, react_response: str = "LLM response"):
    """Build an AssistantAgent whose ReAct path returns a canned AIMessage."""
    settings = _make_settings()
    agent = AssistantAgent(
        settings=settings,
        tools=tools,
        router=IntentRouter(config=settings.router),
    )

    # Replace _get_llm so ReAct path never touches a real provider.
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=react_response))
    agent._get_llm = lambda provider_name=None: mock_llm  # type: ignore[assignment]
    return agent, mock_llm


# ─── Tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_open_spotify_uses_regex_and_skips_llm():
    agent, mock_llm = _make_agent([open_application])
    response = await agent.chat("open spotify", provider="mock")
    assert response == "Opened spotify."
    mock_llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_regex_latency_under_100ms():
    agent, _ = _make_agent([open_application])

    # Warm up: first call includes graph compile + any lazy loading.
    await agent.chat("open spotify", provider="mock")

    t0 = time.perf_counter()
    await agent.chat("open chrome", provider="mock")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 100, f"Regex tier took {elapsed_ms:.1f}ms"


@pytest.mark.asyncio
async def test_unknown_command_falls_through_to_react():
    agent, mock_llm = _make_agent([], react_response="Here's your summary.")
    response = await agent.chat("summarize my last 5 emails", provider="mock")
    assert response == "Here's your summary."
    mock_llm.ainvoke.assert_called()


@pytest.mark.asyncio
async def test_close_app_dispatches_to_tool():
    agent, mock_llm = _make_agent([close_application])
    response = await agent.chat("close spotify", provider="mock")
    assert response == "Closed spotify."
    mock_llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_volume_intent_extracts_level():
    agent, _ = _make_agent([set_volume])

    resp1 = await agent.chat("volume to 80", provider="mock")
    assert resp1 == "Volume set to 80."

    resp2 = await agent.chat("mute", provider="mock")
    assert resp2 == "Volume set to 0."


@pytest.mark.asyncio
async def test_power_intent_extracts_action():
    agent, _ = _make_agent([power_control])
    response = await agent.chat("lock", provider="mock")
    assert response == "Power action: lock."


@pytest.mark.asyncio
async def test_reminder_intent_extracts_message_and_minutes():
    agent, _ = _make_agent([set_reminder])
    response = await agent.chat("remind me to call dave in 10 minutes", provider="mock")
    assert "call dave" in response
    assert "10m" in response


@pytest.mark.asyncio
async def test_get_time_handled_inline_without_tool():
    """get_time has no tool - the agent formats the response directly."""
    agent, mock_llm = _make_agent([])
    response = await agent.chat("what time is it", provider="mock")
    assert "time is" in response.lower()
    mock_llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_missing_tool_returns_friendly_error():
    """Router picks open_app but the open_application tool isn't registered."""
    agent, mock_llm = _make_agent([])
    response = await agent.chat("open spotify", provider="mock")
    assert "open_application" in response or "not available" in response.lower()
    mock_llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_router_disabled_always_uses_react():
    """When router.enabled=false every command reaches the LLM."""
    settings = _make_settings()
    settings.router.enabled = False
    agent = AssistantAgent(settings=settings, tools=[open_application])

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="ReAct handled it."))
    agent._get_llm = lambda provider_name=None: mock_llm  # type: ignore[assignment]

    response = await agent.chat("open spotify", provider="mock")
    assert response == "ReAct handled it."
    mock_llm.ainvoke.assert_called()
