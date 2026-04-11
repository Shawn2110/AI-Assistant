"""Tests for voice pipeline orchestrator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.voice.pipeline import VoicePipeline, PipelineEvent


class TestVoicePipelineInit:
    """Test VoicePipeline instantiation."""

    def test_init_with_components(self):
        """Pipeline accepts injected components."""
        mock_capture = MagicMock()
        mock_wake = MagicMock()
        mock_stt = MagicMock()
        mock_tts = MagicMock()
        mock_agent = AsyncMock()

        pipeline = VoicePipeline(
            audio_capture=mock_capture,
            wake_word_detector=mock_wake,
            stt=mock_stt,
            tts=mock_tts,
            agent_fn=mock_agent,
        )

        assert pipeline.audio_capture is mock_capture
        assert pipeline.wake_word_detector is mock_wake
        assert pipeline.stt is mock_stt
        assert pipeline.tts is mock_tts

    def test_init_not_running(self):
        """Pipeline starts in stopped state."""
        pipeline = VoicePipeline(
            audio_capture=MagicMock(),
            wake_word_detector=MagicMock(),
            stt=MagicMock(),
            tts=MagicMock(),
            agent_fn=AsyncMock(),
        )
        assert not pipeline.running


class TestPipelineEvents:
    """Test that events are emitted at each stage."""

    @pytest.mark.asyncio
    async def test_events_emitted_during_full_flow(self):
        """Full flow emits: wake_detected, listening_started, transcription_complete, speaking_started, speaking_done."""
        events = []

        def on_event(event: PipelineEvent):
            events.append(event.name)

        # Setup mocks
        mock_capture = MagicMock()
        chunk = np.zeros(1600, dtype=np.int16)

        mock_wake = MagicMock()
        # First call: wake detected. After that: return None (pipeline will stop)
        wake_event = MagicMock()
        wake_event.detected = True
        wake_event.confidence = 0.9
        mock_wake.process.side_effect = [wake_event]
        mock_wake.reset.return_value = None

        mock_stt = MagicMock()
        mock_stt.feed.return_value = "open chrome"
        mock_stt.reset.return_value = None

        mock_tts = AsyncMock()
        mock_tts.speak.return_value = None

        mock_agent = AsyncMock(return_value="Opening Chrome now.")

        pipeline = VoicePipeline(
            audio_capture=mock_capture,
            wake_word_detector=mock_wake,
            stt=mock_stt,
            tts=mock_tts,
            agent_fn=mock_agent,
            on_event=on_event,
        )

        # Simulate one full cycle
        await pipeline._process_one_cycle(chunk)

        assert "wake_detected" in events
        assert "listening_started" in events
        assert "transcription_complete" in events
        assert "speaking_started" in events
        assert "speaking_done" in events

    @pytest.mark.asyncio
    async def test_no_events_when_no_wake_word(self):
        """No events emitted when wake word is not detected."""
        events = []

        def on_event(event: PipelineEvent):
            events.append(event.name)

        mock_capture = MagicMock()
        mock_wake = MagicMock()
        mock_wake.process.return_value = None  # No wake word

        pipeline = VoicePipeline(
            audio_capture=mock_capture,
            wake_word_detector=mock_wake,
            stt=MagicMock(),
            tts=AsyncMock(),
            agent_fn=AsyncMock(),
            on_event=on_event,
        )

        chunk = np.zeros(1600, dtype=np.int16)
        await pipeline._process_wake_phase(chunk)

        assert len(events) == 0


class TestPipelineErrorRecovery:
    """Test error recovery during pipeline execution."""

    @pytest.mark.asyncio
    async def test_stt_failure_does_not_crash(self):
        """If STT fails, pipeline emits error event and returns to wake listening."""
        events = []

        def on_event(event: PipelineEvent):
            events.append(event)

        mock_wake = MagicMock()
        wake_event = MagicMock()
        wake_event.detected = True
        wake_event.confidence = 0.9
        mock_wake.process.return_value = wake_event

        mock_stt = MagicMock()
        mock_stt.feed.side_effect = Exception("STT crashed")
        mock_stt.reset.return_value = None

        pipeline = VoicePipeline(
            audio_capture=MagicMock(),
            wake_word_detector=mock_wake,
            stt=mock_stt,
            tts=AsyncMock(),
            agent_fn=AsyncMock(),
            on_event=on_event,
        )

        chunk = np.zeros(1600, dtype=np.int16)
        # Should not raise
        await pipeline._process_one_cycle(chunk)

        error_events = [e for e in events if e.name == "error"]
        assert len(error_events) >= 1

    @pytest.mark.asyncio
    async def test_tts_failure_does_not_crash(self):
        """If TTS fails, pipeline emits error event but doesn't crash."""
        events = []

        def on_event(event: PipelineEvent):
            events.append(event)

        mock_wake = MagicMock()
        wake_event = MagicMock()
        wake_event.detected = True
        wake_event.confidence = 0.9
        mock_wake.process.return_value = wake_event

        mock_stt = MagicMock()
        mock_stt.feed.return_value = "hello"
        mock_stt.reset.return_value = None

        mock_tts = AsyncMock()
        mock_tts.speak.side_effect = Exception("TTS crashed")

        mock_agent = AsyncMock(return_value="Hi there")

        pipeline = VoicePipeline(
            audio_capture=MagicMock(),
            wake_word_detector=mock_wake,
            stt=mock_stt,
            tts=mock_tts,
            agent_fn=mock_agent,
            on_event=on_event,
        )

        chunk = np.zeros(1600, dtype=np.int16)
        await pipeline._process_one_cycle(chunk)

        error_events = [e for e in events if e.name == "error"]
        assert len(error_events) >= 1

    @pytest.mark.asyncio
    async def test_agent_failure_does_not_crash(self):
        """If agent fails, pipeline emits error event but doesn't crash."""
        events = []

        def on_event(event: PipelineEvent):
            events.append(event)

        mock_wake = MagicMock()
        wake_event = MagicMock()
        wake_event.detected = True
        wake_event.confidence = 0.9
        mock_wake.process.return_value = wake_event

        mock_stt = MagicMock()
        mock_stt.feed.return_value = "hello"
        mock_stt.reset.return_value = None

        mock_agent = AsyncMock(side_effect=Exception("Agent crashed"))

        pipeline = VoicePipeline(
            audio_capture=MagicMock(),
            wake_word_detector=mock_wake,
            stt=mock_stt,
            tts=AsyncMock(),
            agent_fn=mock_agent,
            on_event=on_event,
        )

        chunk = np.zeros(1600, dtype=np.int16)
        await pipeline._process_one_cycle(chunk)

        error_events = [e for e in events if e.name == "error"]
        assert len(error_events) >= 1


class TestPipelineStartStop:
    """Test start and stop controls."""

    def test_stop_sets_running_false(self):
        """stop() sets running to False."""
        pipeline = VoicePipeline(
            audio_capture=MagicMock(),
            wake_word_detector=MagicMock(),
            stt=MagicMock(),
            tts=AsyncMock(),
            agent_fn=AsyncMock(),
        )
        pipeline._running = True
        pipeline.stop()
        assert not pipeline.running
