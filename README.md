# Mike - Personal AI Assistant

A voice-first personal AI assistant that automates work tasks, runs recurring workflows, and responds to voice commands. Accessible via voice or CLI.

## Features

- **Voice Interaction** -- Wake word detection ("Hey Mike"), speech-to-text (Vosk), and text-to-speech (Edge-TTS with offline fallback)
- **Multiple AI Providers** -- Groq, Gemini, Ollama, Claude, and OpenAI with automatic fallback
- **Offline-First** -- Works fully offline with Ollama + Vosk + pyttsx3
- **Intent Router** -- Trivial commands ("open spotify", "volume to 50") skip the LLM entirely via a three-tier regex + embedding-classifier router — sub-100ms fast path for ~70% of commands
- **Code-as-Policy Workflows** -- Recurring tasks ("every Monday summarize my week") are generated once as sandboxed Python scripts and run deterministically on cron — no LLM in the run-loop
- **System Control** -- Open/close apps, file operations, volume, power, reminders
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
| `paid`       | Claude (Anthropic) + OpenAI                 |
| `microsoft`  | Outlook, Teams, OneDrive                    |
| `messaging`  | Telegram + Discord bots                     |
| `voice-extra`| openwakeword for wake detection             |
| `router`     | sentence-transformers for Tier-1 classifier |
| `workflows`  | apscheduler + croniter for scheduled jobs   |
| `dev`        | pytest, ruff                                |

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

# Voice mode (wake word + microphone, also hosts the workflow scheduler)
assistant --voice

# Workflow management
assistant workflow create "every monday at 9am summarize my calendar and post to slack" --schedule "0 9 * * MON"
assistant workflow list
assistant workflow run <id>
assistant workflow disable <id>
assistant workflow logs <id>

# Use a specific AI provider
assistant --provider claude "explain this code"

# Inspect routing decisions (which tier caught a phrase)
assistant --explain-routing "open spotify"

# Debug logging
assistant -v
```

## Architecture

```
                         ┌──────────────────────────────────┐
                         │          Entry Points            │
                         │  CLI chat  |  Voice  |  Workflows│
                         └────────────┬─────────────────────┘
                                      │
                      ┌───────────────┴─────────────────┐
                      │                                 │
           ┌──────────▼──────────┐           ┌──────────▼──────────┐
           │   Voice Pipeline    │           │  Workflow Manager   │
           │  (hosts scheduler)  │           │                     │
           │ AudioCapture        │           │ Generator + ast     │
           │ WakeWordDetector    │           │ Validator + sandbox │
           │ SpeechToText (Vosk) │           │ APScheduler (cron)  │
           │ TextToSpeech (Edge) │           │ Per-run logs        │
           └──────────┬──────────┘           └──────────┬──────────┘
                      │                                 │
                      └─────────────────┬───────────────┘
                                        │
                           ┌────────────▼────────────┐
                           │   Intent Router         │
                           │   regex -> classifier   │
                           │   -> ReAct fallback     │
                           └────────────┬────────────┘
                                        │
                           ┌────────────▼────────────┐
                           │   LangGraph ReAct Agent │
                           │                         │
                           │   Think → Act → Loop    │
                           └────────────┬────────────┘
                                        │
                         ┌──────────────┼──────────────┐
                         │              │              │
                ┌────────▼──────┐ ┌─────▼─────┐ ┌──────▼──────┐
                │   Providers   │ │   Tools   │ │   Config    │
                │  Groq/Gemini  │ │  System + │ │  Pydantic   │
                │  Ollama       │ │  Google + │ │  YAML+.env  │
                │  Claude/OpenAI│ │  MS/Slack │ │             │
                └───────────────┘ └───────────┘ └─────────────┘
```

**Key modules:**

| Module              | Purpose                                          |
|---------------------|--------------------------------------------------|
| `src/ai/`           | LangGraph agent, provider factory, fallback     |
| `src/ai/router/`    | Intent router (regex + embedding classifier)    |
| `src/voice/`        | Audio capture, wake word, STT, TTS, pipeline    |
| `src/workflows/`    | Generator, sandbox, scheduler, manager          |
| `src/integrations/` | System tools, Google, Microsoft, Slack          |
| `src/core/`         | Config, logging, auth, exceptions               |
| `src/server/`       | FastAPI server                                  |

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
│   ├── ai/              # Agent, providers, router
│   ├── voice/           # Voice pipeline (hosts scheduler)
│   ├── workflows/       # Code-as-policy workflows
│   ├── integrations/    # System and service tools
│   ├── core/            # Config, auth, logging
│   ├── server/          # FastAPI server
│   ├── tunnel/          # ngrok remote access
│   └── cli.py           # CLI entry point
├── tests/               # Test suite
├── config/
│   ├── settings.yaml    # Main configuration
│   ├── intents.yaml     # Router intent catalogue
│   └── vosk-model/      # Offline speech model
├── workflows/           # Generated workflow scripts + run logs
├── conductor/           # Development framework
└── pyproject.toml       # Dependencies and build config
```

## License

This project is currently unlicensed. All rights reserved.
