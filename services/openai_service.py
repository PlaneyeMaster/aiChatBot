import os
import json
from openai import AsyncOpenAI
from typing import AsyncGenerator

def _client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing env var: OPENAI_API_KEY")
    return AsyncOpenAI(api_key=api_key)

def model_name() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

async def get_chat_stream(messages: list) -> AsyncGenerator[str, None]:
    client = _client()
    
    # stream=True 설정이 핵심입니다
    stream = await client.chat.completions.create(
        model=model_name(),
        messages=messages,
        stream=True
    )

    async for chunk in stream:
        # chunk.choices[0].delta.content에 실제 텍스트 조각이 담깁니다
        content = chunk.choices[0].delta.content
        if content:
            yield content