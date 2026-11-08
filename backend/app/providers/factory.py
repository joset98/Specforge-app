from app.config import Settings
from app.providers.base import LLMProvider, ProviderError
from app.providers.claude import ClaudeProvider
from app.providers.openai import OpenAIProvider


def make_provider(provider: str | None, user_key: str | None, settings: Settings) -> LLMProvider:
    name = provider or settings.default_provider
    if name not in ("claude", "openai"):
        raise ProviderError("auth", f"Unknown LLM provider '{name}'. Use claude or openai.")
    owner_key = settings.anthropic_api_key if name == "claude" else settings.openai_api_key
    key = user_key or owner_key
    if not key:
        raise ProviderError("auth", "No API key available for this provider.")
    if name == "claude":
        return ClaudeProvider(key, settings.claude_model)
    if not settings.openai_model:
        raise ProviderError("upstream", "OPENAI_MODEL is not configured on the server.")
    return OpenAIProvider(key, settings.openai_model)
