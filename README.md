# Mike - Personal AI Assistant

A voice-enabled personal AI assistant that automates work tasks, provides reminders, and responds to voice commands. Accessible via voice, hotkey, system tray, or CLI.

## Features

- **Voice Interaction** -- Wake word detection ("Hey Mike"), speech-to-text (Vosk), and text-to-speech (Edge-TTS with offline fallback)
- **Multiple AI Providers** -- Groq, Gemini, Ollama, Claude, and OpenAI with automatic fallback
- **Offline-First** -- Works fully offline with Ollama + Vosk + pyttsx3
- **System Control** -- Open/close apps, file operations, volume, power, reminders
- **Background Daemon** -- System tray icon with notifications and quick commands
- **Extensible Integrations** -- Google Suite, Microsoft, Slack, Discord, Telegram (planned)

## Requirements

- Python 3.12+
- Windows 10/11 (primary) or macOS

## Installation

```bash
git clone https://github.com/Shawn2110/AI-Assistant.git
cd AI-Assistant
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

**Core install (free providers only):**

```bash
pip install -e .
```

**With all optional dependencies:**

```bash
pip install -e ".[all]"
```

**Other install options:**

| Extra        | What it adds                    |
|--------------|---------------------------------|
| `paid`       | Claude (Anthropic) + OpenAI     |
| `microsoft`  | Outlook, Teams, OneDrive        |
| `messaging`  | Telegram + Discord bots         |
| `voice-extra`| openwakeword for wake detection |
| `dev`        | pytest, ruff                    |

## Configuration

1. Create a `.env` file in the project root with your API keys:

```env
GROQ_API_KEY=your_key_here        # Free
GEMINI_API_KEY=your_key_here      # Free
# ANTHROPIC_API_KEY=your_key      # Optional (paid)
# OPENAI_API_KEY=your_key         # Optional (paid)
```

At minimum, set one AI provider key (e.g. `GROQ_API_KEY` for free usage).

2. Run the interactive setup wizard:

```bash
assistant --setup
```

Or edit `config/settings.yaml` directly to configure providers, voice settings, integrations, and persona.

## Usage

```bash
# Interactive chat
assistant

# Single command
assistant "open spotify"

# Voice mode (wake word + microphone)
assistant --voice

# Background daemon (system tray)
assistant --daemon

# Use a specific AI provider
assistant --provider claude "explain this code"

# Debug logging
assistant -v
```

## Architecture

```
                         ┌──────────────────────────────────┐
                         │          Entry Points            │
                         │    CLI   |   Voice   |   Daemon  │
                         └────────────┬─────────────────────┘
                                      │
                      ┌───────────────┴───────────────┐
                      │                               │
           ┌──────────▼──────────┐         ┌──────────▼──────────┐
           │   Voice Pipeline    │         │   System Tray       │
           │                     │         │   Daemon            │
           │ AudioCapture        │         │ Background Monitor  │
           │ WakeWordDetector    │         │ Toast Notifications │
           │ SpeechToText (Vosk) │         │ Quick Commands      │
           │ TextToSpeech (Edge) │         │ Reminder Delivery   │
           └──────────┬──────────┘         └──────────┬──────────┘
                      │                               │
                      └───────────────┬───────────────┘
                                      │
                           ┌──────────▼──────────┐
               │   LangGraph Agent   │
               │   (ReAct Pattern)   │
               │                     │
               │  Think → Act → Loop │
               └──────────┬──────────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
   ┌──────────▼──┐ ┌─────▼─────┐ ┌──▼──────────┐
   │  Provider   │ │   Tools   │ │   Config    │
   │  Factory    │ │           │ │             │
   │             │ │ System    │ │ Pydantic    │
   │ Groq       │ │ Google    │ │ YAML + .env │
   │ Gemini     │ │ Microsoft │ │ OAuth Tokens│
   │ Ollama     │ │ Slack     │ │ Persona     │
   │ Claude     │ │ Discord   │ │             │
   │ OpenAI     │ │ Telegram  │ │             │
   └─────────────┘ └───────────┘ └─────────────┘
```

**Key modules:**

| Module             | Purpose                                      |
|--------------------|----------------------------------------------|
| `src/ai/`         | LangGraph agent, provider factory, fallback   |
| `src/voice/`      | Audio capture, wake word, STT, TTS, pipeline  |
| `src/integrations/`| System tools, Google, Microsoft, Slack        |
| `src/core/`       | Config, logging, auth, exceptions             |
| `src/server/`     | FastAPI server for mobile access              |
| `src/daemon.py`   | System tray background service                |

## AI Providers

| Provider | Type       | Model                    | Cost |
|----------|------------|--------------------------|------|
| Groq     | Cloud      | Llama 3.3 70B            | Free |
| Gemini   | Cloud      | Gemini 2.0 Flash         | Free |
| Ollama   | Local      | Qwen, Llama, Mistral     | Free |
| Claude   | Cloud      | Claude Sonnet 4          | Paid |
| OpenAI   | Cloud      | GPT-4o Mini              | Paid |

The assistant automatically falls back through configured providers if one fails.

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific module
pytest tests/test_voice/ -v
```

## Development

```bash
pip install -e ".[dev]"

# Lint and format
ruff check src/ tests/
ruff format src/ tests/
```

## Project Structure

```
AI-Assistant/
├── src/
│   ├── ai/              # Agent and provider logic
│   ├── voice/           # Voice pipeline components
│   ├── integrations/    # System and service tools
│   ├── core/            # Config, auth, logging
│   ├── server/          # FastAPI server
│   ├── tunnel/          # ngrok remote access
│   ├── cli.py           # CLI entry point
│   └── daemon.py        # System tray daemon
├── tests/               # Test suite
├── config/
│   ├── settings.yaml    # Main configuration
│   └── vosk-model/      # Offline speech model
├── conductor/           # Development framework
└── pyproject.toml       # Dependencies and build config
```

## License

This project is currently unlicensed. All rights reserved.
