"""Custom exception hierarchy for the AI Assistant."""


class AssistantError(Exception):
    """Base exception for all assistant errors."""


class ProviderError(AssistantError):
    """Error from an AI provider (API failure, rate limit, etc.)."""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ProviderNotAvailableError(ProviderError):
    """Provider is not configured or all providers exhausted."""


class IntegrationError(AssistantError):
    """Error from an integration (Google, Microsoft, system, etc.)."""

    def __init__(self, integration: str, message: str):
        self.integration = integration
        super().__init__(f"[{integration}] {message}")


class ConfigError(AssistantError):
    """Configuration error (missing keys, invalid values)."""


class VoiceError(AssistantError):
    """Voice pipeline error (mic, STT, TTS)."""


class AuthError(AssistantError):
    """Authentication/authorization error."""
