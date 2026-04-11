"""Tests for audio capture module."""

import asyncio
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.voice.audio_capture import AudioCapture


class TestAudioCaptureInit:
    """Test AudioCapture instantiation."""

    def test_default_settings(self):
        """AudioCapture uses sensible defaults: 16kHz, mono, 16-bit."""
        capture = AudioCapture()
        assert capture.sample_rate == 16000
        assert capture.channels == 1
        assert capture.device is None  # system default

    def test_custom_settings(self):
        """AudioCapture accepts custom device and sample rate."""
        capture = AudioCapture(sample_rate=44100, channels=2, device=3)
        assert capture.sample_rate == 44100
        assert capture.channels == 2
        assert capture.device == 3

    def test_chunk_duration_default(self):
        """Default chunk duration produces expected chunk size."""
        capture = AudioCapture(chunk_duration_ms=100)
        # 16000 Hz * 0.1s = 1600 samples per chunk
        assert capture.chunk_size == 1600


class TestAudioCaptureStream:
    """Test audio chunk streaming."""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        """Streaming yields numpy arrays of the correct shape and dtype."""
        capture = AudioCapture()

        fake_audio = np.zeros((capture.chunk_size, 1), dtype=np.int16)

        with patch("src.voice.audio_capture.sd") as mock_sd:
            # Simulate InputStream that feeds chunks via callback
            mock_stream = MagicMock()
            mock_stream.active = True
            mock_sd.InputStream.return_value.__enter__ = MagicMock(return_value=mock_stream)
            mock_sd.InputStream.return_value.__exit__ = MagicMock(return_value=False)

            chunks = []

            async def collect_chunks():
                async for chunk in capture.stream():
                    chunks.append(chunk)
                    if len(chunks) >= 2:
                        capture.stop()
                        break

            # Feed fake audio into the capture's internal queue
            capture._running = True
            capture._queue = asyncio.Queue()
            await capture._queue.put(fake_audio)
            await capture._queue.put(fake_audio)

            async for chunk in capture._read_chunks():
                chunks.append(chunk)
                if len(chunks) >= 2:
                    break

            assert len(chunks) == 2
            for chunk in chunks:
                assert isinstance(chunk, np.ndarray)
                assert chunk.dtype == np.int16

    @pytest.mark.asyncio
    async def test_stream_chunk_shape(self):
        """Each chunk has the expected number of samples."""
        capture = AudioCapture(chunk_duration_ms=100)
        expected_samples = 1600  # 16000 * 0.1

        capture._running = True
        capture._queue = asyncio.Queue()
        fake_audio = np.zeros((expected_samples, 1), dtype=np.int16)
        await capture._queue.put(fake_audio)

        chunks = []
        async for chunk in capture._read_chunks():
            chunks.append(chunk)
            break

        assert chunks[0].shape[0] == expected_samples


class TestAudioCaptureNoMic:
    """Test graceful handling when no microphone is available."""

    @pytest.mark.asyncio
    async def test_no_microphone_raises_voice_error(self):
        """Starting capture with no mic raises VoiceError."""
        from src.core.exceptions import VoiceError

        capture = AudioCapture()

        with patch("src.voice.audio_capture.sd") as mock_sd:
            mock_sd.InputStream.side_effect = Exception("No input device found")

            with pytest.raises(VoiceError, match="microphone"):
                await capture.start()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Stopping when not running is a no-op, not an error."""
        capture = AudioCapture()
        capture.stop()  # Should not raise
        assert not capture._running
