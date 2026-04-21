"""CLI entry point for the AI Assistant."""

from __future__ import annotations

import argparse
import asyncio
import sys

from src.core.config import get_settings, reload_settings
from src.core.exceptions import AssistantError
from src.core.logger import get_logger, setup_logging

log = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="assistant",
        description="AI Assistant - your personal AI helper",
    )
    parser.add_argument(
        "message",
        nargs="*",
        help="Send a message directly (e.g., assistant what time is it)",
    )
    parser.add_argument(
        "--voice", action="store_true", help="Start in voice mode (wake word + mic)"
    )
    parser.add_argument(
        "--server", action="store_true", help="Start the API server for phone access"
    )
    parser.add_argument(
        "--setup", action="store_true", help="Interactive setup wizard"
    )
    parser.add_argument(
        "--provider", type=str, default=None,
        help="Override AI provider (groq, gemini, ollama, claude, openai)",
    )
    parser.add_argument(
        "--explain-routing", type=str, default=None, metavar="COMMAND",
        help="Print the intent router's decision for COMMAND and exit",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    return parser.parse_args()


def _create_agent():
    """Create the assistant agent with all enabled tools."""
    from src.ai.agent import AssistantAgent
    from src.integrations import get_all_tools

    settings = get_settings()
    tools = get_all_tools()
    return AssistantAgent(settings=settings, tools=tools)


async def run_chat(message: str, provider: str | None = None) -> str:
    """Send a single message and get a response."""
    agent = _create_agent()
    return await agent.chat(message, provider=provider)


async def run_interactive(provider: str | None = None) -> None:
    """Run an interactive chat loop."""
    settings = get_settings()
    agent = _create_agent()

    persona = settings.persona
    name = persona.name

    # Persona greeting
    print(f"\n  {persona.get_greeting()}")
    print(f"  {persona.tagline}")

    # Show active provider
    active = settings.ai.active_provider
    if active and active in settings.all_providers:
        model = settings.all_providers[active].model
        print(f"  [{active}: {model}]")
    print("\n  Type your message, or 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{name}: {persona.get_farewell()}")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print(f"\n{name}: {persona.get_farewell()}")
            break

        try:
            response = await agent.chat(user_input, provider=provider)
            print(f"\n{name}: {response}\n")
        except AssistantError as e:
            print(f"\n[!]Error: {e}\n")
        except Exception as e:
            log.error("chat.error", error=str(e))
            print(f"\n[!]Unexpected error: {e}\n")


def main():
    # Intercept subcommands before the default argparse (which treats any
    # positional as a chat message). Subcommands get their own parser.
    argv = sys.argv[1:]
    if argv and argv[0] == "workflow":
        from src.workflows.cli import main as workflow_main
        setup_logging("INFO")
        sys.exit(workflow_main(argv[1:]))

    args = parse_args()
    setup_logging("DEBUG" if args.verbose else "INFO")

    if args.setup:
        from src.core.setup import run_setup
        run_setup()
        reload_settings()
        return

    if args.explain_routing:
        from src.ai.router import IntentRouter
        settings = get_settings()
        router = IntentRouter(config=settings.router)
        decision = router.route(args.explain_routing)
        print(decision.explain())
        return

    if args.voice:
        from src.voice.start import start_voice
        start_voice(provider=args.provider)
        return

    if args.server:
        print("Server mode coming soon! (Phase 3)")
        return

    if args.message:
        # Single message mode
        message = " ".join(args.message)
        try:
            response = asyncio.run(run_chat(message, provider=args.provider))
            print(response)
        except AssistantError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Interactive mode
        asyncio.run(run_interactive(provider=args.provider))


if __name__ == "__main__":
    main()
