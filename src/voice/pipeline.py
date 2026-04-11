"""Voice pipeline orchestrator - wires audio capture, wake word, STT, agent, and TTS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

import numpy as np

from src.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class PipelineEvent:
    """Event emitted by the voice pipeline at each stage."""
    name: str
    data: dict[str, Any] = field(default_factory=dict)


class VoicePipeline:
    """Orchestrates the full voice loop: listen -> wake -> transcribe -> agent -> speak.

    Components are injected so the pipeline is testable without hardware.

    Usage::

        pipeline = VoicePipeline(
            audio_capture=capture,
            wake_word_detector=detector,
            stt=stt_engine,
            tts=tts_engine,
            agent_fn=agent.chat,
            on_event=my_callback,
        )
        await pipeline.run()
    """

    def __init__(
        self,
        audio_capture,
        wake_word_detector,
        stt,
        tts,
        agent_fn: Callable[[str], Awaitable[str]],
        on_event: Callable[[PipelineEvent], None] | None = None,
    ):
        self.audio_capture = audio_capture
        self.wake_word_detector = wake_word_detector
        self.stt = stt
        self.tts = tts
        self.agent_fn = agent_fn
        self._on_event = on_event
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def _emit(self, name: str, **data) -> None:
        """Emit a pipeline event."""
        event = PipelineEvent(name=name, data=data)
        if self._on_event:
            self._on_event(event)
        log.info(f"pipeline.{name}", **data)

    async def run(self) -> None:
        """Start the pipeline loop. Blocks until stop() is called."""
        self._running = True
        log.info("pipeline.started")
        try:
            async for chunk in self.audio_capture.stream():
                if not self._running:
                    break
                await self._process_one_cycle(chunk)
        finally:
            self._running = False
            log.info("pipeline.stopped")

    def stop(self) -> None:
        """Stop the pipeline loop."""
        self._running = False
        self.audio_capture.stop()

    async def _process_wake_phase(self, chunk: np.ndarray) -> bool:
        """Check for wake word. Returns True if detected."""
        result = self.wake_word_detector.process(chunk)
        if result is not None and result.detected:
            self._emit("wake_detected", confidence=result.confidence)
            return True
        return False

    async def _process_one_cycle(self, chunk: np.ndarray) -> None:
        """Process one full cycle: wake -> listen -> transcribe -> agent -> speak."""
        # Wake phase
        wake_detected = await self._process_wake_phase(chunk)
        if not wake_detected:
            return

        try:
            # Listening phase
            self._emit("listening_started")

            # Transcription phase - feed the chunk that triggered wake + get transcript
            transcript = self.stt.feed(chunk)
            if not transcript:
                transcript = self.stt.finalize()

            if not transcript:
                self.stt.reset()
                self.wake_word_detector.reset()
                return

            self._emit("transcription_complete", text=transcript)

            # Agent phase
            response = await self.agent_fn(transcript)

            # Speaking phase
            self._emit("speaking_started", text=response)
            await self.tts.speak(response)
            self._emit("speaking_done")

        except Exception as exc:
            log.error("pipeline.error", error=str(exc))
            self._emit("error", error=str(exc))
        finally:
            # Always reset for next cycle
            self.stt.reset()
            self.wake_word_detector.reset()
