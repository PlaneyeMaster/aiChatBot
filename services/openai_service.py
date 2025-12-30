import os
from openai import AsyncOpenAI

def _client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing env var: OPENAI_API_KEY")
    return AsyncOpenAI(api_key=api_key)

def model_name() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
