"""Tests for voice configuration."""

import pytest

from src.core.config import VoiceConfig, Settings


class TestVoiceConfigDefaults:
    """Test default values for voice configuration."""

    def test_enabled_by_default(self):
        """Voice is enabled by default."""
        config = VoiceConfig()
        assert config.enabled is True

    def test_default_stt_engine(self):
        """Default STT engine is vosk."""
        config = VoiceConfig()
        assert config.stt_engine == "vosk"

    def test_default_tts_engine(self):
        """Default TTS engine is edge_tts."""
        config = VoiceConfig()
        assert config.tts_engine == "edge_tts"

    def test_default_tts_voice(self):
        """Default TTS voice is en-US-GuyNeural."""
        config = VoiceConfig()
        assert config.tts_voice == "en-US-GuyNeural"

    def test_default_wake_threshold(self):
        """Default wake word threshold is 0.7."""
        config = VoiceConfig()
        assert config.wake_threshold == 0.7

    def test_default_vosk_model_path(self):
        """Default Vosk model path is config/vosk-model."""
        config = VoiceConfig()
        assert config.vosk_model_path == "config/vosk-model"

    def test_default_input_device(self):
        """Default input device is None (system default)."""
        config = VoiceConfig()
        assert config.input_device is None


class TestVoiceConfigCustom:
    """Test custom values."""

    def test_custom_threshold(self):
        """Custom wake threshold is accepted."""
        config = VoiceConfig(wake_threshold=0.5)
        assert config.wake_threshold == 0.5

    def test_custom_model_path(self):
        """Custom Vosk model path is accepted."""
        config = VoiceConfig(vosk_model_path="/custom/model")
        assert config.vosk_model_path == "/custom/model"

    def test_custom_input_device(self):
        """Custom input device index is accepted."""
        config = VoiceConfig(input_device=2)
        assert config.input_device == 2


class TestVoiceConfigValidation:
    """Test validation of config values."""

    def test_threshold_between_0_and_1(self):
        """Threshold must be between 0 and 1."""
        with pytest.raises(Exception):
            VoiceConfig(wake_threshold=1.5)

        with pytest.raises(Exception):
            VoiceConfig(wake_threshold=-0.1)

    def test_threshold_boundaries_valid(self):
        """Threshold at 0 and 1 are valid."""
        config_zero = VoiceConfig(wake_threshold=0.0)
        assert config_zero.wake_threshold == 0.0

        config_one = VoiceConfig(wake_threshold=1.0)
        assert config_one.wake_threshold == 1.0


class TestSettingsVoiceSection:
    """Test that Settings loads voice config properly."""

    def test_settings_has_voice_config(self):
        """Settings includes VoiceConfig with defaults."""
        settings = Settings()
        assert isinstance(settings.voice, VoiceConfig)
        assert settings.voice.enabled is True

    def test_voice_config_missing_section_uses_defaults(self):
        """When voice section is absent from YAML, defaults are used."""
        settings = Settings.model_validate({})
        assert settings.voice.wake_threshold == 0.7
        assert settings.voice.vosk_model_path == "config/vosk-model"
