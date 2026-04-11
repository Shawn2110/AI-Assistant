"""Voice mode entry point — starts the voice pipeline with all components wired up."""

from __future__ import annotations

import asyncio

from src.core.config import get_settings
from src.core.logger import get_logger

log = get_logger(__name__)


def start_voice(provider: str | None = None) -> None:
    """Start the voice pipeline in the terminal (no desktop pet).

    Listens for the wake word, transcribes speech, sends to the agent,
    and speaks the response. Runs until Ctrl+C.
    """
    settings = get_settings()
    voice_cfg = settings.voice
    persona = settings.persona

    if not voice_cfg.enabled:
        print("Voice is disabled in settings.yaml. Set voice.enabled: true to use.")
        return

    print(f"\n  {persona.name} Voice Mode")
    print(f"  Say '{persona.wake_word}' to activate.")
    print(f"  Press Ctrl+C to stop.\n")

    try:
        asyncio.run(_run_pipeline(settings, provider))
    except KeyboardInterrupt:
        print(f"\n  {persona.get_farewell()}")


async def _run_pipeline(settings, provider: str | None = None) -> None:
    """Build and run the voice pipeline."""
    voice_cfg = settings.voice

    # Audio capture
    from src.voice.audio_capture import AudioCapture
    capture = AudioCapture(
        sample_rate=16000,
        channels=1,
        device=voice_cfg.input_device,
    )

    # Wake word detector
    from src.voice.wake_word import WakeWordDetector
    detector = WakeWordDetector(threshold=voice_cfg.wake_threshold)

    # Speech-to-text
    from src.voice.stt import SpeechToText
    stt = SpeechToText(model_path=voice_cfg.vosk_model_path)

    # Text-to-speech
    from src.voice.tts import TextToSpeech
    tts = TextToSpeech(voice=voice_cfg.tts_voice)

    # Agent
    from src.ai.agent import AssistantAgent
    from src.integrations import get_all_tools
    agent = AssistantAgent(settings=settings, tools=get_all_tools())

    async def agent_fn(text: str) -> str:
        return await agent.chat(text, provider=provider)

    # Event logger for terminal mode
    def on_event(event):
        if event.name == "wake_detected":
            print(f"  [{settings.persona.name}] I'm listening...")
        elif event.name == "transcription_complete":
            print(f"  [You] {event.data.get('text', '')}")
        elif event.name == "speaking_started":
            print(f"  [{settings.persona.name}] {event.data.get('text', '')}")
        elif event.name == "speaking_done":
            print(f"  (Ready for next command)\n")
        elif event.name == "error":
            print(f"  [!] Error: {event.data.get('error', '')}")

    # Pipeline
    from src.voice.pipeline import VoicePipeline
    pipeline = VoicePipeline(
        audio_capture=capture,
        wake_word_detector=detector,
        stt=stt,
        tts=tts,
        agent_fn=agent_fn,
        on_event=on_event,
    )

    log.info("voice.pipeline_started")
    await pipeline.run()
