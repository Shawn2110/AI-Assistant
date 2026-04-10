"""Comprehensive CLI setup wizard for the AI Assistant.

Walks the user through:
  1. AI Provider selection and API keys
  2. Integration selection and credentials
  3. Voice automation rules
  4. Provider-per-task assignment
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

from src.core.config import CONFIG_DIR, ROOT_DIR

# --- Integration metadata ------------------------------------------

INTEGRATION_INFO = {
    "system": {
        "label": "System Control",
        "description": "Open/close apps, file management, power control, volume, reminders",
        "auth_type": "none",
        "requires_keys": [],
        "capabilities": [
            "open_app", "close_app", "shutdown", "restart", "sleep", "lock",
            "set_volume", "list_files", "search_files", "set_reminder",
            "system_info", "run_command",
        ],
    },
    "google": {
        "label": "Google Suite",
        "description": "Gmail, Google Calendar, Google Drive",
        "auth_type": "oauth",
        "requires_keys": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
        "oauth_config": {
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": [
                "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/drive",
            ],
        },
        "capabilities": [
            "read_email", "send_email", "search_email",
            "create_event", "list_events", "update_event",
            "upload_file", "download_file", "search_drive",
        ],
    },
    "microsoft": {
        "label": "Microsoft 365",
        "description": "Outlook, Teams, OneDrive",
        "auth_type": "oauth",
        "requires_keys": ["MS_CLIENT_ID", "MS_CLIENT_SECRET"],
        "oauth_config": {
            "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "scopes": [
                "Mail.ReadWrite", "Calendars.ReadWrite", "Files.ReadWrite.All",
                "Chat.ReadWrite", "User.Read", "offline_access",
            ],
        },
        "capabilities": [
            "read_outlook", "send_outlook", "search_outlook",
            "create_teams_message", "list_teams_channels",
            "upload_onedrive", "download_onedrive",
        ],
    },
    "telegram": {
        "label": "Telegram",
        "description": "Send/receive messages, manage chats",
        "auth_type": "bot_token",
        "requires_keys": ["TELEGRAM_BOT_TOKEN"],
        "auto_setup": {
            "instructions": "I'll open Telegram BotFather. Create a bot and paste the token.",
            "url": "https://t.me/BotFather",
        },
        "capabilities": [
            "send_telegram", "read_telegram", "reply_telegram",
        ],
    },
    "discord": {
        "label": "Discord",
        "description": "Send/receive messages, manage servers",
        "auth_type": "bot_token",
        "requires_keys": ["DISCORD_BOT_TOKEN"],
        "auto_setup": {
            "instructions": "I'll open Discord Developer Portal. Create an app, add a bot, and paste the token.",
            "url": "https://discord.com/developers/applications",
        },
        "capabilities": [
            "send_discord", "read_discord", "reply_discord",
        ],
    },
    "whatsapp": {
        "label": "WhatsApp",
        "description": "Send/receive messages via WhatsApp",
        "auth_type": "oauth",
        "requires_keys": ["WHATSAPP_API_TOKEN"],
        "oauth_config": {
            "auth_uri": "https://www.facebook.com/v18.0/dialog/oauth",
            "token_uri": "https://graph.facebook.com/v18.0/oauth/access_token",
            "scopes": ["whatsapp_business_messaging", "whatsapp_business_management"],
        },
        "capabilities": [
            "send_whatsapp", "read_whatsapp", "reply_whatsapp",
        ],
    },
    "instagram": {
        "label": "Instagram",
        "description": "Read DMs, reply to messages, check notifications, view posts",
        "auth_type": "oauth",
        "requires_keys": ["INSTAGRAM_ACCESS_TOKEN"],
        "oauth_config": {
            "auth_uri": "https://www.instagram.com/oauth/authorize",
            "token_uri": "https://api.instagram.com/oauth/access_token",
            "scopes": [
                "instagram_basic", "instagram_manage_messages",
                "instagram_manage_comments",
            ],
        },
        "capabilities": [
            "read_instagram_dms", "reply_instagram_dm", "get_instagram_notifications",
            "list_instagram_posts", "get_instagram_comments", "reply_instagram_comment",
        ],
    },
    "slack": {
        "label": "Slack",
        "description": "Messages, reminders, channel management, notifications",
        "auth_type": "oauth",
        "requires_keys": ["SLACK_BOT_TOKEN"],
        "oauth_config": {
            "auth_uri": "https://slack.com/oauth/v2/authorize",
            "token_uri": "https://slack.com/api/oauth.v2.access",
            "scopes": [
                "chat:write", "channels:read", "channels:history",
                "reminders:write", "users:read", "im:history",
            ],
        },
        "capabilities": [
            "send_slack", "read_slack", "set_slack_reminder",
            "list_slack_channels", "slack_status",
        ],
    },
    "figma": {
        "label": "Figma",
        "description": "View projects, export assets, read/write comments",
        "auth_type": "oauth",
        "requires_keys": ["FIGMA_ACCESS_TOKEN"],
        "oauth_config": {
            "auth_uri": "https://www.figma.com/oauth",
            "token_uri": "https://api.figma.com/v1/oauth/token",
            "scopes": ["files:read", "file_comments:write"],
        },
        "capabilities": [
            "list_figma_projects", "get_figma_file", "export_figma_assets",
            "read_figma_comments", "post_figma_comment",
        ],
    },
    "browser": {
        "label": "Browser Automation",
        "description": "Web search, navigate pages, fill forms, extract data",
        "auth_type": "none",
        "requires_keys": [],
        "capabilities": [
            "web_search", "open_url", "fill_form", "screenshot_page",
            "extract_page_text",
        ],
    },
}

# --- Voice automation presets ---------------------------------------

VOICE_AUTOMATION_PRESETS = {
    "reply_messages": {
        "label": "Auto-reply to messages",
        "description": "When you say 'reply to [name]', the assistant reads the latest "
                       "message and drafts a reply for your approval",
        "trigger": "reply to *",
        "requires_integrations": ["telegram", "discord", "whatsapp", "slack"],
        "action": "read_latest_message ->draft_reply ->confirm ->send",
    },
    "morning_briefing": {
        "label": "Morning briefing",
        "description": "Say 'good morning' to hear your calendar, unread emails, "
                       "and pending Slack messages",
        "trigger": "good morning | morning briefing",
        "requires_integrations": ["google", "microsoft", "slack"],
        "action": "read_calendar_today ->count_unread_email ->summarize_slack ->speak",
    },
    "slack_reminder": {
        "label": "Set Slack reminders by voice",
        "description": "Say 'remind me on slack to [task] at [time]' to create a Slack reminder",
        "trigger": "remind me on slack *",
        "requires_integrations": ["slack"],
        "action": "parse_time ->create_slack_reminder",
    },
    "send_message": {
        "label": "Send messages by voice",
        "description": "Say 'send a message to [person] on [platform] saying [text]'",
        "trigger": "send * message to * on * saying *",
        "requires_integrations": ["telegram", "discord", "whatsapp", "slack"],
        "action": "resolve_contact ->compose_message ->confirm ->send",
    },
    "email_summary": {
        "label": "Email summary",
        "description": "Say 'summarize my emails' to hear a summary of unread emails",
        "trigger": "summarize my emails | check my email | any new emails",
        "requires_integrations": ["google", "microsoft"],
        "action": "fetch_unread ->summarize_with_ai ->speak",
    },
    "system_control": {
        "label": "System control by voice",
        "description": "Say 'open chrome', 'shutdown in 10 minutes', 'set volume to 50'",
        "trigger": "open * | close * | shutdown * | restart * | volume *",
        "requires_integrations": ["system"],
        "action": "parse_command ->execute_system_tool",
    },
    "figma_updates": {
        "label": "Figma project updates",
        "description": "Say 'check figma comments' to hear new comments on your designs",
        "trigger": "check figma * | figma comments | figma updates",
        "requires_integrations": ["figma"],
        "action": "fetch_recent_comments ->summarize ->speak",
    },
    "focus_mode": {
        "label": "Focus mode",
        "description": "Say 'focus mode' to mute Slack notifications, set status to busy, "
                       "and block distracting apps",
        "trigger": "focus mode | do not disturb | dnd",
        "requires_integrations": ["slack", "system"],
        "action": "set_slack_dnd ->update_slack_status ->close_distracting_apps",
    },
    "meeting_prep": {
        "label": "Meeting preparation",
        "description": "Say 'prepare for my next meeting' to get agenda, attendees, and "
                       "relevant documents",
        "trigger": "prepare for * meeting | next meeting | meeting prep",
        "requires_integrations": ["google", "microsoft"],
        "action": "get_next_event ->list_attendees ->find_related_docs ->speak_summary",
    },
    "end_of_day": {
        "label": "End of day wrap-up",
        "description": "Say 'wrap up' to get a summary of today's activity and set "
                       "reminders for tomorrow",
        "trigger": "wrap up | end of day | eod",
        "requires_integrations": ["google", "microsoft", "slack"],
        "action": "summarize_today ->list_tomorrow_events ->speak",
    },
}


# --- Main setup flow -----------------------------------------------

def run_setup() -> None:
    """Full interactive setup wizard."""
    config_path = CONFIG_DIR / "settings.yaml"
    env_path = ROOT_DIR / ".env"
    env_example = ROOT_DIR / ".env.example"

    with open(config_path) as f:
        settings = yaml.safe_load(f)

    # Ensure .env exists
    if not env_path.exists():
        if env_example.exists():
            shutil.copy(env_example, env_path)
        else:
            env_path.touch()

    _print_banner()

    # Main menu loop
    while True:
        print("\n-- Main Menu ---------------------------------------\n")
        print("  1. Persona            -Name and personality of your assistant")
        print("  2. AI Provider        -Choose which AI to use")
        print("  3. Add Custom AI      -Add any open-source model server")
        print("  4. Integrations       -Connect apps and services")
        print("  5. Voice Automations  -Set up voice command workflows")
        print("  6. Task Routing       -Assign different AIs to different tasks")
        print("  7. View Config        -Show current configuration")
        print("  8. Done               -Save and exit setup")
        print()

        choice = _input_choice("  Select (1-8): ", range(1, 9))

        match choice:
            case 1:
                _setup_persona(settings)
            case 2:
                _setup_providers(settings, env_path)
            case 3:
                _add_custom_provider(settings, env_path)
            case 4:
                _setup_integrations(settings, env_path)
            case 5:
                _setup_voice_automations(settings)
            case 6:
                _setup_task_routing(settings)
            case 7:
                _show_config(settings)
            case 8:
                break

    # Save final config
    with open(config_path, "w") as f:
        yaml.dump(settings, f, default_flow_style=False, sort_keys=False)

    _print_finish(settings)


# --- Section 0: Persona -------------------------------------------

TONE_PRESETS = {
    "professional-witty": {
        "label": "Professional & Witty (Jarvis-style)",
        "personality": (
            "You are {name}, a personal AI assistant. "
            "You speak in a professional yet witty tone, similar to Jarvis from Iron Man. "
            "You are efficient, slightly formal, but show personality through dry humor "
            "and clever observations. You address the user respectfully and always stay "
            "focused on getting things done. You keep responses concise unless detail is "
            "requested. When executing tasks, you confirm actions briefly and report results "
            "clearly. You never say 'as an AI' or break character."
        ),
        "greeting": "Good {time_of_day}. {name} online. How can I assist you?",
        "farewell": "Until next time. {name} signing off.",
        "tagline": "At your service.",
    },
    "friendly": {
        "label": "Friendly & Warm",
        "personality": (
            "You are {name}, a friendly personal AI assistant. "
            "You're warm, approachable, and enthusiastic. You talk like a helpful friend "
            "who genuinely enjoys helping out. You use casual language, occasionally crack "
            "jokes, and celebrate wins with the user. You keep things simple and clear. "
            "You never say 'as an AI' or break character."
        ),
        "greeting": "Hey! {name} here. What's up?",
        "farewell": "Catch you later! {name} out.",
        "tagline": "Happy to help!",
    },
    "formal": {
        "label": "Formal & Precise",
        "personality": (
            "You are {name}, a formal personal AI assistant. "
            "You communicate with precision, clarity, and professionalism. "
            "You use proper grammar, avoid slang, and present information in a "
            "structured manner. You are thorough but never verbose. "
            "You never say 'as an AI' or break character."
        ),
        "greeting": "Good {time_of_day}. {name} at your disposal.",
        "farewell": "Session concluded. {name} standing by.",
        "tagline": "Precision in every response.",
    },
    "casual": {
        "label": "Casual & Chill",
        "personality": (
            "You are {name}, a laid-back personal AI assistant. "
            "You keep it super chill and conversational. You use casual language, "
            "contractions, and a relaxed tone. You're helpful but never stiff. "
            "Think of yourself as the user's tech-savvy buddy. "
            "You never say 'as an AI' or break character."
        ),
        "greeting": "Yo, {name} here. What do you need?",
        "farewell": "Later! {name} out.",
        "tagline": "Just ask.",
    },
}


def _setup_persona(settings: dict) -> None:
    """Configure the assistant's persona -- name, personality, tone."""
    if "persona" not in settings:
        settings["persona"] = {}

    persona = settings["persona"]
    current_name = persona.get("name", "Assistant")

    print("\n-- Persona Setup ---------------------------------------\n")
    print("  Give your assistant an identity.\n")
    print(f"  Current name: {current_name}")
    print(f"  Current tone: {persona.get('tone', 'professional-witty')}")
    print()

    # Step 1: Name
    new_name = input(f"  Assistant name (Enter to keep '{current_name}'): ").strip()
    if new_name:
        persona["name"] = new_name
        # Auto-update wake word
        persona["wake_word"] = f"hey {new_name.lower()}"
        print(f"  -> Name set to: {new_name}")
        print(f"  -> Wake word set to: 'hey {new_name.lower()}'")
    else:
        new_name = current_name

    # Step 2: Tone
    print("\n  Choose a personality tone:\n")
    tone_keys = list(TONE_PRESETS.keys())
    for i, (key, preset) in enumerate(TONE_PRESETS.items(), 1):
        current = " <- current" if persona.get("tone") == key else ""
        print(f"  {i}. {preset['label']}{current}")
    print(f"  {len(tone_keys) + 1}. Custom (write your own personality)")
    print()

    choice = _input_choice(
        f"  Select tone (1-{len(tone_keys) + 1}): ",
        range(1, len(tone_keys) + 2),
    )

    if choice <= len(tone_keys):
        key = tone_keys[choice - 1]
        preset = TONE_PRESETS[key]
        persona["tone"] = key
        persona["personality"] = preset["personality"]
        persona["greeting"] = preset["greeting"]
        persona["farewell"] = preset["farewell"]
        persona["tagline"] = preset["tagline"]
        print(f"  -> Tone set to: {preset['label']}")
    else:
        # Custom personality
        print("\n  Write a custom personality description.")
        print("  Use {name} where you want the assistant's name inserted.")
        print("  Example: 'You are {name}, a sarcastic but brilliant assistant...'")
        print()
        custom = input("  Personality: ").strip()
        if custom:
            persona["tone"] = "custom"
            persona["personality"] = custom
        tagline = input("  Tagline (short motto): ").strip()
        if tagline:
            persona["tagline"] = tagline
        greeting = input("  Greeting (use {time_of_day} and {name}): ").strip()
        if greeting:
            persona["greeting"] = greeting
        farewell = input("  Farewell (use {name}): ").strip()
        if farewell:
            persona["farewell"] = farewell

    # Preview
    from datetime import datetime
    hour = datetime.now().hour
    tod = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    name = persona.get("name", "Assistant")

    print(f"\n  -- Preview --")
    print(f"  Greeting: \"{persona.get('greeting', '').format(time_of_day=tod, name=name)}\"")
    print(f"  Tagline:  \"{persona.get('tagline', '')}\"")
    print(f"  Farewell: \"{persona.get('farewell', '').format(name=name)}\"")
    print(f"  Wake word: \"{persona.get('wake_word', '')}\"")
    print()


