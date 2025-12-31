import os

async def generate_minimax_tts(text: str) -> str:
    content = (text or "").strip()
    if not content:
        return ""
    base_url = os.getenv("MINIMAX_TTS_URL")
    api_key = os.getenv("MINIMAX_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError("Missing env vars: MINIMAX_TTS_URL / MINIMAX_API_KEY")
    return base_url
