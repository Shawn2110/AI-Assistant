"""Speech-to-text engine - transcribes audio chunks using Vosk."""

from __future__ import annotations

import json

import numpy as np
import vosk

from src.core.exceptions import VoiceError


class SpeechToText:
    """Offline speech-to-text using Vosk.

    Feed audio chunks via feed(). When Vosk detects end-of-utterance
    (silence), feed() returns the final transcript string. Otherwise
    it returns None (still accumulating).

    Call finalize() to flush any remaining audio at the end of a session.
    Call reset() to start a new utterance with a fresh recognizer.
    """

    def __init__(self, model_path: str, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        try:
            self._model = vosk.Model(model_path=model_path)
        except Exception as exc:
            raise VoiceError(f"Failed to load Vosk model: {exc}") from exc
        self._recognizer = vosk.KaldiRecognizer(self._model, self.sample_rate)

    def feed(self, chunk: np.ndarray) -> str | None:
        """Feed an audio chunk to the recognizer.

        Returns the final transcript string when end-of-utterance is
        detected, or None if still accumulating.
        """
        audio_bytes = chunk.tobytes()
        if self._recognizer.AcceptWaveform(audio_bytes):
            result = json.loads(self._recognizer.Result())
            text = result.get("text", "").strip()
            return text if text else None
        return None

    def finalize(self) -> str | None:
        """Flush remaining audio and return any final transcript."""
        result = json.loads(self._recognizer.FinalResult())
        text = result.get("text", "").strip()
        return text if text else None

    def reset(self) -> None:
        """Create a fresh recognizer for the next utterance."""
        self._recognizer = vosk.KaldiRecognizer(self._model, self.sample_rate)
