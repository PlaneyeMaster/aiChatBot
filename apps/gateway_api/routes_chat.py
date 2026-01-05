import asyncio
import json
import logging
import os
import time
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from repos.supabase_repo import get_user_by_id
from services.openai_service import client as openai_client, model_name
from repos.supabase_repo import insert_message
from services.rag_personal import retrieve_personal_memory
from services.memory_writer import write_personal_memory
from repos.supabase_repo import supabase_client

router = APIRouter(prefix="/chat", tags=["chat"])
_logger = logging.getLogger(__name__)

class ChatStreamRequest(BaseModel):
    session_id: str
    text: str

def sse(data: dict) -> str:
    # SSE 한 이벤트 라인 포맷
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

@router.post("/stream")
async def chat_stream(req: ChatStreamRequest):
    req_started = time.monotonic()
    sb = supabase_client()
    session_id = req.session_id
    user_text = req.text

    sess = _get_session(sb, session_id)
    character = _get_character(sb, sess["character_id"])
    scenario = _get_scenario(sb, sess["scenario_id"])

    phase = (sess.get("phase") or PHASE_INTRO).strip() or PHASE_INTRO

    msg_res = (
        sb.table("messages")
        .select("id,role,content,created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )
    existing_msgs = getattr(msg_res, "data", None) or []
    user_turns = sum(1 for m in existing_msgs if m.get("role") == "user")

    if phase == PHASE_GUIDE and _should_reflect(user_turns, user_text):
        phase = PHASE_REFLECTION
        _update_session_phase(sb, session_id, PHASE_REFLECTION)

    user_profile = None
    if sess.get("user_id"):
        try:
            user_profile = get_user_by_id(sess["user_id"])
        except Exception:
            _logger.exception("chat_user_profile_failed", extra={"session_id": session_id})

    # 1) 개인 메모리 검색 (user_id 없으면 스킵)
    memories = []
    if sess.get("user_id"):
        try:
            t0 = time.monotonic()
            memories = await retrieve_personal_memory(sess["user_id"], user_text, top_k=2)
            _logger.info(
                "chat_memory_retrieved session_id=%s elapsed_ms=%d count=%d",
                session_id,
                int((time.monotonic() - t0) * 1000),
                len(memories),
            )
        except Exception:
            _logger.exception("chat_memory_retrieve_failed", extra={"session_id": session_id})

    t0 = time.monotonic()
    system_prompt = _build_system_prompt(
        character=character,
        scenario=scenario,
        phase=phase,
        user_profile=user_profile,
        memories=memories,
    )
    _logger.info(
        "chat_prompt_built session_id=%s elapsed_ms=%d prompt_chars=%d",
        session_id,
        int((time.monotonic() - t0) * 1000),
        len(system_prompt),
    )

    messages: list[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for m in existing_msgs:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})

    model = model_name()

    async def event_generator():
        yield sse({"type": "meta", "event": "start", "model": model})
        yield sse({"type": "meta", "event": "phase", "phase": phase})

        # 2) 유저 메시지 저장
        try:
            t0 = time.monotonic()
            insert_message(session_id=session_id, user_id=sess.get("user_id"), role="user", content=user_text)
            _logger.info(
                "chat_user_message_saved session_id=%s elapsed_ms=%d",
                session_id,
                int((time.monotonic() - t0) * 1000),
            )
        except Exception:
            _logger.exception("chat_insert_message_failed", extra={"session_id": session_id, "role": "user"})

        assistant_full = ""

        try:
            t0 = time.monotonic()
            resp = await openai_client().chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )
            _logger.info(
                "chat_llm_stream_started session_id=%s elapsed_ms=%d model=%s",
                session_id,
                int((time.monotonic() - t0) * 1000),
                model,
            )

            async for chunk in resp:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    if assistant_full == "":
                        _logger.info(
                            "chat_llm_ttfb session_id=%s elapsed_ms=%d",
                            session_id,
                            int((time.monotonic() - t0) * 1000),
                        )
                    assistant_full += delta.content
                    yield sse({"type": "delta", "text": delta.content})

            _logger.info(
                "chat_llm_stream_done session_id=%s elapsed_ms=%d assistant_chars=%d",
                session_id,
                int((time.monotonic() - t0) * 1000),
                len(assistant_full),
            )

            # 3) assistant 메시지 저장
            try:
                t0 = time.monotonic()
                insert_message(session_id=req.session_id, user_id=sess.get("user_id"), role="assistant", content=assistant_full)
                _logger.info(
                    "chat_assistant_message_saved session_id=%s elapsed_ms=%d",
                    session_id,
                    int((time.monotonic() - t0) * 1000),
                )
            except Exception:
                _logger.exception("chat_insert_message_failed", extra={"session_id": session_id, "role": "assistant"})

            def _after_done_phase_update() -> None:
                existing_phase = (sess.get("phase") or "").strip()
                if (not existing_phase or existing_phase == PHASE_INTRO) and phase == PHASE_INTRO:
                    _update_session_phase(sb, session_id, PHASE_GUIDE)
                elif phase == PHASE_REFLECTION:
                    _update_session_phase(sb, session_id, PHASE_WRAP)

            try:
                _after_done_phase_update()
                _logger.info(
                    "chat_phase_updated session_id=%s phase=%s",
                    session_id,
                    phase,
                )
            except Exception:
                _logger.exception("chat_phase_update_failed", extra={"session_id": session_id})

            # 4) 개인 메모리 추출+저장 (user_id 없으면 스킵)
            if sess.get("user_id"):
                if os.getenv("MEMORY_SAVE_BACKGROUND", "1") == "1":
                    async def _save_memory() -> None:
                        try:
                            t0 = time.monotonic()
                            result = await write_personal_memory(
                                user_id=sess["user_id"],
                                session_id=session_id,
                                user_text=user_text,
                                assistant_text=assistant_full,
                            )
                            _logger.info(
                                "chat_memory_saved session_id=%s elapsed_ms=%d saved=%d skipped_duplicate=%d",
                                session_id,
                                int((time.monotonic() - t0) * 1000),
                                result.get("saved", 0),
                                result.get("skipped_duplicate", 0),
                            )
                        except Exception:
                            _logger.exception("chat_memory_save_failed", extra={"session_id": session_id})

                    asyncio.create_task(_save_memory())
                    yield sse({"type": "meta", "event": "memory_queued"})
                else:
                    try:
                        t0 = time.monotonic()
                        result = await write_personal_memory(
                            user_id=sess["user_id"],
                            session_id=session_id,
                            user_text=user_text,
                            assistant_text=assistant_full,
                        )
                        _logger.info(
                            "chat_memory_saved session_id=%s elapsed_ms=%d saved=%d skipped_duplicate=%d",
                            session_id,
                            int((time.monotonic() - t0) * 1000),
                            result.get("saved", 0),
                            result.get("skipped_duplicate", 0),
                        )
                        yield sse({"type": "meta", "event": "memory_saved", "count": result.get("saved", 0)})
                        yield sse({"type": "meta", "event": "memory_skipped_duplicate", "count": result.get("skipped_duplicate", 0)})
                    except Exception:
                        # 메모리 실패도 스트림을 망치지 않음
                        _logger.exception("chat_memory_save_failed", extra={"session_id": session_id})
                        yield sse({"type": "meta", "event": "memory_saved", "count": 0})

            _logger.info(
                "chat_stream_done session_id=%s elapsed_ms=%d",
                session_id,
                int((time.monotonic() - req_started) * 1000),
            )
            yield sse({"type": "meta", "event": "done"})

        except Exception as e:
            _logger.exception("chat_stream_failed", extra={"session_id": session_id})
            yield sse({"type": "error", "message": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ===== Phase constants =====
PHASE_INTRO = "intro"
PHASE_GUIDE = "guide"
PHASE_REFLECTION = "reflection"
PHASE_WRAP = "wrap"

def _get_session(sb, session_id: str) -> Dict[str, Any]:
    res = sb.table("sessions").select("*").eq("id", session_id).limit(1).execute()
    rows = getattr(res, "data", None) or []
    if not rows:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    return rows[0]

def _get_character(sb, character_id: str) -> Dict[str, Any]:
    res = sb.table("characters").select("*").eq("id", character_id).limit(1).execute()
    rows = getattr(res, "data", None) or []
    if not rows:
        raise HTTPException(status_code=400, detail="Invalid character_id")
    return rows[0]

def _get_scenario(sb, scenario_id: str) -> Dict[str, Any]:
    res = sb.table("scenarios").select("*").eq("id", scenario_id).limit(1).execute()
    rows = getattr(res, "data", None) or []
    if not rows:
        raise HTTPException(status_code=400, detail="Invalid scenario_id")
    return rows[0]

def _update_session_phase(sb, session_id: str, phase: str) -> None:
    sb.table("sessions").update({"phase": phase}).eq("id", session_id).execute()

def _build_system_prompt(
    character: Dict[str, Any],
    scenario: Dict[str, Any],
    phase: str,
    user_profile: Dict[str, Any] | None = None,
    memories: list[str] | None = None,
) -> str:
    """
    phase에 따라 '개요/목표/첫 질문 강제' vs '가이드 진행' vs '리플렉션'을 엄격하게 구분.
    """
    persona = character.get("persona_prompt") or ""
    cname = character.get("name") or character.get("id") or "캐릭터"
    sname = scenario.get("name") or scenario.get("id") or "시나리오"
    outline = scenario.get("outline") or ""
    goal = scenario.get("goal") or ""
    story = scenario.get("story") or ""
    rules = scenario.get("scenario_prompt") or ""

    base = f"""
당신은 어린이를 돕는 대화형 학습 가이드 AI입니다.

[캐릭터]
- 이름: {cname}
- 페르소나: {persona}

[시나리오]
- 제목: {sname}
- 줄거리(참고용): {story}
- 개요(사용자에게 설명용): {outline}
- 학습 목표: {goal}

[공통 규칙]
- 한국어로 답합니다.
- 한 번에 질문은 1개만 합니다.
- 아이의 답을 존중하고, 단정/비난하지 않습니다.
- 과도하게 길게 말하지 않습니다.
- 사용자가 다른 주제로 이탈하면, 부드럽게 시나리오 목표로 다시 유도합니다.

    [시나리오 진행 규칙(추가)]
    {rules}
""".strip()

    if user_profile:
        lines = []
        for k in ["tone", "goal", "expertise", "age_band"]:
            v = user_profile.get(k)
            if v:
                lines.append(f"- {k}: {v}")
        if lines:
            base += "\n\n[사용자 프로필]\n" + "\n".join(lines)

    if memories:
        base += "\n\n[개인 메모리]\n" + "\n".join([f"- {m}" for m in memories])

    if phase == PHASE_INTRO:
        return base + """

[현재 단계: INTRO]
아래 출력 형식을 반드시 지키세요. (순서 고정)

출력 형식:
1) [개요] 3~5문장으로 쉽고 짧게 설명
2) [오늘의 목표] 1문장
3) [질문] 아이에게 던질 질문 1개(한 문장)

주의:
- 질문은 1개만.
- 아직 정답을 말하지 말고, 아이가 스스로 생각하도록 유도.
""".strip()

    if phase == PHASE_REFLECTION:
        return base + """

[현재 단계: REFLECTION]
아래 출력 형식을 반드시 지키세요.

출력 형식:
1) [오늘의 깨달음] 아이가 발견할 수 있는 가치 1~2개를 쉬운 말로 2~3줄
2) [내일 해볼 행동] 현실에서 할 수 있는 작은 행동 1개
3) [질문] 아이에게 "오늘 마음이 어땠는지" 묻는 질문 1개

주의:
- 설교하지 말고, 아이 말에서 출발해 정리.
- 질문은 1개만.
""".strip()

    if phase == PHASE_WRAP:
        return base + """

[현재 단계: WRAP]
짧게 마무리합니다.
- 오늘 대화 요약 2줄
- 칭찬 1줄
- "다음에 다른 이야기 해볼까?" 제안 1줄
""".strip()

    # default GUIDE
    return base + """

[현재 단계: GUIDE]
- 캐릭터 페르소나에 따라 질문/공감 방식으로 진행합니다.
- 아이의 답을 1문장으로 요약한 뒤, 다음 질문 1개만 던집니다.
- 목표(형제애/배려/나눔 등)를 스스로 발견하도록 유도합니다.
""".strip()

def _should_reflect(turn_count: int, user_text: str) -> bool:
    """
    MVP용: 간단한 기준으로 reflection 단계로 전환.
    - 왕복 턴 수가 일정 이상이거나
    - '정리', '결론', '오늘 배운', '깨달' 키워드 포함
    """
    if turn_count >= 6:
        return True
    kws = ["정리", "결론", "오늘 배운", "깨달", "요약"]
    return any(k in (user_text or "") for k in kws)
