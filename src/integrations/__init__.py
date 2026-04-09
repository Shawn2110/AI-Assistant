"""Integration tools for the AI Assistant.

Each integration exposes LangChain @tool-decorated functions
that the LangGraph agent can call.
"""

from src.integrations.system.apps import get_system_tools


def get_all_tools() -> list:
    """Collect all enabled integration tools."""
    tools = []

    # System tools are always available
    tools.extend(get_system_tools())

    return tools
