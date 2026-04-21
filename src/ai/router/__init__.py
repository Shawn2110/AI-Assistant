"""Intent router - a three-tier fast-path in front of the ReAct agent.

Tier 0: regex patterns      -> direct tool call, no LLM
Tier 1: embedding classifier -> direct tool call, no LLM
Tier 2: fallback             -> existing LangGraph ReAct agent
"""

from src.ai.router.router import IntentRouter, RoutingDecision

__all__ = ["IntentRouter", "RoutingDecision"]
