"""Tests for desktop overlay voice event integration."""

from unittest.mock import MagicMock, patch

import pytest

from src.voice.overlay_bridge import OverlayVoiceBridge
from src.voice.pipeline import PipelineEvent


class TestOverlayBridgeSubscription:
    """Test that the bridge subscribes to pipeline events."""

    def test_bridge_accepts_pet_and_chat(self):
        """Bridge accepts pet and optional chat window references."""
        mock_pet = MagicMock()
        bridge = OverlayVoiceBridge(pet=mock_pet)
        assert bridge.pet is mock_pet
        assert bridge.chat_window is None

    def test_bridge_accepts_chat_window(self):
        """Bridge accepts an optional chat window."""
        mock_pet = MagicMock()
        mock_chat = MagicMock()
        bridge = OverlayVoiceBridge(pet=mock_pet, chat_window=mock_chat)
        assert bridge.chat_window is mock_chat


class TestOverlayWakeDetected:
    """Test UI state changes on wake_detected."""

    def test_wake_sets_pet_to_idle_alert(self):
        """On wake_detected, pet shows a listening speech bubble."""
        mock_pet = MagicMock()
        bridge = OverlayVoiceBridge(pet=mock_pet)

        event = PipelineEvent(name="wake_detected", data={"confidence": 0.9})
        bridge.on_event(event)

        mock_pet.say.assert_called_once()
        assert "listening" in mock_pet.say.call_args[0][0].lower() or \
               "yes" in mock_pet.say.call_args[0][0].lower() or \
               "here" in mock_pet.say.call_args[0][0].lower()


class TestOverlayTranscription:
    """Test that transcription text appears in chat window."""

    def test_transcription_shown_in_chat(self):
        """On transcription_complete, user's text appears in chat window."""
        mock_pet = MagicMock()
        mock_chat = MagicMock()
        bridge = OverlayVoiceBridge(pet=mock_pet, chat_window=mock_chat)

        event = PipelineEvent(name="transcription_complete", data={"text": "open chrome"})
        bridge.on_event(event)

        mock_chat._add_message.assert_called_once()
        call_args = mock_chat._add_message.call_args
        assert "open chrome" in call_args[0][1]
        assert call_args[1].get("is_bot", call_args[0][2] if len(call_args[0]) > 2 else None) is False

    def test_transcription_without_chat_window(self):
        """Transcription with no chat window doesn't crash."""
        mock_pet = MagicMock()
        bridge = OverlayVoiceBridge(pet=mock_pet, chat_window=None)

        event = PipelineEvent(name="transcription_complete", data={"text": "hello"})
        bridge.on_event(event)  # Should not raise


class TestOverlaySpeaking:
    """Test expression changes during speaking."""

    def test_speaking_started_sets_talk_state(self):
        """On speaking_started, pet enters TALK state with response text."""
        mock_pet = MagicMock()
        mock_chat = MagicMock()
        bridge = OverlayVoiceBridge(pet=mock_pet, chat_window=mock_chat)

        event = PipelineEvent(name="speaking_started", data={"text": "Opening Chrome now."})
        bridge.on_event(event)

        mock_pet.say.assert_called_once_with("Opening Chrome now.")
        mock_chat._add_message.assert_called_once()

    def test_speaking_done_returns_to_idle(self):
        """On speaking_done, pet returns to IDLE state."""
        mock_pet = MagicMock()
        bridge = OverlayVoiceBridge(pet=mock_pet)

        event = PipelineEvent(name="speaking_done", data={})
        bridge.on_event(event)

        mock_pet._set_state.assert_called_once()

    def test_error_event_shows_in_chat(self):
        """On error, system message appears in chat."""
        mock_pet = MagicMock()
        mock_chat = MagicMock()
        bridge = OverlayVoiceBridge(pet=mock_pet, chat_window=mock_chat)

        event = PipelineEvent(name="error", data={"error": "STT crashed"})
        bridge.on_event(event)

        mock_chat._add_system_message.assert_called_once()
        assert "STT crashed" in mock_chat._add_system_message.call_args[0][0]
