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
from repos.supabase_repo import insert_message
from services.rag_personal import retrieve_personal_memory
from services.memory_writer import write_personal_memory

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

    # 1) 개인 메모리 검색 (user_id 없으면 스킵)
    memories = []
    if sess.get("user_id"):
        memories = await retrieve_personal_memory(sess["user_id"], req.text, top_k=5)

    system_prompt = build_system_prompt(
        persona_prompt=character.get("persona_prompt", ""),
        scenario_prompt=scenario.get("scenario_prompt", ""),
        user_profile=user_profile,
        memories=memories,
    )

    model = model_name()

    async def event_generator():
        yield sse({"type": "meta", "event": "start", "model": model})

        # 2) 유저 메시지 저장
        try:
            insert_message(session_id=req.session_id, user_id=sess.get("user_id"), role="user", content=req.text)
        except Exception:
            pass  # MVP: 저장 실패가 스트리밍을 막지 않게

        assistant_full = ""

        try:
            resp = await openai_client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": req.text},
                ],
                stream=True,
            )

            async for chunk in resp:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    assistant_full += delta.content
                    yield sse({"type": "delta", "text": delta.content})

            # 3) assistant 메시지 저장
            try:
                insert_message(session_id=req.session_id, user_id=sess.get("user_id"), role="assistant", content=assistant_full)
            except Exception:
                pass

            # 4) 개인 메모리 추출+저장 (user_id 없으면 스킵)
            if sess.get("user_id"):
                try:
                    result = await write_personal_memory(
                        user_id=sess["user_id"],
                        session_id=req.session_id,
                        user_text=req.text,
                        assistant_text=assistant_full,
                    )
                    yield sse({"type": "meta", "event": "memory_saved", "count": result.get("saved", 0)})
                except Exception:
                    # 메모리 실패도 스트림을 망치지 않음
                    yield sse({"type": "meta", "event": "memory_saved", "count": 0})

            yield sse({"type": "meta", "event": "done"})

        except Exception as e:
            yield sse({"type": "error", "message": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
