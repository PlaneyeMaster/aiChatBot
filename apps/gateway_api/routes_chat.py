import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from repos.supabase_repo import (
    get_session_by_id,
    get_character_by_id,
    get_scenario_by_id,
    get_user_by_id,
)
from services.openai_service import _client, model_name
from services.prompt_service import build_system_prompt

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatStreamRequest(BaseModel):
    session_id: str
    text: str

def sse(data: dict) -> str:
    # SSE 한 이벤트 라인 포맷
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

@router.post("/stream")
async def chat_stream(req: ChatStreamRequest):
    # (앞부분 Supabase 데이터 로드 로직은 동일)
    sess = get_session_by_id(req.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    character = get_character_by_id(sess["character_id"])
    scenario = get_scenario_by_id(sess["scenario_id"])
    if not character or not scenario:
        raise HTTPException(status_code=400, detail="Invalid session mapping")

    user_profile = None
    if sess.get("user_id"):
        user_profile = get_user_by_id(sess["user_id"])

    system_prompt = build_system_prompt(
        persona_prompt=character.get("persona_prompt", ""),
        scenario_prompt=scenario.get("scenario_prompt", ""),
        user_profile=user_profile,
    )

    client = _client()
    model = model_name()

    async def event_generator():
        yield sse({"type": "meta", "event": "start", "model": model})

        try:
            # client.chat.completions.create를 사용하고 stream=True를 설정해야 합니다
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": req.text},
                ],
                stream=True, # 스트리밍 활성화
            )

            # 비동기 반복문을 통해 스트림 데이터를 처리합니다
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    delta_text = chunk.choices[0].delta.content
                    yield sse({"type": "delta", "text": delta_text})
            
            yield sse({"type": "meta", "event": "done"})

        except Exception as e:
            # 에러 발생 시 SSE 형식으로 에러 메시지 전송
            yield sse({"type": "error", "message": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
