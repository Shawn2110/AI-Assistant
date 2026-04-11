"""Wake word detector - listens for 'Hey Mike' using openwakeword."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import openwakeword

from src.core.exceptions import VoiceError


@dataclass
class WakeWordEvent:
    """Emitted when the wake word is detected."""
    detected: bool
    confidence: float


class WakeWordDetector:
    """Detects a wake word in audio chunks using openwakeword.

    After detection, further calls to process() return None until reset() is called.
    This prevents duplicate triggers from the same utterance.
    """

    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        self._triggered = False
        try:
            self._model = openwakeword.Model()
        except Exception as exc:
            raise VoiceError(f"Failed to load wake word model: {exc}") from exc

    def process(self, chunk: np.ndarray) -> WakeWordEvent | None:
        """Feed an audio chunk and check for wake word.

        Returns a WakeWordEvent if the wake word is detected above the
        confidence threshold, or None otherwise. After a detection,
        returns None until reset() is called.
        """
        if self._triggered:
            return None

        predictions = self._model.predict(chunk)

        # Find the highest confidence score across all wake word models
        max_confidence = 0.0
        for score in predictions.values():
            if score > max_confidence:
                max_confidence = score

        if max_confidence >= self.threshold:
            self._triggered = True
            return WakeWordEvent(detected=True, confidence=max_confidence)

        return None

    def reset(self) -> None:
        """Reset the detector to allow new detections."""
        self._triggered = False
        self._model.reset()
