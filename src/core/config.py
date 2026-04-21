"""Configuration loader - merges settings.yaml with environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

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
    fallback_chain: list[str] = Field(default_factory=lambda: ["ollama", "groq"])
    # Advanced: optional per-task provider routing
    # e.g., {"coding": "claude", "research": "groq", "email": "gemini"}
    task_routing: dict[str, str] = Field(default_factory=dict)


class RouterConfig(BaseModel):
    """Configuration for the intent router that sits in front of the ReAct agent."""

    enabled: bool = True
    classifier_enabled: bool = True
    classifier_type: Literal["embedding", "ollama"] = "embedding"
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    embedding_model: str = "all-MiniLM-L6-v2"
    ollama_model: str = "qwen2.5:3b"
    intents_path: str = "config/intents.yaml"


class VoiceConfig(BaseModel):
    enabled: bool = True
    stt_engine: str = "vosk"
    tts_engine: str = "edge_tts"
    tts_voice: str = "en-US-GuyNeural"
    silence_threshold_ms: int = 500
    listen_timeout_s: int = 10
    wake_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    vosk_model_path: str = "config/vosk-model"
    input_device: int | None = None


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8765
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


class TunnelConfig(BaseModel):
    enabled: bool = False
    provider: str = "ngrok"
    ngrok: dict[str, Any] = Field(default_factory=dict)


class PersonaConfig(BaseModel):
    name: str = "Assistant"
    wake_word: str = "hey assistant"
    tagline: str = "At your service."
    personality: str = (
        "You are {name}, a personal AI assistant. "
        "You speak in a professional yet witty tone, similar to Jarvis from Iron Man. "
        "You are efficient, slightly formal, but show personality through dry humor "
        "and clever observations. You address the user respectfully and always stay "
        "focused on getting things done. You keep responses concise unless detail is "
        "requested. When executing tasks, you confirm actions briefly and report results "
        "clearly. You never say 'as an AI' or break character."
    )
    tone: str = "professional-witty"  # professional-witty | friendly | formal | casual | custom
    greeting: str = "Good {time_of_day}. {name} online. How can I assist you?"
    farewell: str = "Until next time. {name} signing off."

    def get_system_prompt(self) -> str:
        """Build the full system prompt with the persona's name injected."""
        return self.personality.format(name=self.name)

    def get_greeting(self) -> str:
        """Get a time-appropriate greeting."""
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            tod = "morning"
        elif hour < 17:
            tod = "afternoon"
        else:
            tod = "evening"
        return self.greeting.format(time_of_day=tod, name=self.name)

    def get_farewell(self) -> str:
        return self.farewell.format(name=self.name)


class IntegrationToggle(BaseModel):
    enabled: bool = False


class VoiceAutomation(BaseModel):
    enabled: bool = False
    trigger: str = ""
    action: str = ""
    provider: str | None = None
    custom: bool = False


class Settings(BaseModel):
    persona: PersonaConfig = Field(default_factory=PersonaConfig, alias="persona")
    ai: AIConfig = Field(default_factory=AIConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    custom_providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    router: RouterConfig = Field(default_factory=RouterConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    tunnel: TunnelConfig = Field(default_factory=TunnelConfig)
    integrations: dict[str, IntegrationToggle] = Field(default_factory=dict)
    voice_automations: dict[str, VoiceAutomation] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @property
    def all_providers(self) -> dict[str, ProviderConfig]:
        """All providers including custom ones."""
        return {**self.providers, **self.custom_providers}

    def get_active_provider(self) -> tuple[str, ProviderConfig]:
        """Get the currently active AI provider name and config."""
        name = self.ai.active_provider
        all_provs = self.all_providers
        if not name or name not in all_provs:
            raise ValueError(
                f"No active provider set. Run 'python -m src --setup' to choose one. "
                f"Available: {list(all_provs.keys())}"
            )
        provider = all_provs[name]
        if not provider.enabled:
            raise ValueError(f"Provider '{name}' is not enabled.")
        return name, provider

    def get_provider_for_task(self, task_type: str | None = None) -> tuple[str, ProviderConfig]:
        """Get the best provider for a task type.

        If task_routing is configured and has a match, uses that provider.
        Otherwise falls back to the active provider → fallback chain.
        """
        all_provs = self.all_providers

        # Check task routing (advanced: user assigns different AIs to tasks)
        if task_type and self.ai.task_routing:
            routed = self.ai.task_routing.get(task_type)
            if routed and routed in all_provs and all_provs[routed].enabled:
                return routed, all_provs[routed]

        # Active provider
        active = self.ai.active_provider
        if active and active in all_provs and all_provs[active].enabled:
            return active, all_provs[active]

        # Fallback chain
        for name in self.ai.fallback_chain:
            if name in all_provs and all_provs[name].enabled:
                return name, all_provs[name]

        # Any enabled
        for name, config in all_provs.items():
            if config.enabled:
                return name, config

        raise ValueError("No AI provider available. Run 'python -m src --setup' to configure one.")

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
