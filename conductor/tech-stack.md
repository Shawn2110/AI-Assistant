# Tech Stack

## Backend / Core

| Technology | Purpose |
|---|---|
| Python 3.12 | Primary language for the backend, AI orchestration, voice pipeline, and server |
| setuptools | Build system and packaging via `pyproject.toml`. CLI entry point: `assistant` |

## AI Orchestration

| Technology | Purpose |
|---|---|
| LangGraph | Agent framework -- builds Mike's brain as a ReAct-style state graph (think → tool → think) |
| LangChain | Foundation layer for chat models, tool definitions, prompts, and message types |

## AI Providers

| Technology | Provider | Tier | Purpose |
|---|---|---|---|
| langchain-groq | Groq | Free | Default cloud provider. Runs Llama 3.3 70B at high speed |
| langchain-ollama | Ollama | Free | Local/offline AI. Runs models on the user's machine (Qwen, Llama, Mistral) |
| langchain-google-genai | Google Gemini | Free | Cloud AI via Google Gemini 2.0 Flash |
| langchain-anthropic | Claude (Anthropic) | Paid | Premium AI for coding and reasoning tasks |
| langchain-openai | OpenAI GPT | Paid | Versatile cloud AI. Also used for custom OpenAI-compatible endpoints (LM Studio, vLLM, LocalAI) |

## Voice Pipeline

| Technology | Role | Online/Offline |
|---|---|---|
| Vosk | Speech-to-Text (STT) | Offline |
| Edge-TTS | Text-to-Speech (TTS) -- high quality Microsoft voices | Online |
| pyttsx3 | Text-to-Speech (TTS) -- fallback | Offline |
| sounddevice | Microphone audio capture | N/A |
| openwakeword | Wake word detection ("Hey Mike") | Offline |
| numpy | Audio waveform processing | N/A |

## Server & Networking

| Technology | Purpose |
|---|---|
| FastAPI | REST + WebSocket API server for mobile app and remote access |
| Uvicorn | ASGI server that runs FastAPI |
| websockets | Real-time bidirectional communication with clients |
| python-jose[cryptography] | JWT token creation and verification for secure remote auth |
| slowapi | Rate limiting to prevent abuse on exposed endpoints |
| pyngrok | Tunnel from internet to localhost for remote phone access without port forwarding |

## Desktop GUI -- Current (tkinter)

| Technology | Purpose |
|---|---|
| tkinter | Transparent overlay window for desktop pet and chat bubble |
| Pillow (PIL) | Programmatic sprite generation and tray icon creation |
| pystray | System tray icon with menu (Open Chat, Quick Command, Settings, Quit) |
| winotify | Windows toast notifications for reminders and alerts |

## Desktop Avatar -- Planned (Blender + Godot)

| Technology | Purpose |
|---|---|
| Blender | 3D character modeling, rigging, and animation. Exports glTF/GLB |
| Godot Engine | Real-time 3D rendering of Mike's anime-style avatar as a desktop overlay. Replaces tkinter pet. Communicates with Python backend via WebSocket/localhost |

## Mobile App -- Planned (Flutter)

| Technology | Purpose |
|---|---|
| Flutter (Dart) | Cross-platform mobile app (Android + iOS) for chat and voice interaction with Mike |
| Design | No 3D avatar on mobile. Small logo/icon pops up (Bixby/Siri style) with minimal chat interface |
| Connection | Connects to Mike's FastAPI backend over network (local WiFi or pyngrok tunnel) |

## Configuration & Utilities

| Technology | Purpose |
|---|---|
| Pydantic | Settings validation and type-safe configuration models |
| PyYAML | Reads `config/settings.yaml` |
| python-dotenv | Loads API keys from `.env` into environment variables |
| structlog | Structured logging with timestamps, context, and colored console output |
| httpx | HTTP client for OAuth token exchange and external API calls |

## Authentication

| Technology | Purpose |
|---|---|
| Custom OAuth 2.0 flow | Browser-based consent → local callback server → token exchange → secure storage in `config/tokens/` |
| python-jose (JWT) | Token-based auth for remote server access |

## Integrations (Planned)

| Integration | Auth Type | Capabilities |
|---|---|---|
| Google Suite (Gmail, Calendar, Drive) | OAuth 2.0 | Read/send email, manage events, file access |
| Microsoft (Outlook, Teams, OneDrive) | OAuth 2.0 | Email, calendar, file access |
| Slack | Bot token | Read/send messages, channel management |
| Telegram | Bot token | Send/receive messages |
| Discord | Bot token | Send/receive messages |
| WhatsApp | API token | Send/receive messages |
| Figma | Personal access token | Read designs, export assets |
| System (built) | None | Open/close apps, power control, volume, files, reminders, system info |

## Dev Tools

| Technology | Purpose |
|---|---|
| pytest | Test runner |
| pytest-asyncio | Async test support |
| ruff | Linter and formatter (line length 100, target Python 3.12) |
