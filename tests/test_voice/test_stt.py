"""Tests for speech-to-text engine module."""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.voice.stt import SpeechToText


class TestSpeechToTextInit:
    """Test SpeechToText instantiation."""

    @patch("src.voice.stt.vosk")
    def test_init_with_model_path(self, mock_vosk):
        """SpeechToText initializes with a Vosk model path."""
        mock_vosk.Model.return_value = MagicMock()
        stt = SpeechToText(model_path="/path/to/model")
        mock_vosk.Model.assert_called_once_with(model_path="/path/to/model")
        assert stt.sample_rate == 16000

    @patch("src.voice.stt.vosk")
    def test_init_custom_sample_rate(self, mock_vosk):
        """SpeechToText accepts custom sample rate."""
        mock_vosk.Model.return_value = MagicMock()
        stt = SpeechToText(model_path="/path/to/model", sample_rate=8000)
        assert stt.sample_rate == 8000

    @patch("src.voice.stt.vosk")
    def test_init_invalid_model_path_raises(self, mock_vosk):
        """Invalid model path raises VoiceError."""
        from src.core.exceptions import VoiceError

        mock_vosk.Model.side_effect = Exception("Model not found")

        with pytest.raises(VoiceError, match="model"):
            SpeechToText(model_path="/nonexistent/path")


class TestSpeechToTextTranscription:
    """Test audio transcription."""

    @patch("src.voice.stt.vosk")
    def test_feed_chunk_partial_result(self, mock_vosk):
        """Feeding audio chunks accumulates partial results."""
        mock_model = MagicMock()
        mock_vosk.Model.return_value = mock_model

        mock_recognizer = MagicMock()
        mock_recognizer.AcceptWaveform.return_value = False
        mock_recognizer.PartialResult.return_value = json.dumps({"partial": "hello"})
        mock_vosk.KaldiRecognizer.return_value = mock_recognizer

        stt = SpeechToText(model_path="/path/to/model")
        chunk = np.zeros(1600, dtype=np.int16)
        result = stt.feed(chunk)

        assert result is None  # Not a final result yet
        mock_recognizer.AcceptWaveform.assert_called_once()

    @patch("src.voice.stt.vosk")
    def test_feed_chunk_final_result(self, mock_vosk):
        """When silence is detected, a final transcript is returned."""
        mock_model = MagicMock()
        mock_vosk.Model.return_value = mock_model

        mock_recognizer = MagicMock()
        mock_recognizer.AcceptWaveform.return_value = True
        mock_recognizer.Result.return_value = json.dumps({"text": "open chrome"})
        mock_vosk.KaldiRecognizer.return_value = mock_recognizer

        stt = SpeechToText(model_path="/path/to/model")
        chunk = np.zeros(1600, dtype=np.int16)
        result = stt.feed(chunk)

        assert result == "open chrome"

    @patch("src.voice.stt.vosk")
    def test_feed_empty_final_result_returns_none(self, mock_vosk):
        """Empty final transcript returns None (silence only)."""
        mock_model = MagicMock()
        mock_vosk.Model.return_value = mock_model

        mock_recognizer = MagicMock()
        mock_recognizer.AcceptWaveform.return_value = True
        mock_recognizer.Result.return_value = json.dumps({"text": ""})
        mock_vosk.KaldiRecognizer.return_value = mock_recognizer

        stt = SpeechToText(model_path="/path/to/model")
        chunk = np.zeros(1600, dtype=np.int16)
        result = stt.feed(chunk)

        assert result is None

    @patch("src.voice.stt.vosk")
    def test_finalize_returns_remaining_audio(self, mock_vosk):
        """Finalize flushes any remaining audio and returns transcript."""
        mock_model = MagicMock()
        mock_vosk.Model.return_value = mock_model

        mock_recognizer = MagicMock()
        mock_recognizer.FinalResult.return_value = json.dumps({"text": "set a timer"})
        mock_vosk.KaldiRecognizer.return_value = mock_recognizer

        stt = SpeechToText(model_path="/path/to/model")
        result = stt.finalize()

        assert result == "set a timer"

    @patch("src.voice.stt.vosk")
    def test_reset_creates_new_recognizer(self, mock_vosk):
        """Reset creates a fresh KaldiRecognizer for the next utterance."""
        mock_model = MagicMock()
        mock_vosk.Model.return_value = mock_model

        stt = SpeechToText(model_path="/path/to/model")
        initial_call_count = mock_vosk.KaldiRecognizer.call_count

        stt.reset()

        assert mock_vosk.KaldiRecognizer.call_count == initial_call_count + 1