# --- Section 1: AI Providers --------------------------------------

def _setup_providers(settings: dict, env_path: Path) -> None:
    """Configure AI providers and API keys."""
    # Merge built-in and custom providers
    providers = {**settings.get("providers", {}), **settings.get("custom_providers", {})}
    provider_list = list(providers.keys())

    print("\n-- AI Provider Setup --------------------------------\n")
    print("  Choose which AI provider to use. Bring your own API key\n"
          "  for cloud providers, or run open-source models locally.\n")

    for i, (name, config) in enumerate(providers.items(), 1):
        tier = config.get("tier", "free").upper()
        desc = config.get("description", "")
        enabled = "ON " if config.get("enabled") else "OFF"
        active = " <- active" if settings["ai"].get("active_provider") == name else ""
        is_custom = name in settings.get("custom_providers", {})
        tag = " [CUSTOM]" if is_custom else ""

        key_env = config.get("api_key_env", "")
        key_status = ""
        if key_env:
            has_key = _env_has_key(env_path, key_env)
            key_status = " [key: [OK]]" if has_key else " [key: [X]]"
        elif name == "ollama" or config.get("base_url"):
            key_status = " [local]"

        print(f"  {i}. [{enabled}] {name:<12} {tier:<6} {desc}{key_status}{active}{tag}")

    print(f"\n  {len(provider_list) + 1}. Back to main menu")
    print()

    choice = _input_choice(
        "  Select provider to configure (or back): ",
        range(1, len(provider_list) + 2),
    )
    if choice == len(provider_list) + 1:
        return

    name = provider_list[choice - 1]
    config = providers[name]

    # Toggle enabled
    current = config.get("enabled", False)
    toggle = input(f"\n  {name} is {'ON' if current else 'OFF'}. Toggle? (y/N): ").strip().lower()
    if toggle == "y":
        config["enabled"] = not current
        print(f"  ->{name} is now {'ON' if config['enabled'] else 'OFF'}")

    # Set as active?
    if config.get("enabled"):
        make_active = input(f"  Set {name} as your primary AI provider? (y/N): ").strip().lower()
        if make_active == "y":
            settings["ai"]["active_provider"] = name
            print(f"  ->{name} is now your active provider")

    # API key
    key_env = config.get("api_key_env", "")
    if key_env and config.get("enabled"):
        has_key = _env_has_key(env_path, key_env)
        if not has_key:
            print(f"\n  {name} needs an API key ({key_env}).")
            _show_key_instructions(name)
            _set_api_key(env_path, key_env)
        else:
            change = input(f"\n  {key_env} is already set. Change it? (y/N): ").strip().lower()
            if change == "y":
                _set_api_key(env_path, key_env)

    # Ollama model selection
    if name == "ollama" and config.get("enabled"):
        print(f"\n  Current model: {config.get('model', 'qwen3:8b')}")
        print("  Popular models: qwen3:8b, llama3.2:8b, mistral:7b, gemma2:9b")
        new_model = input("  Change model? (enter name or press Enter to keep): ").strip()
        if new_model:
            config["model"] = new_model
            print(f"  ->Model set to: {new_model}")
        print("\n  Make sure Ollama is installed: https://ollama.com")
        print(f"  Run: ollama pull {config['model']}")

    # Ask to configure another
    another = input("\n  Configure another provider? (y/N): ").strip().lower()
    if another == "y":
        _setup_providers(settings, env_path)


