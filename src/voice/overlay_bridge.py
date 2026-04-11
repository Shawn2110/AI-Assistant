"""Bridge between the voice pipeline and the desktop overlay (pet + chat window).

Translates VoicePipeline events into UI updates: speech bubbles, pet state
changes, chat window messages, and error displays.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.pet.pet import PetState
from src.voice.pipeline import PipelineEvent

log = get_logger(__name__)


class OverlayVoiceBridge:
    """Connects VoicePipeline events to the desktop pet and chat window.

    Pass an instance's ``on_event`` method as the ``on_event`` callback
    when constructing a ``VoicePipeline``::

        bridge = OverlayVoiceBridge(pet=pet, chat_window=chat)
        pipeline = VoicePipeline(..., on_event=bridge.on_event)
    """

    def __init__(self, pet, chat_window=None):
        self.pet = pet
        self.chat_window = chat_window

    def on_event(self, event: PipelineEvent) -> None:
        """Dispatch a pipeline event to the appropriate UI handler."""
        handler = getattr(self, f"_on_{event.name}", None)
        if handler:
            handler(event)
        else:
            log.debug("overlay_bridge.unhandled_event", event=event.name)

    def _on_wake_detected(self, event: PipelineEvent) -> None:
        """Wake word detected — show listening indicator."""
        self.pet.say("I'm listening...", duration=3000)

    def _on_listening_started(self, event: PipelineEvent) -> None:
        """Active listening started."""
        pass  # Pet is already in TALK state from wake_detected

    def _on_transcription_complete(self, event: PipelineEvent) -> None:
        """User's speech transcribed — show in chat window."""
        text = event.data.get("text", "")
        if self.chat_window and text:
            self.chat_window._add_message("You", text, is_bot=False)

    def _on_speaking_started(self, event: PipelineEvent) -> None:
        """Mike is speaking — update pet and chat."""
        text = event.data.get("text", "")
        if text:
            self.pet.say(text)
        if self.chat_window and text:
            persona_name = getattr(self.pet, "persona", None)
            name = persona_name.name if persona_name else "Mike"
            self.chat_window._add_message(name, text, is_bot=True)

    def _on_speaking_done(self, event: PipelineEvent) -> None:
        """Mike finished speaking — return to idle."""
        self.pet._set_state(PetState.IDLE)

    def _on_error(self, event: PipelineEvent) -> None:
        """Pipeline error — show in chat window."""
        error = event.data.get("error", "Unknown error")
        if self.chat_window:
            self.chat_window._add_system_message(f"Voice error: {error}")
        log.error("overlay_bridge.error", error=error)
