import os
from openai import AsyncOpenAI
from services.openai_service import client as openai_client

def embed_model() -> str:
    return os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

async def embed_text(text: str) -> list[float]:
    c: AsyncOpenAI = openai_client()
    resp = await c.embeddings.create(model=embed_model(), input=text)
    return resp.data[0].embedding