# --- Section 1b: Custom AI Provider ------------------------------

def _add_custom_provider(settings: dict, env_path: Path) -> None:
    """Add a custom open-source AI provider (any OpenAI-compatible endpoint)."""
    if "custom_providers" not in settings:
        settings["custom_providers"] = {}

    print("\n-- Add Custom AI Provider --------------------------\n")
    print("  Add any open-source model running locally or remotely.")
    print("  Supports any OpenAI-compatible API endpoint:\n")
    print("    - LM Studio     (http://localhost:1234/v1)")
    print("    - Ollama         (http://localhost:11434/v1)")
    print("    - vLLM           (http://localhost:8000/v1)")
    print("    - LocalAI        (http://localhost:8080/v1)")
    print("    - text-gen-webui (http://localhost:5000/v1)")
    print("    - llama.cpp      (http://localhost:8080/v1)")
    print("    - Any other OpenAI-compatible server")
    print()

    # Show existing custom providers
    existing = settings["custom_providers"]
    if existing:
        print("  Current custom providers:")
        for name, config in existing.items():
            status = "ON" if config.get("enabled") else "OFF"
            print(f"    [{status}] {name} ->{config.get('base_url', '')} ({config.get('model', '')})")
        print()

    name = input("  Provider name (short, e.g., 'lmstudio', 'vllm'): ").strip().lower()
    if not name:
        print("  Cancelled.")
        return

    base_url = input("  Base URL (e.g., http://localhost:1234/v1): ").strip()
    if not base_url:
        print("  Cancelled.")
        return

    model = input("  Model name (e.g., 'qwen2.5-coder-7b', 'llama-3.2-8b'): ").strip()
    if not model:
        model = "default"

    needs_key = input("  Does it require an API key? (y/N): ").strip().lower()
    api_key_env = ""
    if needs_key == "y":
        key_name = f"{name.upper()}_API_KEY"
        api_key_env = key_name
        _set_api_key(env_path, key_name)

    desc = input("  Description (optional): ").strip() or f"Custom model: {model}"

    settings["custom_providers"][name] = {
        "enabled": True,
        "base_url": base_url,
        "model": model,
        "api_key_env": api_key_env,
        "max_tokens": 4096,
        "temperature": 0.7,
        "tier": "free",
        "description": desc,
    }

    # Set as active?
    make_active = input(f"\n  Set '{name}' as your active AI provider? (y/N): ").strip().lower()
    if make_active == "y":
        settings["ai"]["active_provider"] = name
        print(f"  ->'{name}' is now your active provider")

    print(f"\n  [OK] Custom provider '{name}' added!")
    print(f"     URL: {base_url}")
    print(f"     Model: {model}")

    another = input("\n  Add another custom provider? (y/N): ").strip().lower()
    if another == "y":
        _add_custom_provider(settings, env_path)


