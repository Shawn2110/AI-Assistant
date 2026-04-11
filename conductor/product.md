# Initial Concept

A personal AI assistant named "Mike" that automates work tasks, provides reminders, responds to voice commands, and is accessible from both laptop and phone. Features include a desktop pet mascot, system tray daemon, multi-provider AI (Groq, Ollama, Claude, etc.), system control tools, and planned integrations with Google, Microsoft, Slack, and messaging platforms.

---

# Product Guide

## Vision

Mike is an open-source AI assistant that lives as an animated character on your screen. He appears when you call him by voice ("Hey Mike"), press a hotkey, or when he has something to tell you -- like a reminder or a notification. When not needed, Mike sits quietly in the system tray. He is a companion that feels present, not a hidden CLI tool.

Mike works both online and fully offline. With a local model (Ollama) and local speech recognition (Vosk), Mike functions without any internet connection. When online, he can use faster cloud providers (Groq, Gemini) or premium ones (Claude, OpenAI) and connect to external services like Gmail, Slack, and calendar.

## Target Users

Mike is an open-source tool for the general public:

- **Developers** who want a voice-activated coding assistant that can run commands, manage Git, and control their system.
- **Productivity-focused users** who want reminders, app automation, and workflow management through natural conversation.
- **Privacy-conscious users** who want an AI assistant that runs entirely offline on their own hardware.

## How Mike Works

### Summoning Mike
Mike appears on screen in three ways:
1. **Voice:** Say "Hey Mike" and he wakes up, appears on screen, and listens for your command.
2. **Hotkey/Button:** Press a configurable shortcut (or click the system tray icon) and Mike slides onto the screen ready for input.
3. **Proactive:** Mike appears on his own to deliver reminders, notifications, or scheduled alerts. He pops up, delivers the message with a speech bubble, and fades back after acknowledgment.

### On-Screen Presence
When summoned, Mike appears as an animated robot character on the desktop overlay. He shows speech bubbles with his responses, reacts with expressions (talking, happy, thinking), and can be dragged around. A chat window opens alongside him for longer conversations. When dismissed, he walks off screen or fades back to the system tray.

### Interaction Modes
- **Voice conversation (guided):** The user summons Mike first ("Hey Mike" / hotkey / tray). Mike acknowledges and asks what they need. The user states their intent (e.g., "Send a message"). Mike then guides them step-by-step with follow-up questions (platform? recipient? message?) to build a complete, structured command. Mike confirms the full action before executing.
- **Text chat:** Type in the chat window next to Mike, or use the CLI for terminal-based interaction. The same guided flow applies -- Mike asks clarifying questions before acting.
- **Quick command:** Press the hotkey, speak or type a one-liner, get a quick response -- Mike disappears after. For simple actions (e.g., "What time is it?"), no guided flow is needed.
- **Notification reply (one-shot):** User says: "Mike, on [app] reply to [name] [message]". This is a structured one-shot command that skips the guided flow. Examples:
  - "Mike, on Slack reply to Dave meeting at 3"
  - "Mike, on WhatsApp reply to Mom I'll be home soon"
  - "Mike, on Discord reply to John sounds good"

### Offline vs Online

| Mode | AI Provider | Voice | Integrations |
|------|------------|-------|-------------|
| **Offline** | Ollama (local models) | Vosk (STT) + pyttsx3 (TTS) | System tools only (apps, files, reminders, power) |
| **Online** | Groq, Gemini, Claude, OpenAI | Edge-TTS (higher quality TTS) | Full: Gmail, Calendar, Slack, Telegram, Discord, WhatsApp |

Mike detects connectivity and switches seamlessly. If the internet drops mid-conversation, he falls back to the local model without interrupting the user.

## Core Use Cases (Priority Order)

### 1. Coding Assistant
Run terminal commands, manage Git repos, explain code, generate snippets, and automate development workflows -- all through voice or text.

### 2. Productivity Automation
Open/close apps, manage files, control system power and volume, set reminders that pop up on screen with Mike delivering them as an animated character.

### 3. Communication Hub
Read and send emails, manage calendar events, send messages on Slack, Telegram, Discord, and WhatsApp -- all from conversation with Mike.

### 4. Media Control
Control Spotify playback through voice -- play, pause, skip, search for songs/artists/playlists, queue tracks, and check what's currently playing.

## Platform Strategy

- **Desktop (Primary):** Windows/macOS app with a 3D anime-style human avatar (Blender + Godot Engine), system tray background service, voice wake word, and CLI. Mike appears as a full animated character on screen.
- **Mobile (Secondary):** Lightweight mobile app where Mike appears as a small logo/icon (like Bixby/Siri) with a minimal chat interface. No 3D avatar on mobile -- fast and unobtrusive.

## Action Confirmation

Mike always asks before executing actions (opening apps, sending messages, shutting down, etc.). Users see the proposed action in the chat window and confirm or reject. This is the safe default for an open-source tool.

## AI Architecture

- **Multi-provider, no vendor lock-in:** Ollama (offline), Groq (free cloud), Gemini (free cloud), Claude (paid), OpenAI (paid), plus any OpenAI-compatible endpoint.
- **Automatic fallback:** If a provider fails, Mike tries the next one in the chain.
- **Task routing:** Optionally assign providers per task type (e.g., Claude for coding, Groq for chat).

## Key Differentiator

Mike is not a chatbot hiding in a terminal. He is an on-screen character with personality -- a Jarvis-style companion who appears when called, delivers reminders proactively, reacts with animations, and disappears when not needed. The combination of animated presence, voice interaction, offline capability, and open-source extensibility makes Mike unique.
