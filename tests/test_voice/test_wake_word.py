"""Tests for wake word detector module."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.voice.wake_word import WakeWordDetector, WakeWordEvent


class TestWakeWordDetectorInit:
    """Test WakeWordDetector instantiation."""

    @patch("src.voice.wake_word.openwakeword")
    def test_default_threshold(self, mock_oww):
        """Default confidence threshold is 0.7."""
        detector = WakeWordDetector()
        assert detector.threshold == 0.7

    @patch("src.voice.wake_word.openwakeword")
    def test_custom_threshold(self, mock_oww):
        """Custom confidence threshold is accepted."""
        detector = WakeWordDetector(threshold=0.5)
        assert detector.threshold == 0.5

    @patch("src.voice.wake_word.openwakeword")
    def test_model_loaded_on_init(self, mock_oww):
        """openwakeword model is loaded during __init__."""
        detector = WakeWordDetector()
        mock_oww.Model.assert_called_once()


class TestWakeWordDetection:
    """Test wake word detection from audio chunks."""

    @patch("src.voice.wake_word.openwakeword")
    def test_detection_above_threshold(self, mock_oww):
        """Audio chunk with high confidence triggers detection."""
        mock_model = MagicMock()
        mock_model.predict.return_value = {"hey_mike": 0.85}
        mock_oww.Model.return_value = mock_model

        detector = WakeWordDetector(threshold=0.7)
        chunk = np.zeros(1600, dtype=np.int16)
        result = detector.process(chunk)

        assert result is not None
        assert isinstance(result, WakeWordEvent)
        assert result.confidence == 0.85
        assert result.detected is True

    @patch("src.voice.wake_word.openwakeword")
    def test_no_detection_below_threshold(self, mock_oww):
        """Audio chunk with low confidence returns None."""
        mock_model = MagicMock()
        mock_model.predict.return_value = {"hey_mike": 0.3}
        mock_oww.Model.return_value = mock_model

        detector = WakeWordDetector(threshold=0.7)
        chunk = np.zeros(1600, dtype=np.int16)
        result = detector.process(chunk)

        assert result is None

    @patch("src.voice.wake_word.openwakeword")
    def test_exact_threshold_triggers(self, mock_oww):
        """Confidence exactly at threshold triggers detection."""
        mock_model = MagicMock()
        mock_model.predict.return_value = {"hey_mike": 0.7}
        mock_oww.Model.return_value = mock_model

        detector = WakeWordDetector(threshold=0.7)
        chunk = np.zeros(1600, dtype=np.int16)
        result = detector.process(chunk)

        assert result is not None
        assert result.detected is True


class TestWakeWordReset:
    """Test reset behavior after detection."""

    @patch("src.voice.wake_word.openwakeword")
    def test_reset_clears_state(self, mock_oww):
        """Reset allows fresh detection after a previous trigger."""
        mock_model = MagicMock()
        mock_oww.Model.return_value = mock_model

        detector = WakeWordDetector()
        detector.reset()

        mock_model.reset.assert_called_once()

    @patch("src.voice.wake_word.openwakeword")
    def test_multiple_detections_require_reset(self, mock_oww):
        """After detection, subsequent chunks are ignored until reset."""
        mock_model = MagicMock()
        mock_model.predict.return_value = {"hey_mike": 0.9}
        mock_oww.Model.return_value = mock_model

        detector = WakeWordDetector(threshold=0.7)
        chunk = np.zeros(1600, dtype=np.int16)

        # First detection succeeds
        result1 = detector.process(chunk)
        assert result1 is not None

        # Second detection is suppressed (already triggered)
        result2 = detector.process(chunk)
        assert result2 is None

        # After reset, detection works again
        detector.reset()
        result3 = detector.process(chunk)
        assert result3 is not None