# --- Section 2: Integrations -------------------------------------

def _setup_integrations(settings: dict, env_path: Path) -> None:
    """Configure which integrations to enable and their credentials."""
    integrations = settings.get("integrations", {})

    print("\n-- Integration Setup --------------------------------\n")
    print("  Choose which apps and services to connect.\n")

    int_list = list(integrations.keys())
    for i, name in enumerate(int_list, 1):
        info = INTEGRATION_INFO.get(name, {})
        label = info.get("label", name.title())
        desc = info.get("description", "")
        enabled = "ON " if integrations[name].get("enabled") else "OFF"

        # Check if keys are configured
        keys_needed = info.get("requires_keys", [])
        if keys_needed:
            keys_ok = all(_env_has_key(env_path, k) for k in keys_needed)
            key_status = " [auth: [OK]]" if keys_ok else " [auth: [X]]"
        else:
            key_status = ""

        print(f"  {i}. [{enabled}] {label:<22} {desc}{key_status}")

    print(f"\n  {len(int_list) + 1}. Back to main menu")
    print()

    choice = _input_choice(
        "  Select integration to configure (or back): ",
        range(1, len(int_list) + 2),
    )
    if choice == len(int_list) + 1:
        return

    name = int_list[choice - 1]
    info = INTEGRATION_INFO.get(name, {})
    label = info.get("label", name.title())

    print(f"\n  -- {label} --\n")
    print(f"  {info.get('description', '')}\n")

    # Show capabilities
    caps = info.get("capabilities", [])
    if caps:
        print("  What it can do:")
        for cap in caps:
            readable = cap.replace("_", " ").title()
            print(f"    - {readable}")
        print()

    # Toggle
    current = integrations[name].get("enabled", False)
    toggle = input(f"  {label} is {'ON' if current else 'OFF'}. Toggle? (y/N): ").strip().lower()
    if toggle == "y":
        integrations[name]["enabled"] = not current
        print(f"  ->{label} is now {'ON' if integrations[name]['enabled'] else 'OFF'}")

    # Setup auth if needed and enabled
    if integrations[name].get("enabled"):
        auth_type = info.get("auth_type", "none")
        from src.core.auth import has_valid_token, run_bot_token_flow, run_oauth_flow

        if auth_type == "oauth":
            if has_valid_token(name):
                print("  [OK] Already authorized.")
                reauth = input("  Re-authorize? (y/N): ").strip().lower()
                if reauth != "y":
                    pass
                else:
                    _run_integration_auth(name, info, env_path)
            else:
                print(f"\n  {label} needs authorization.")
                print("  I'll open your browser to authorize -just click 'Allow'.")
                proceed = input("  Proceed with authorization? (Y/n): ").strip().lower()
                if proceed != "n":
                    _run_integration_auth(name, info, env_path)

        elif auth_type == "bot_token":
            if has_valid_token(name):
                print("  [OK] Bot token is configured.")
                change = input("  Change it? (y/N): ").strip().lower()
                if change == "y":
                    auto = info.get("auto_setup", {})
                    run_bot_token_flow(name, auto.get("url", ""), auto.get("instructions", ""))
            else:
                auto = info.get("auto_setup", {})
                run_bot_token_flow(name, auto.get("url", ""), auto.get("instructions", ""))

    # Ask to configure another
    another = input("\n  Configure another integration? (y/N): ").strip().lower()
    if another == "y":
        _setup_integrations(settings, env_path)


