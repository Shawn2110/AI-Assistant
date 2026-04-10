"""AI provider factory - creates LangChain LLM instances from config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.language_models.chat_models import BaseChatModel

from src.core.exceptions import ProviderError, ProviderNotAvailableError
from src.core.logger import get_logger

if TYPE_CHECKING:
    from src.core.config import ProviderConfig

log = get_logger(__name__)


def create_provider(name: str, config: ProviderConfig) -> BaseChatModel:
    """Create a LangChain chat model from provider name and config.

    Built-in providers: groq, gemini, ollama, claude, openai.
    Any other name is treated as a custom OpenAI-compatible provider
    (LM Studio, vLLM, LocalAI, text-generation-webui, etc.)
    """
    match name:
        case "groq":
            return _create_groq(config)
        case "gemini":
            return _create_gemini(config)
        case "ollama":
            return _create_ollama(config)
        case "claude":
            return _create_claude(config)
        case "openai":
            return _create_openai(config)
        case _:
            # Custom provider — treat as OpenAI-compatible endpoint
            return _create_custom(name, config)


def _create_groq(config: ProviderConfig) -> BaseChatModel:
    try:
        from langchain_groq import ChatGroq
    except ImportError:
        raise ProviderError("groq", "Install langchain-groq: pip install langchain-groq")

    api_key = config.api_key
    if not api_key:
        raise ProviderError("groq", "GROQ_API_KEY not set in .env")

    return ChatGroq(
        model=config.model,
        api_key=api_key,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )


def _create_gemini(config: ProviderConfig) -> BaseChatModel:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        raise ProviderError("gemini", "Install langchain-google-genai")

    api_key = config.api_key
    if not api_key:
        raise ProviderError("gemini", "GEMINI_API_KEY not set in .env")

    return ChatGoogleGenerativeAI(
        model=config.model,
        google_api_key=api_key,
        max_output_tokens=config.max_tokens,
        temperature=config.temperature,
    )


def _create_ollama(config: ProviderConfig) -> BaseChatModel:
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        raise ProviderError("ollama", "Install langchain-ollama")

    return ChatOllama(
        model=config.model,
        base_url=config.base_url or "http://localhost:11434",
        num_predict=config.max_tokens,
        temperature=config.temperature,
    )


def _create_claude(config: ProviderConfig) -> BaseChatModel:
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise ProviderError(
            "claude", "Install langchain-anthropic: pip install ai-assistant[paid]"
        )

    api_key = config.api_key
    if not api_key:
        raise ProviderError("claude", "ANTHROPIC_API_KEY not set in .env")

    return ChatAnthropic(
        model=config.model,
        api_key=api_key,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )


def _create_openai(config: ProviderConfig) -> BaseChatModel:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ProviderError(
            "openai", "Install langchain-openai: pip install ai-assistant[paid]"
        )

    api_key = config.api_key
    if not api_key:
        raise ProviderError("openai", "OPENAI_API_KEY not set in .env")

    return ChatOpenAI(
        model=config.model,
        api_key=api_key,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )


def _create_custom(name: str, config: ProviderConfig) -> BaseChatModel:
    """Create a custom provider using any OpenAI-compatible endpoint.

    Works with LM Studio, vLLM, LocalAI, text-generation-webui, llama.cpp, etc.
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ProviderError(
            name, "Install langchain-openai: pip install langchain-openai"
        )

    if not config.base_url:
        raise ProviderError(
            name, f"Custom provider '{name}' needs a base_url (e.g., http://localhost:1234/v1)"
        )

    # API key is optional for local servers
    api_key = config.api_key or "not-needed"

    log.info("ai.provider.custom", name=name, base_url=config.base_url, model=config.model)
    return ChatOpenAI(
        model=config.model,
        api_key=api_key,
        base_url=config.base_url,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )
