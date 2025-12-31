import json
import os
import uuid
from services.openai_service import client as openai_client, model_name
from services.embeddings_service import embed_text
from repos.pinecone_repo import upsert_memory
from repos.supabase_repo import insert_memory_item
from repos.supabase_repo import list_recent_memory_texts
from repos.pinecone_repo import query_memory
from services.memory_dedupe import is_text_duplicate, is_vector_duplicate

MEMORY_EXTRACT_SYSTEM = """
당신은 7세 아이의 대화를 분석하는 아동 심리 전문가입니다.
대화 내용 중 아이의 '칭찬할 점', '기억해야 할 친구/가족', '좋아하는 것', '오늘의 기분'을 추출하세요.

[규칙]
1. 민감한 개인정보(집 주소, 실명 등)는 절대 추출하지 마세요.
2. 중요도(importance)는 1~5로 정하며, 아이의 감정이나 성취는 4점 이상으로 책정하세요.
3. 반드시 아래 JSON 형식을 지키세요.

{
  "items": [
    { "text": "아이의 기억 내용", "kind": "fact/preference/emotion", "importance": 5, "ttl_days": 30 }
  ]
}
"""

async def extract_memory_candidates(history_text: str) -> list[dict]:
    c = openai_client()
    resp = await c.chat.completions.create(
        model=model_name(),
        messages=[
            {"role": "system", "content": MEMORY_EXTRACT_SYSTEM.strip()},
            {"role": "user", "content": history_text},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    if os.getenv("MEMORY_DEBUG") == "1":
        print(f"memory_extract_raw={raw}", flush=True)
    try:
        data = json.loads(raw)
        items = []
        if isinstance(data, dict):
            items = data.get("items", []) or []
        elif isinstance(data, list):
            items = data
        if not isinstance(items, list):
            return []

        # 최소 필드 정리
        cleaned = []
        for it in items:
            if not isinstance(it, dict):
                continue
            txt = (it.get("text") or "").strip()
            if not txt:
                continue
            cleaned.append({
                "kind": (it.get("kind") or "").strip(),
                "text": txt,
                "importance": it.get("importance", 3),
                "ttl_days": it.get("ttl_days", 30),
            })
        if os.getenv("MEMORY_DEBUG") == "1":
            print(f"memory_extract_cleaned={cleaned}", flush=True)
        return cleaned
    except Exception:
        if os.getenv("MEMORY_DEBUG") == "1":
            print("memory_extract_parse_error", flush=True)
        return []
    
MIN_LEN = 12
MAX_LEN = 160
MIN_IMPORTANCE = 4
MAX_SAVE_PER_TURN = 5

async def write_personal_memory(user_id: str, session_id: str, user_text: str, assistant_text: str):
    history_text = f"[USER]\n{user_text}\n\n[ASSISTANT]\n{assistant_text}"
    cands = await extract_memory_candidates(history_text)
    if not cands:
        if os.getenv("MEMORY_DEBUG") == "1":
            print(f"memory_write_context user_id={user_id} session_id={session_id} cands=0", flush=True)
        return {"saved": 0, "skipped_duplicate": 0}
    if os.getenv("MEMORY_DEBUG") == "1":
        print(f"memory_write_context user_id={user_id} session_id={session_id} cands={len(cands)}", flush=True)

    recent_texts = list_recent_memory_texts(user_id=user_id, limit=50)

    vectors = []
    saved = 0
    skipped_dup = 0

    for it in cands:
        txt = (it.get("text") or "").strip()
        kind = (it.get("kind") or "").strip() or None
        importance = int(it.get("importance") or 0)

        # 1) 기준 필터
        if importance < MIN_IMPORTANCE:
            continue
        if not (MIN_LEN <= len(txt) <= MAX_LEN):
            continue

        # 2) 텍스트 중복
        if is_text_duplicate(txt, recent_texts):
            skipped_dup += 1
            continue

        # 3) 임베딩 생성
        emb = await embed_text(txt)

        # 4) 벡터 유사도 중복 (top1 score로 판단)
        res = query_memory(user_id=user_id, vector=emb, top_k=1)
        if is_vector_duplicate(res, score_threshold=0.90):
            skipped_dup += 1
            continue

        # 5) 저장
        vid = str(uuid.uuid4())
        vectors.append({
            "id": vid,
            "values": emb,
            "metadata": {"text": txt, "kind": kind, "session_id": session_id, "importance": importance},
        })
        insert_memory_item(
            user_id=user_id,
            session_id=session_id,
            kind=kind,
            text=txt,
            source="chat",
            pinecone_vector_id=vid,
        )
        recent_texts.append(txt)  # 이번 턴 내 중복 방지
        saved += 1

        if saved >= MAX_SAVE_PER_TURN:
            break

    if saved > 0:
        upsert_memory(user_id=user_id, items=vectors)

    return {"saved": saved, "skipped_duplicate": skipped_dup}