# --- Section 3: Voice Automations --------------------------------

def _setup_voice_automations(settings: dict) -> None:
    """Configure voice command automations."""
    # Initialize automations section if missing
    if "voice_automations" not in settings:
        settings["voice_automations"] = {}

    active_automations = settings["voice_automations"]
    enabled_integrations = {
        k for k, v in settings.get("integrations", {}).items() if v.get("enabled")
    }

    print("\n-- Voice Automation Setup ---------------------------\n")
    print("  Set up what your assistant does when you say specific things.\n")

    preset_list = list(VOICE_AUTOMATION_PRESETS.keys())
    for i, (key, preset) in enumerate(VOICE_AUTOMATION_PRESETS.items(), 1):
        enabled = "ON " if key in active_automations and active_automations[key].get("enabled") else "OFF"

        # Check if required integrations are enabled
        required = set(preset.get("requires_integrations", []))
        has_deps = required.issubset(enabled_integrations) if required else True
        dep_status = "" if has_deps else " [!]needs: " + ", ".join(required - enabled_integrations)

        print(f"  {i}. [{enabled}] {preset['label']}")
        print(f"       Trigger: \"{preset['trigger']}\"")
        print(f"       {preset['description']}{dep_status}")
        print()

    print(f"  {len(preset_list) + 1}. Add custom voice automation")
    print(f"  {len(preset_list) + 2}. Back to main menu")
    print()

    choice = _input_choice(
        "  Select automation to configure (or back): ",
        range(1, len(preset_list) + 3),
    )

    if choice == len(preset_list) + 2:
        return

    if choice == len(preset_list) + 1:
        _add_custom_automation(settings)
        return

    key = preset_list[choice - 1]
    preset = VOICE_AUTOMATION_PRESETS[key]

    # Check dependencies
    required = set(preset.get("requires_integrations", []))
    missing = required - enabled_integrations
    if missing:
        print(f"\n  [!]This automation requires these integrations to be enabled first:")
        for m in missing:
            label = INTEGRATION_INFO.get(m, {}).get("label", m)
            print(f"       - {label}")
        print("  Go to 'Integrations' in the main menu to enable them.")
        input("\n  Press Enter to continue...")
        _setup_voice_automations(settings)
        return

    # Toggle automation
    current = key in active_automations and active_automations.get(key, {}).get("enabled")
    toggle = input(
        f"\n  '{preset['label']}' is {'ON' if current else 'OFF'}. Toggle? (y/N): "
    ).strip().lower()

    if toggle == "y":
        if key not in active_automations:
            active_automations[key] = {}
        active_automations[key]["enabled"] = not current
        active_automations[key]["trigger"] = preset["trigger"]
        active_automations[key]["action"] = preset["action"]
        status = "ON" if active_automations[key]["enabled"] else "OFF"
        print(f"  ->'{preset['label']}' is now {status}")

    # Custom trigger phrase?
    if active_automations.get(key, {}).get("enabled"):
        custom = input(
            f"\n  Default trigger: \"{preset['trigger']}\"\n"
            "  Customize trigger phrase? (enter new phrase or press Enter to keep): "
        ).strip()
        if custom:
            active_automations[key]["trigger"] = custom
            print(f"  ->Trigger set to: \"{custom}\"")

    # Configure provider for this automation?
    change_provider = input(
        "\n  Use a specific AI provider for this automation? (y/N): "
    ).strip().lower()
    if change_provider == "y":
        providers = settings.get("providers", {})
        enabled_providers = [n for n, c in providers.items() if c.get("enabled")]
        if not enabled_providers:
            print("  No providers enabled. Set up providers first.")
        else:
            print(f"  Available: {', '.join(enabled_providers)}")
            prov = input("  Provider name: ").strip().lower()
            if prov in enabled_providers:
                active_automations[key]["provider"] = prov
                print(f"  ->This automation will use: {prov}")

    another = input("\n  Configure another automation? (y/N): ").strip().lower()
    if another == "y":
        _setup_voice_automations(settings)


