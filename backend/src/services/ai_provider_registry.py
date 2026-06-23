import os

from src.services.ai_provider import AIProvider
from src.services.openai_provider import OpenAIProvider


class AIProviderRegistry:
    _provider_instances = {}

    @classmethod
    def get_provider(cls) -> AIProvider:
        """Resolve the active AI provider based on environment variables."""
        provider_name = os.getenv("AI_PROVIDER", "openai").lower()

        if provider_name not in cls._provider_instances:
            if provider_name == "openai":
                cls._provider_instances[provider_name] = OpenAIProvider()
            else:
                raise ValueError(f"Unsupported AI provider: {provider_name}")

        return cls._provider_instances[provider_name]

    @classmethod
    def register_provider(cls, name: str, provider: AIProvider) -> None:
        """Register a provider instance manually (e.g. for testing)."""
        cls._provider_instances[name.lower()] = provider
