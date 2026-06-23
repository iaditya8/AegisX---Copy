from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Asynchronously send a prompt to the LLM and return the response."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of the AI provider (e.g., 'openai')."""
        pass

    @abstractmethod
    def get_version(self) -> str:
        """Return the active model version (e.g., 'gpt-4o-mini')."""
        pass