def _add_custom_automation(settings: dict) -> None:
    """Add a custom voice automation rule."""
    if "voice_automations" not in settings:
        settings["voice_automations"] = {}

    print("\n  -- Custom Voice Automation --\n")
    print("  Define a voice trigger and what the assistant should do.\n")
    print("  Examples:")
    print("    Trigger: 'check my portfolio'")
    print("    Action:  'Open browser, go to portfolio tracker, read the summary aloud'")
    print()

    name = input("  Automation name (short, e.g., 'check_portfolio'): ").strip()
    if not name:
        print("  Cancelled.")
        return

    trigger = input("  Trigger phrase (what you'll say): ").strip()
    if not trigger:
        print("  Cancelled.")
        return

    action = input("  What should the assistant do?: ").strip()
    if not action:
        print("  Cancelled.")
        return

    key = name.lower().replace(" ", "_")
    settings["voice_automations"][key] = {
        "enabled": True,
        "trigger": trigger,
        "action": action,
        "custom": True,
    }

    print(f"\n  [OK] Custom automation '{name}' created!")
    print(f"     Say \"{trigger}\" ->{action}")


# --- Section 4: Provider Routing ---------------------------------

def _setup_task_routing(settings: dict) -> None:
    """Advanced: assign different AI providers to different task types.

    By default, one provider handles everything. This lets power users
    route specific tasks to specific providers (e.g., Claude for coding).
    """
    all_providers = {**settings.get("providers", {}), **settings.get("custom_providers", {})}
    enabled_providers = [n for n, c in all_providers.items() if c.get("enabled")]

    if len(enabled_providers) < 2:
        print("\n  You need at least 2 enabled providers to set up task routing.")
        print("  Go to 'AI Provider' or 'Add Custom AI' first to enable more.")
        return

    if "ai" not in settings:
        settings["ai"] = {}
    if "task_routing" not in settings["ai"]:
        settings["ai"]["task_routing"] = {}

    routing = settings["ai"]["task_routing"]

    print("\n-- Task Routing (Advanced) --------------------------\n")
    print("  Assign different AI providers to different tasks.")
    print("  Leave unset to use your default provider for that task.\n")
    print(f"  Default provider: {settings['ai'].get('active_provider', 'not set')}")
    print(f"  Enabled providers: {', '.join(enabled_providers)}\n")

    categories = [
        ("general", "General questions and conversation"),
        ("coding", "Code generation, debugging, technical help"),
        ("research", "Research, fact-checking, analysis"),
        ("summarization", "Summarizing emails, documents, messages"),
        ("creative", "Creative writing, brainstorming, ideas"),
        ("system_control", "Opening apps, system commands"),
        ("email", "Reading and composing emails"),
        ("calendar", "Calendar events and scheduling"),
        ("messaging", "Chat and messaging across platforms"),
    ]

    default = settings["ai"].get("active_provider", "default")
    for i, (cat, desc) in enumerate(categories, 1):
        current = routing.get(cat, default)
        marker = " *" if cat in routing else ""
        print(f"  {i}. {cat:<18} ->{current:<12} ({desc}){marker}")

    print(f"\n  {len(categories) + 1}. Clear all routing (use default for everything)")
    print(f"  {len(categories) + 2}. Back to main menu")
    print()

    choice = _input_choice(
        "  Select task to change (or back): ",
        range(1, len(categories) + 3),
    )

    if choice == len(categories) + 2:
        return

    if choice == len(categories) + 1:
        settings["ai"]["task_routing"] = {}
        print("  ->All routing cleared. Default provider handles everything.")
        return

    cat_key, cat_desc = categories[choice - 1]
    print(f"\n  Task: {cat_key} ({cat_desc})")
    print(f"  Available: {', '.join(enabled_providers)}")

    provider = input("  Assign provider (or 'default' to remove): ").strip().lower()
    if provider == "default":
        routing.pop(cat_key, None)
        print(f"  ->{cat_key} will use the default provider")
    elif provider in enabled_providers:
        routing[cat_key] = provider
        print(f"  ->{cat_key} will now use: {provider}")
    else:
        print(f"  Unknown. Available: {', '.join(enabled_providers)}")

    another = input("\n  Configure another task? (y/N): ").strip().lower()
    if another == "y":
        _setup_task_routing(settings)


