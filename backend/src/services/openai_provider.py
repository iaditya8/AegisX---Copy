import logging
import os
from typing import Optional

import httpx
from src.services.ai_provider import AIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        # Allow passing api_key (useful for testing), falling back to env var
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.url = "https://api.openai.com/v1/chat/completions"

    def get_name(self) -> str:
        return "openai"

    def get_version(self) -> str:
        return self.model

    async def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        # Timeout settings
        timeout = httpx.Timeout(30.0, connect=10.0)

        # Retry loop for transient errors (up to 3 attempts)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self.url, headers=headers, json=payload
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning(f"OpenAI generation attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise e
        raise ValueError("AI generation failed after maximum retries")
