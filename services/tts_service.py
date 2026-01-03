import httpx
import os

async def generate_minimax_tts(text: str):
    # Minimax API 호출 (예시 구조)
    url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={os.getenv('MINIMAX_GROUP_ID')}"
    headers = {"Authorization": f"Bearer {os.getenv('MINIMAX_API_KEY')}", "Content-Type": "application/json"}
    
    payload = {
        "model": "speech-01-turbo",
        "text": text,
        "voice_setting": {"voice_id": "sweet_child_voice"} # 캐릭터별 목소리 설정 가능
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        return resp.json().get("data", {}).get("audio_url") # URL 또는 바이너리 반환