# --- Section 5: View Config --------------------------------------

def _show_config(settings: dict) -> None:
    """Display current configuration summary."""
    print("\n-- Current Configuration ----------------------------\n")

    # Persona
    p = settings.get("persona", {})
    print(f"  Name:        {p.get('name', 'Assistant')}")
    print(f"  Tone:        {p.get('tone', 'professional-witty')}")
    print(f"  Tagline:     \"{p.get('tagline', '')}\"")
    print(f"  Wake Word:   \"{p.get('wake_word', 'hey assistant')}\"")

    # Active provider
    active = settings.get("ai", {}).get("active_provider", "not set")
    print(f"\n  Active AI Provider: {active}")

    # Built-in providers
    print("\n  AI Providers:")
    for name, config in settings.get("providers", {}).items():
        status = "ON " if config.get("enabled") else "OFF"
        model = config.get("model", "")
        print(f"    [{status}] {name:<12} model: {model}")

    # Custom providers
    custom = settings.get("custom_providers", {})
    if custom:
        print("\n  Custom AI Providers:")
        for name, config in custom.items():
            status = "ON " if config.get("enabled") else "OFF"
            model = config.get("model", "")
            url = config.get("base_url", "")
            print(f"    [{status}] {name:<12} model: {model} ({url})")

    # Task routing
    routing = settings.get("ai", {}).get("task_routing", {})
    if routing:
        print("\n  Task Routing (advanced):")
        for cat, prov in routing.items():
            print(f"    {cat:<18} ->{prov}")

    # Integrations
    print("\n  Integrations:")
    for name, config in settings.get("integrations", {}).items():
        status = "ON " if config.get("enabled") else "OFF"
        label = INTEGRATION_INFO.get(name, {}).get("label", name.title())
        print(f"    [{status}] {label}")

    # Voice automations
    automations = settings.get("voice_automations", {})
    if automations:
        print("\n  Voice Automations:")
        for key, auto in automations.items():
            if auto.get("enabled"):
                label = VOICE_AUTOMATION_PRESETS.get(key, {}).get("label", key)
                trigger = auto.get("trigger", "")
                provider = auto.get("provider", "default")
                print(f"    [ON ] \"{trigger}\" ->{label} (via {provider})")

    # Voice settings
    voice = settings.get("voice", {})
    print(f"\n  Voice:")
    print(f"    STT Engine: {voice.get('stt_engine', 'vosk')}")
    print(f"    TTS Engine: {voice.get('tts_engine', 'edge_tts')}")
    print(f"    TTS Voice:  {voice.get('tts_voice', 'en-US-GuyNeural')}")

    print()
    input("  Press Enter to continue...")


