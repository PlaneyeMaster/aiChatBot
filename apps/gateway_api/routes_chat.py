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
        # 1) 시작 이벤트(프론트에서 로딩 표시 용)
        yield sse({"type": "meta", "event": "start", "model": model})

        try:
            stream = await client.responses.stream(
                model=model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": req.text},
                ],
            )

            async with stream:
                async for event in stream:
                    # 텍스트 델타만 골라서 내려주기
                    if event.type == "response.output_text.delta":
                        yield sse({"type": "delta", "text": event.delta})
                    elif event.type == "response.completed":
                        yield sse({"type": "meta", "event": "done"})
        except Exception as e:
            yield sse({"type": "error", "message": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
