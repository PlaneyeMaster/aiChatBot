import os
from openai import AsyncOpenAI
from typing import AsyncGenerator

_client_instance: AsyncOpenAI | None = None

def client() -> AsyncOpenAI:
    """Singleton AsyncOpenAI client."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing env var: OPENAI_API_KEY")

    _client_instance = AsyncOpenAI(api_key=api_key)
    return _client_instance

def model_name() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

async def get_chat_stream(messages: list, model: str | None = None) -> AsyncGenerator[str, None]:
    c = client()
    stream = await c.chat.completions.create(
        model=model or model_name(),
        messages=messages,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content
