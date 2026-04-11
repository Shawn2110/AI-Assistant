# Spec: Build the Voice Pipeline MVP

## Overview

Implement a complete voice interaction pipeline for Mike so the user can summon him with "Hey Mike", speak a command, receive a spoken response, and have the entire flow integrate with the existing LangGraph agent and desktop overlay.

## Goals

1. **Wake Word Detection:** Continuously listen for "Hey Mike" using openwakeword. When detected, transition to active listening mode.
2. **Speech-to-Text (STT):** Capture the user's spoken command via sounddevice and transcribe it using Vosk (offline). No cloud dependency for basic STT.
3. **Text-to-Speech (TTS):** Speak Mike's response aloud using Edge-TTS (online, high-quality Microsoft voices) with automatic fallback to pyttsx3 (offline).
4. **Agent Integration:** Route the transcribed text through the existing LangGraph agent and return the agent's text response to the TTS engine.
5. **Desktop Overlay Integration:** Signal the existing tkinter desktop pet/chat overlay when Mike is listening, thinking, and speaking so the UI can update expressions and show the transcript.

## Non-Goals (Out of Scope)

- Mobile voice interaction (mobile app is a separate future track).
- Streaming STT (real-time partial transcripts). This MVP uses utterance-level transcription.
- Voice authentication or speaker identification.
- Custom wake word training. We use the default openwakeword model for "Hey Mike".
- Replacing the tkinter overlay with Godot (separate future track).

## Technical Approach

### Audio Capture
- Use `sounddevice` to open a continuous audio input stream from the default microphone.
- Audio format: 16-bit PCM, 16kHz mono (required by both Vosk and openwakeword).
- The stream feeds into a shared ring buffer or callback pipeline.

### Wake Word Detection
- `openwakeword` runs on each audio chunk from the stream.
- When confidence exceeds a configurable threshold (default 0.7), emit a "wake" event.
- After wake, pause wake word detection and hand audio to the STT engine.

### Speech-to-Text
- `vosk` loads a pre-downloaded language model from a configurable path (e.g., `config/vosk-model/`).
- Audio chunks are fed to a `KaldiRecognizer` until silence is detected (end-of-utterance).
- The final transcript text is returned.

### Agent Processing
- The transcript string is sent to the existing LangGraph agent as a user message.
- The agent processes it (tool calls, reasoning) and returns a text response.
- This is the existing `src/ai_assistant/agent/` code -- no new agent logic needed.

### Text-to-Speech
- **Online path:** `edge-tts` generates an audio stream from the agent's response text. Play it via `sounddevice` or a temporary file.
- **Offline fallback:** If Edge-TTS fails (no internet), fall back to `pyttsx3.speak()`.
- TTS engine selection is automatic based on connectivity, matching the product spec.

### Pipeline Orchestration
- A `VoicePipeline` class orchestrates the full loop: listen → wake → transcribe → agent → speak → listen.
- Runs in its own asyncio task (or thread) so the desktop overlay remains responsive.
- Emits events (wake_detected, listening_started, transcription_complete, speaking_started, speaking_done) that the overlay can subscribe to.

### Configuration
- All voice settings live in `config/settings.yaml` under a `voice:` key.
- Configurable: wake word threshold, Vosk model path, TTS voice name, input device index.

## Acceptance Criteria

1. User says "Hey Mike" → Mike wakes and begins listening (desktop overlay shows listening state).
2. User speaks a command → command is transcribed and shown in the chat window.
3. Transcribed command is processed by the LangGraph agent → response appears in chat.
4. Mike speaks the response aloud using Edge-TTS (or pyttsx3 offline).
5. After speaking, Mike returns to wake word listening mode.
6. The pipeline handles errors gracefully: no crash on missing microphone, missing Vosk model, or TTS failure.
7. Unit test coverage >80% for all new modules.
