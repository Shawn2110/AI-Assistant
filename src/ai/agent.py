"""LangGraph agent - the brain of the AI Assistant.

Uses a ReAct-style agent graph:
  User message → AI thinks → calls tools if needed → responds
"""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from src.ai.providers import create_provider
from src.core.config import Settings, get_settings
from src.core.exceptions import ProviderError
from src.core.logger import get_logger

log = get_logger(__name__)


class AgentState(TypedDict):
    """State that flows through the LangGraph agent."""

    messages: Annotated[list[BaseMessage], add_messages]
    provider_name: str


class AssistantAgent:
    """The main AI assistant agent powered by LangGraph."""

    def __init__(self, settings: Settings | None = None, tools: list | None = None):
        self.settings = settings or get_settings()
        self.tools = tools or []
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
        """Build the LangGraph agent graph."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("agent", self._agent_node)
        if self.tools:
            graph.add_node("tools", ToolNode(self.tools))

        # Add edges
        graph.add_edge(START, "agent")

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

    async def _agent_node(self, state: AgentState) -> dict[str, Any]:
        """The AI thinking node - processes messages and decides what to do."""
        llm = self._get_llm(state.get("provider_name"))

        # Add system message with persona
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            system_msg = SystemMessage(content=self.settings.persona.get_system_prompt())
            messages = [system_msg] + messages

        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    def _should_use_tools(self, state: AgentState) -> str:
        """Decide whether the agent should call tools or finish."""
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return "end"

    @property
    def graph(self):
        """Lazy-build and cache the compiled graph."""
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    async def chat(self, message: str, provider: str | None = None) -> str:
        """Send a message and get a response.

        Args:
            message: The user's message text.
            provider: Optional provider override (e.g., "claude" for coding tasks).

        Returns:
            The assistant's text response.
        """
        state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "provider_name": provider or self._provider_name or "",
        }

        # Try active provider, then fallback chain
        providers_to_try = [provider] if provider else []
        if not providers_to_try:
            active = self.settings.ai.active_provider
            if active:
                providers_to_try.append(active)
            providers_to_try.extend(self.settings.ai.fallback_chain)

        # Deduplicate while preserving order
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
        """Stream a response token by token.

        Yields partial text chunks as they arrive.
        """
        state: AgentState = {
            "messages": [HumanMessage(content=message)],
            "provider_name": provider or self.settings.ai.active_provider or "",
        }

        async for event in self.graph.astream_events(state, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    yield chunk.content
