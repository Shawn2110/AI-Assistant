"""LangGraph agent - the brain of the AI Assistant.

Architecture (post-router):

    START -> route -> { direct_tool (tier=regex|classifier) -> END
                      | agent (tier=react) -> [tools -> agent]* -> END }

The router is a cheap fast-path in front of the existing ReAct agent.
Most trivial commands ("open spotify", "what time is it") never reach
the LLM. Anything ambiguous falls through to the existing ReAct loop.
"""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import NotRequired, TypedDict

from src.ai.providers import create_provider
from src.ai.router import IntentRouter, RoutingDecision
from src.core.config import Settings, get_settings
from src.core.exceptions import ProviderError
from src.core.logger import get_logger

log = get_logger(__name__)


class AgentState(TypedDict):
    """State that flows through the LangGraph agent."""

    messages: Annotated[list[BaseMessage], add_messages]
    provider_name: str
    routing: NotRequired[RoutingDecision | None]


class AssistantAgent:
    """The main AI assistant agent powered by LangGraph."""

    def __init__(
        self,
        settings: Settings | None = None,
        tools: list | None = None,
        router: IntentRouter | None = None,
    ):
        self.settings = settings or get_settings()
        self.tools = tools or []
        self._tools_by_name = {getattr(t, "name", None): t for t in self.tools}
        self.router = router or IntentRouter(config=self.settings.router)
        self._graph = None
        self._llm = None
        self._provider_name = None

    def _get_llm(self, provider_name: str | None = None):
        """Get the LLM for the given provider, or the active provider."""
        if provider_name and provider_name == self._provider_name and self._llm:
            return self._llm

        name = provider_name
        if not name:
            name, _ = self.settings.get_provider_for_task()

        all_provs = self.settings.all_providers
        config = all_provs[name]
        self._llm = create_provider(name, config)
        self._provider_name = name

        # Bind tools if available
        if self.tools:
            self._llm = self._llm.bind_tools(self.tools)

        log.info("ai.provider.loaded", provider=name, model=config.model)
        return self._llm

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph agent graph with router in front."""
        graph = StateGraph(AgentState)

        graph.add_node("route", self._route_node)
        graph.add_node("direct_tool", self._direct_tool_node)
        graph.add_node("agent", self._agent_node)
        if self.tools:
            graph.add_node("tools", ToolNode(self.tools))

        graph.add_edge(START, "route")
        graph.add_conditional_edges(
            "route",
            self._route_branch,
            {"direct_tool": "direct_tool", "agent": "agent"},
        )
        graph.add_edge("direct_tool", END)

        if self.tools:
            graph.add_conditional_edges(
                "agent",
                self._should_use_tools,
                {"tools": "tools", "end": END},
            )
            graph.add_edge("tools", "agent")
        else:
            graph.add_edge("agent", END)

        return graph.compile()

    # ─── Router nodes ──────────────────────────────────────────────

    def _route_node(self, state: AgentState) -> dict[str, Any]:
        """Run the intent router on the latest user message."""
        text = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                text = msg.content if isinstance(msg.content, str) else ""
                break
        decision = self.router.route(text)
        return {"routing": decision}

    def _route_branch(self, state: AgentState) -> str:
        decision = state.get("routing")
        if decision is None or decision.tier == "react":
            return "agent"
        return "direct_tool"

    def _direct_tool_node(self, state: AgentState) -> dict[str, Any]:
        """Execute a tier-0/tier-1 intent directly, no LLM."""
        decision = state.get("routing")
        assert decision is not None, "direct_tool_node requires a routing decision"
        try:
            text = _execute_intent(decision, self._tools_by_name)
        except Exception as e:
            log.warning(
                "agent.direct_tool.failed",
                intent=decision.intent, error=str(e),
            )
            text = f"I couldn't complete that: {e}"
        return {"messages": [AIMessage(content=text)]}

    # ─── ReAct nodes (unchanged behavior) ──────────────────────────

    async def _agent_node(self, state: AgentState) -> dict[str, Any]:
        """The AI thinking node - processes messages and decides what to do."""
        llm = self._get_llm(state.get("provider_name"))

        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            system_msg = SystemMessage(content=self.settings.persona.get_system_prompt())
            messages = [system_msg] + messages

        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    def _should_use_tools(self, state: AgentState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return "end"

    @property
    def graph(self):
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    async def chat(self, message: str, provider: str | None = None) -> str:
        """Send a message and get a response."""
        state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "provider_name": provider or self._provider_name or "",
            "routing": None,
        }

        providers_to_try = [provider] if provider else []
        if not providers_to_try:
            active = self.settings.ai.active_provider
            if active:
                providers_to_try.append(active)
            providers_to_try.extend(self.settings.ai.fallback_chain)

        seen = set()
        unique_providers = []
        for p in providers_to_try:
            if p and p not in seen:
                seen.add(p)
                unique_providers.append(p)

        last_error = None
        for prov in unique_providers:
            if prov not in self.settings.providers:
                continue
            if not self.settings.providers[prov].enabled:
                continue

            try:
                state["provider_name"] = prov
                result = await self.graph.ainvoke(state)
                last_msg = result["messages"][-1]
                return last_msg.content
            except Exception as e:
                last_error = e
                log.warning("ai.provider.failed", provider=prov, error=str(e))
                continue

        raise ProviderError(
            "all",
            f"All providers failed. Last error: {last_error}",
        )

    async def stream(self, message: str, provider: str | None = None):
        """Stream a response token by token."""
        state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "provider_name": provider or self.settings.ai.active_provider or "",
            "routing": None,
        }

        async for event in self.graph.astream_events(state, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    yield chunk.content


# ─── Intent dispatch ───────────────────────────────────────────────

def _execute_intent(decision: RoutingDecision, tools_by_name: dict[str, Any]) -> str:
    """Dispatch a router decision to the appropriate tool or inline handler.

    Returns the response text to send back to the user.
    """
    intent = decision.intent
    params = decision.params or {}

    if intent == "open_app":
        return _invoke(tools_by_name, "open_application", {"name": params["app"]})
    if intent == "close_app":
        return _invoke(tools_by_name, "close_application", {"name": params["app"]})
    if intent == "set_volume":
        return _invoke(tools_by_name, "set_volume", {"level": params["level"]})
    if intent == "power":
        return _invoke(tools_by_name, "power_control", {"action": params["action"]})
    if intent == "set_reminder":
        return _invoke(
            tools_by_name, "set_reminder",
            {"message": params["message"], "minutes": params.get("minutes", 0)},
        )
    if intent == "system_status":
        return _invoke(tools_by_name, "get_system_info", {})
    if intent == "get_time":
        from datetime import datetime
        return datetime.now().strftime("The time is %I:%M %p.")
    if intent == "get_date":
        from datetime import date
        return date.today().strftime("Today is %A, %B %d, %Y.")
    if intent == "create_workflow":
        return _create_workflow(params.get("description", ""))

    return f"I recognized the intent '{intent}' but don't know how to handle it yet."


def _create_workflow(description: str) -> str:
    """Voice-triggered workflow creation. Returns a human-friendly confirmation."""
    if not description:
        return "Tell me what the workflow should do."
    try:
        from pathlib import Path

        from src.ai.providers import create_provider
        from src.core.config import get_settings
        from src.workflows.generator import WorkflowGenerator
        from src.workflows.manager import WorkflowManager
    except ImportError as e:
        return f"Workflow support isn't installed: {e}"

    settings = get_settings()

    def llm_factory():
        name, config = settings.get_provider_for_task()
        return create_provider(name, config)

    try:
        manager = WorkflowManager(
            workflows_dir=Path("workflows"),
            generator=WorkflowGenerator(llm_factory=llm_factory),
        )
        w = manager.create(description)
    except Exception as e:
        log.warning("agent.create_workflow.failed", error=str(e))
        return f"I couldn't create that workflow: {e}"

    return (
        f"Workflow '{w.id}' created. Run it now with 'workflow run {w.id}' "
        f"or add a schedule with 'workflow create ... --schedule ...'."
    )


def _invoke(tools_by_name: dict[str, Any], tool_name: str, args: dict[str, Any]) -> str:
    tool = tools_by_name.get(tool_name)
    if tool is None:
        return f"Tool '{tool_name}' is not available."
    result = tool.invoke(args)
    return str(result) if result is not None else ""
