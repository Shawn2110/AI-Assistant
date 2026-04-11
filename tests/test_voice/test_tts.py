"""Tests for text-to-speech engine module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.voice.tts import TextToSpeech


class TestTextToSpeechInit:
    """Test TextToSpeech instantiation."""

    def test_default_voice(self):
        """Default voice is en-US-GuyNeural."""
        tts = TextToSpeech()
        assert tts.voice == "en-US-GuyNeural"

    def test_custom_voice(self):
        """Custom voice name is accepted."""
        tts = TextToSpeech(voice="en-US-JennyNeural")
        assert tts.voice == "en-US-JennyNeural"


class TestTextToSpeechEdgeTTS:
    """Test Edge-TTS online path."""

    @pytest.mark.asyncio
    async def test_speak_uses_edge_tts(self):
        """speak() uses edge_tts.Communicate when online."""
        tts = TextToSpeech()

        with patch("src.voice.tts.edge_tts") as mock_edge:
            mock_communicate = AsyncMock()
            mock_communicate.save.return_value = None
            mock_edge.Communicate.return_value = mock_communicate

            with patch("src.voice.tts.play_audio_file") as mock_play:
                mock_play.return_value = None
                await tts.speak("Hello world")

            mock_edge.Communicate.assert_called_once_with(
                text="Hello world", voice="en-US-GuyNeural"
            )
            mock_communicate.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_speak_custom_voice(self):
        """speak() passes the configured voice to Edge-TTS."""
        tts = TextToSpeech(voice="en-US-JennyNeural")

        with patch("src.voice.tts.edge_tts") as mock_edge:
            mock_communicate = AsyncMock()
            mock_communicate.save.return_value = None
            mock_edge.Communicate.return_value = mock_communicate

            with patch("src.voice.tts.play_audio_file"):
                await tts.speak("Test")

            mock_edge.Communicate.assert_called_once_with(
                text="Test", voice="en-US-JennyNeural"
            )


class TestTextToSpeechFallback:
    """Test pyttsx3 offline fallback."""

    @pytest.mark.asyncio
    async def test_fallback_to_pyttsx3_on_edge_tts_failure(self):
        """When Edge-TTS fails, falls back to pyttsx3."""
        tts = TextToSpeech()

        with patch("src.voice.tts.edge_tts") as mock_edge:
            mock_edge.Communicate.side_effect = Exception("No internet")

            with patch("src.voice.tts.pyttsx3") as mock_pyttsx3:
                mock_engine = MagicMock()
                mock_pyttsx3.init.return_value = mock_engine

                await tts.speak("Fallback test")

                mock_engine.say.assert_called_once_with("Fallback test")
                mock_engine.runAndWait.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_save_failure(self):
        """When Edge-TTS save() fails, falls back to pyttsx3."""
        tts = TextToSpeech()

        with patch("src.voice.tts.edge_tts") as mock_edge:
            mock_communicate = AsyncMock()
            mock_communicate.save.side_effect = Exception("Connection lost")
            mock_edge.Communicate.return_value = mock_communicate

            with patch("src.voice.tts.pyttsx3") as mock_pyttsx3:
                mock_engine = MagicMock()
                mock_pyttsx3.init.return_value = mock_engine

                await tts.speak("Connection lost test")

                mock_engine.say.assert_called_once_with("Connection lost test")


class TestTextToSpeechEdgeCases:
    """Test edge cases."""

    @pytest.mark.asyncio
    async def test_empty_string_is_noop(self):
        """Speaking an empty string does nothing."""
        tts = TextToSpeech()

        with patch("src.voice.tts.edge_tts") as mock_edge:
            await tts.speak("")
            mock_edge.Communicate.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_only_is_noop(self):
        """Speaking whitespace-only string does nothing."""
        tts = TextToSpeech()

        with patch("src.voice.tts.edge_tts") as mock_edge:
            await tts.speak("   \n  ")
            mock_edge.Communicate.assert_not_called()

    @pytest.mark.asyncio
    async def test_long_text_is_accepted(self):
        """Long text is passed through without truncation."""
        tts = TextToSpeech()
        long_text = "word " * 500

        with patch("src.voice.tts.edge_tts") as mock_edge:
            mock_communicate = AsyncMock()
            mock_communicate.save.return_value = None
            mock_edge.Communicate.return_value = mock_communicate

            with patch("src.voice.tts.play_audio_file"):
                await tts.speak(long_text)

            call_args = mock_edge.Communicate.call_args
            assert call_args[1]["text"] == long_text
