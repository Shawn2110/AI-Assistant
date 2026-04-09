"""Interactive setup wizard for the AI Assistant."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

from src.core.config import CONFIG_DIR, ROOT_DIR


def run_setup() -> None:
    """Interactive setup wizard - choose AI provider and configure keys."""
    print("\n" + "=" * 55)
    print("   AI Assistant - Setup Wizard")
    print("=" * 55)

    config_path = CONFIG_DIR / "settings.yaml"
    env_path = ROOT_DIR / ".env"
    env_example = ROOT_DIR / ".env.example"

    # Load current settings
    with open(config_path) as f:
        settings = yaml.safe_load(f)

    providers = settings.get("providers", {})

    # Step 1: Create .env if it doesn't exist
    if not env_path.exists() and env_example.exists():
        shutil.copy(env_example, env_path)
        print("\n✅ Created .env file from .env.example")
    elif not env_path.exists():
        env_path.touch()
        print("\n✅ Created .env file")

    # Step 2: Choose AI provider
    print("\n── Choose your AI Provider ──────────────────────────\n")
    print("  Available providers:\n")

    provider_list = list(providers.keys())
    for i, (name, config) in enumerate(providers.items(), 1):
        tier = config.get("tier", "free").upper()
        desc = config.get("description", "")
        needs_key = config.get("api_key_env", "")
        key_status = ""
        if needs_key:
            has_key = bool(os.getenv(needs_key) or _env_has_key(env_path, needs_key))
            key_status = " ✅ key found" if has_key else " ❌ needs API key"
        elif name == "ollama":
            key_status = " (no key needed - runs locally)"

        print(f"  {i}. {name:<10} [{tier}] {desc}{key_status}")

    print()
    choice = _input_choice(
        f"  Select provider (1-{len(provider_list)}): ",
        range(1, len(provider_list) + 1),
    )
    chosen_name = provider_list[choice - 1]
    chosen_config = providers[chosen_name]

    # Step 3: Configure API key if needed
    api_key_env = chosen_config.get("api_key_env", "")
    if api_key_env:
        current_key = os.getenv(api_key_env) or _env_get_key(env_path, api_key_env)
        if current_key:
            print(f"\n  ✅ {api_key_env} is already set.")
            change = input("  Change it? (y/N): ").strip().lower()
            if change == "y":
                _set_api_key(env_path, api_key_env)
        else:
            print(f"\n  You need a {api_key_env} for {chosen_name}.")
            _show_key_instructions(chosen_name)
            _set_api_key(env_path, api_key_env)

    elif chosen_name == "ollama":
        print("\n  Ollama runs locally - no API key needed.")
        print("  Make sure Ollama is installed: https://ollama.com")
        model = chosen_config.get("model", "qwen3:8b")
        print(f"  Then run: ollama pull {model}")

    # Step 4: Update settings.yaml
    # Enable the chosen provider and set it as active
    settings["providers"][chosen_name]["enabled"] = True
    settings["ai"]["active_provider"] = chosen_name

    with open(config_path, "w") as f:
        yaml.dump(settings, f, default_flow_style=False, sort_keys=False)

    print(f"\n✅ Active provider set to: {chosen_name}")
    print(f"   Model: {chosen_config.get('model', 'default')}")

    # Step 5: Ask about additional providers
    print("\n── Additional Providers (optional) ─────────────────\n")
    setup_more = input("  Set up more providers for fallback/overrides? (y/N): ").strip().lower()
    if setup_more == "y":
        for name, config in providers.items():
            if name == chosen_name:
                continue
            add = input(f"  Enable {name} [{config.get('tier', 'free').upper()}]? (y/N): ").strip().lower()
            if add == "y":
                api_key_env = config.get("api_key_env", "")
                if api_key_env and not (os.getenv(api_key_env) or _env_get_key(env_path, api_key_env)):
                    _show_key_instructions(name)
                    _set_api_key(env_path, api_key_env)
                settings["providers"][name]["enabled"] = True

        with open(config_path, "w") as f:
            yaml.dump(settings, f, default_flow_style=False, sort_keys=False)

    # Done
    print("\n" + "=" * 55)
    print("   Setup complete! 🎉")
    print("=" * 55)
    print(f"\n  Run 'python -m src' to start chatting with {chosen_name}.")
    print("  Run 'python -m src --voice' for voice mode (coming soon).")
    print("  Run 'python -m src --setup' to change settings anytime.\n")


def _input_choice(prompt: str, valid_range: range) -> int:
    """Get a valid integer choice from the user."""
    while True:
        try:
            val = int(input(prompt).strip())
            if val in valid_range:
                return val
            print(f"  Please enter a number between {valid_range.start} and {valid_range.stop - 1}.")
        except ValueError:
            print("  Please enter a number.")


def _set_api_key(env_path: Path, key_name: str) -> None:
    """Prompt for and save an API key to .env."""
    key = input(f"  Enter your {key_name}: ").strip()
    if not key:
        print("  Skipped.")
        return

    # Read existing .env
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()

    # Update or append
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key_name}=") or line.startswith(f"# {key_name}="):
            lines[i] = f"{key_name}={key}"
            found = True
            break

    if not found:
        lines.append(f"{key_name}={key}")

    env_path.write_text("\n".join(lines) + "\n")
    print(f"  ✅ {key_name} saved to .env")


def _env_has_key(env_path: Path, key_name: str) -> bool:
    """Check if a key exists in .env (non-commented, non-empty)."""
    if not env_path.exists():
        return False
    for line in env_path.read_text().splitlines():
        if line.startswith(f"{key_name}="):
            value = line.split("=", 1)[1].strip()
            return bool(value) and not value.startswith("your_")
    return False


def _env_get_key(env_path: Path, key_name: str) -> str | None:
    """Get a key value from .env."""
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if line.startswith(f"{key_name}="):
            value = line.split("=", 1)[1].strip()
            if value and not value.startswith("your_"):
                return value
    return None


def _show_key_instructions(provider: str) -> None:
    """Show instructions for getting an API key."""
    instructions = {
        "groq": "  Get a free API key at: https://console.groq.com/keys",
        "gemini": "  Get a free API key at: https://aistudio.google.com/apikey",
        "claude": "  Get an API key at: https://console.anthropic.com/settings/keys",
        "openai": "  Get an API key at: https://platform.openai.com/api-keys",
    }
    msg = instructions.get(provider, "")
    if msg:
        print(msg)
