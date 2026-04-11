"""Text-to-speech engine - speaks text using Edge-TTS (online) or pyttsx3 (offline)."""

from __future__ import annotations

import os
import tempfile

import edge_tts
import pyttsx3
import sounddevice as sd
import soundfile as sf

from src.core.exceptions import VoiceError
from src.core.logger import get_logger

log = get_logger(__name__)


def play_audio_file(path: str) -> None:
    """Play a WAV/MP3 file through the default audio output."""
    data, sample_rate = sf.read(path)
    sd.play(data, samplerate=sample_rate)
    sd.wait()


class TextToSpeech:
    """Speaks text aloud using Edge-TTS (online) with pyttsx3 fallback (offline).

    Usage::

        tts = TextToSpeech(voice="en-US-GuyNeural")
        await tts.speak("Hello, how can I help?")
    """

    def __init__(self, voice: str = "en-US-GuyNeural"):
        self.voice = voice

    async def speak(self, text: str) -> None:
        """Speak the given text aloud.

        Tries Edge-TTS first. If that fails (no internet), falls back to pyttsx3.
        Empty or whitespace-only strings are silently ignored.
        """
        if not text or not text.strip():
            return

        try:
            await self._speak_edge_tts(text)
        except Exception as exc:
            log.warning("edge_tts.failed", error=str(exc))
            self._speak_pyttsx3(text)

    async def _speak_edge_tts(self, text: str) -> None:
        """Speak using Edge-TTS (requires internet)."""
        communicate = edge_tts.Communicate(text=text, voice=self.voice)
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            await communicate.save(tmp_path)
            play_audio_file(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _speak_pyttsx3(self, text: str) -> None:
        """Speak using pyttsx3 (offline fallback)."""
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            raise VoiceError(f"TTS failed (both Edge-TTS and pyttsx3): {exc}") from exc
