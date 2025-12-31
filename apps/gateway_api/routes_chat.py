import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from repos.supabase_repo import (
    get_session_by_id,
    get_character_by_id,
    get_scenario_by_id,
    supabase_client,
)
from services.openai_service import client as openai_client, model_name
from repos.supabase_repo import insert_message
from services.rag_personal import retrieve_personal_memory
from services.memory_writer import write_personal_memory

router = APIRouter(prefix="/chat", tags=["chat"])
_logger = logging.getLogger(__name__)

class ChatStreamRequest(BaseModel):
    session_id: str
    text: str

async def load_user_profile(user_id: str) -> Dict[str, Any]:
    """
    Supabase public.users에서 user profile을 조회.
    없으면 {} 반환.
    """
    try:
        sb = supabase_client()
        res = sb.table("users").select("id,tone,goal,expertise,age_band").eq("id", user_id).maybe_single().execute()
        data = getattr(res, "data", None) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def build_system_prompt(persona_prompt: str, scenario_prompt: str, profile: Dict[str, Any]) -> str:
    tone = profile.get("tone") or ""
    goal = profile.get("goal") or ""
    expertise = profile.get("expertise") or ""
    age_band = profile.get("age_band") or ""

    profile_block = []
    if tone:
        profile_block.append(f"- 말투(tone): {tone}")
    if goal:
        profile_block.append(f"- 목표(goal): {goal}")
    if expertise:
        profile_block.append(f"- 전문성 수준(expertise): {expertise}")
    if age_band:
        profile_block.append(f"- 연령대(age_band): {age_band}")

    profile_text = "\n".join(profile_block) if profile_block else "- (프로필 미지정)"

    return (
        "당신은 아래 지침을 최우선으로 따릅니다.\n\n"
        f"[캐릭터 페르소나]\n{persona_prompt}\n\n"
        f"[대화 시나리오]\n{scenario_prompt}\n\n"
        f"[사용자 프로필]\n{profile_text}\n\n"
        "규칙:\n"
        "- 사실/추측을 구분하고, 불확실하면 짧게 확인 질문 1개만 합니다.\n"
        "- 답변은 간결하고 실행 가능하게 정리합니다.\n"
    )

def sse_json(payload: Dict[str, Any]) -> str:
    # SSE 한 이벤트 라인 포맷
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

@router.post("/stream")
async def chat_stream(req: ChatStreamRequest):
    sess = get_session_by_id(req.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    character = get_character_by_id(sess["character_id"])
    scenario = get_scenario_by_id(sess["scenario_id"])
    if not character or not scenario:
        raise HTTPException(status_code=400, detail="Invalid session mapping")

    user_profile = {}
    if sess.get("user_id"):
        user_profile = await load_user_profile(sess["user_id"])

    # 1) 개인 메모리 검색 (user_id 없으면 스킵)
    memories = []
    if sess.get("user_id"):
        memories = await retrieve_personal_memory(sess["user_id"], req.text, top_k=5)

    system_prompt = build_system_prompt(
        persona_prompt=character.get("persona_prompt", ""),
        scenario_prompt=scenario.get("scenario_prompt", ""),
        profile=user_profile,
        memories=memories,
    )

    model = model_name()

    async def event_generator():
        yield sse_json({"type": "meta", "event": "start", "model": model})

        # 2) 유저 메시지 저장
        try:
            insert_message(session_id=req.session_id, user_id=sess.get("user_id"), role="user", content=req.text)
        except Exception:
            _logger.exception("chat_insert_message_failed", extra={"session_id": req.session_id, "role": "user"})

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
                    yield sse_json({"type": "delta", "text": delta.content})

            # 3) assistant 메시지 저장
            try:
                insert_message(session_id=req.session_id, user_id=sess.get("user_id"), role="assistant", content=assistant_full)
            except Exception:
                _logger.exception("chat_insert_message_failed", extra={"session_id": req.session_id, "role": "assistant"})

            # 4) 개인 메모리 추출+저장 (user_id 없으면 스킵)
            if sess.get("user_id"):
                try:
                    result = await write_personal_memory(
                        user_id=sess["user_id"],
                        session_id=req.session_id,
                        user_text=req.text,
                        assistant_text=assistant_full,
                    )
                    yield sse_json({"type": "meta", "event": "memory_saved", "count": result.get("saved", 0)})
                    yield sse_json({"type": "meta", "event": "memory_skipped_duplicate", "count": result.get("skipped_duplicate", 0)})
                except Exception:
                    # 메모리 실패도 스트림을 망치지 않음
                    _logger.exception("chat_memory_save_failed", extra={"session_id": req.session_id})
                    yield sse_json({"type": "meta", "event": "memory_saved", "count": 0})

            yield sse_json({"type": "meta", "event": "done"})

        except Exception as e:
            _logger.exception("chat_stream_failed", extra={"session_id": req.session_id})
            yield sse_json({"type": "error", "message": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