# --- Auth helpers -------------------------------------------------

def _run_integration_auth(name: str, info: dict, env_path: Path) -> None:
    """Run OAuth flow for an integration."""
    from src.core.auth import run_oauth_flow

    oauth = info.get("oauth_config", {})
    keys_needed = info.get("requires_keys", [])

    # For OAuth, we need client_id and client_secret from .env
    # The first key is typically the access token, but for OAuth we need
    # client credentials first
    client_id_key = f"{name.upper()}_CLIENT_ID"
    client_secret_key = f"{name.upper()}_CLIENT_SECRET"

    # Check if we have client credentials
    client_id = os.getenv(client_id_key) or _env_get_key(env_path, client_id_key)
    client_secret = os.getenv(client_secret_key) or _env_get_key(env_path, client_secret_key)

    if not client_id:
        print(f"\n  Need {client_id_key} to start OAuth flow.")
        print(f"  Set up your app at the provider's developer portal.")
        _set_api_key(env_path, client_id_key)
        client_id = _env_get_key(env_path, client_id_key)

    if not client_secret:
        _set_api_key(env_path, client_secret_key)
        client_secret = _env_get_key(env_path, client_secret_key)

    if client_id and client_secret:
        run_oauth_flow(
            integration_name=name,
            client_id=client_id,
            client_secret=client_secret,
            auth_uri=oauth.get("auth_uri", ""),
            token_uri=oauth.get("token_uri", ""),
            scopes=oauth.get("scopes", []),
        )
    else:
        print("  [X] Missing credentials. Skipping auth flow.")


# --- Utilities ----------------------------------------------------

def _print_banner() -> None:
    print("\n" + "=" * 55)
    print("   AI Assistant - Configuration Wizard")
    print("=" * 55)
    print("""
  This wizard will help you set up:

    1. Persona -give your assistant a name and personality

    2. AI Provider -pick your AI (Ollama, Groq, Gemini,
       Claude, OpenAI) or add any open-source model

    3. Integrations -connect Google, Microsoft, Slack,
       Figma, Instagram, Telegram, Discord, WhatsApp

    4. Voice Automations -morning briefings, message
       replies, Slack reminders, focus mode, etc.

  Your data stays on your machine. Cloud AI providers
  are opt-in and use YOUR API keys.
""")


def _print_finish(settings: dict) -> None:
    active = settings.get("ai", {}).get("active_provider", "not set")
    enabled_integrations = [
        INTEGRATION_INFO.get(k, {}).get("label", k)
        for k, v in settings.get("integrations", {}).items()
        if v.get("enabled")
    ]
    auto_count = sum(
        1 for v in settings.get("voice_automations", {}).values()
        if v.get("enabled")
    )

    print("\n" + "=" * 55)
    print("   Configuration saved! [OK]")
    print("=" * 55)
    print(f"\n  AI Provider:     {active}")
    if enabled_integrations:
        print(f"  Integrations:    {', '.join(enabled_integrations)}")
    if auto_count:
        print(f"  Voice Automations: {auto_count} active")
    print(f"\n  Commands:")
    print(f"    python -m src              Interactive chat")
    print(f"    python -m src --voice      Voice mode")
    print(f"    python -m src --server     Start server for phone app")
    print(f"    python -m src --setup      Re-run this wizard")
    print()


def _input_choice(prompt: str, valid_range: range) -> int:
    """Get a valid integer choice from the user."""
    while True:
        try:
            raw = input(prompt).strip()
            if not raw:
                continue
            val = int(raw)
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

    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()

    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key_name}=") or line.startswith(f"# {key_name}="):
            lines[i] = f"{key_name}={key}"
            found = True
            break

    if not found:
        lines.append(f"{key_name}={key}")

    env_path.write_text("\n".join(lines) + "\n")
    print(f"  [OK] {key_name} saved to .env")


def _env_has_key(env_path: Path, key_name: str) -> bool:
    """Check if a key exists and is set in .env."""
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
