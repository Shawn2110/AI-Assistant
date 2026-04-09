"""Configuration loader - merges settings.yaml with environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file
load_dotenv()

# Project root
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = ROOT_DIR / "config"


class ProviderConfig(BaseModel):
    enabled: bool = False
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    tier: str = "free"
    description: str = ""
    api_key_env: str = ""
    base_url: str = ""

    @property
    def api_key(self) -> str | None:
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return None


class AIConfig(BaseModel):
    active_provider: str | None = None
    overrides: dict[str, str] = Field(default_factory=dict)
    fallback_chain: list[str] = Field(default_factory=lambda: ["groq", "gemini", "ollama"])


class VoiceConfig(BaseModel):
    enabled: bool = True
    stt_engine: str = "vosk"
    tts_engine: str = "edge_tts"
    tts_voice: str = "en-US-GuyNeural"
    silence_threshold_ms: int = 500
    listen_timeout_s: int = 10


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8765
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


class TunnelConfig(BaseModel):
    enabled: bool = False
    provider: str = "ngrok"
    ngrok: dict[str, Any] = Field(default_factory=dict)


class AssistantInfo(BaseModel):
    name: str = "Assistant"
    wake_word: str = "hey assistant"
    personality: str = "You are a helpful personal AI assistant."


class IntegrationToggle(BaseModel):
    enabled: bool = False


class Settings(BaseModel):
    assistant: AssistantInfo = Field(default_factory=AssistantInfo, alias="A")
    ai: AIConfig = Field(default_factory=AIConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    tunnel: TunnelConfig = Field(default_factory=TunnelConfig)
    integrations: dict[str, IntegrationToggle] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    def get_active_provider(self) -> ProviderConfig:
        """Get the currently active AI provider config."""
        name = self.ai.active_provider
        if not name or name not in self.providers:
            raise ValueError(
                f"No active provider set. Run 'assistant setup' to choose one. "
                f"Available: {list(self.providers.keys())}"
            )
        provider = self.providers[name]
        if not provider.enabled:
            raise ValueError(f"Provider '{name}' is not enabled. Enable it in settings.yaml.")
        return provider

    def get_provider_for_category(self, category: str) -> tuple[str, ProviderConfig]:
        """Get the provider name and config for a task category."""
        # Check overrides first
        override_name = self.ai.overrides.get(category)
        if override_name and override_name in self.providers:
            provider = self.providers[override_name]
            if provider.enabled:
                return override_name, provider

        # Fall back to active provider
        name = self.ai.active_provider
        if name and name in self.providers and self.providers[name].enabled:
            return name, self.providers[name]

        # Try fallback chain
        for name in self.ai.fallback_chain:
            if name in self.providers and self.providers[name].enabled:
                return name, self.providers[name]

        raise ValueError("No AI provider available. Run 'assistant setup' to configure one.")

    def get_enabled_providers(self) -> dict[str, ProviderConfig]:
        """Get all enabled providers."""
        return {k: v for k, v in self.providers.items() if v.enabled}


def load_settings(config_path: Path | None = None) -> Settings:
    """Load settings from YAML file, merged with environment variables."""
    if config_path is None:
        config_path = CONFIG_DIR / "settings.yaml"

    if not config_path.exists():
        return Settings()

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    return Settings.model_validate(raw)


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance (lazy loaded)."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from disk."""
    global _settings
    _settings = load_settings()
    return _settings
