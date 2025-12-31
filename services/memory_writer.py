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
너는 개인화 메모리를 추출하는 도우미다.
아래 대화에서 '장기적으로 유용한 사용자 정보'만 후보로 뽑아라.

저장 기준:
- 선호/비선호, 목표, 제약(시간/예산/기한), 반복 프로젝트 맥락, 사용 습관/루틴
- 일회성 잡담/짧은 감탄은 제외
- 민감정보(건강/정치/종교/성생활/범죄/정체성 추정)는 제외

출력은 반드시 JSON 객체.
형식: { "items": [ ... ] }
각 항목은:
{
  "kind": "preference|goal|constraint|profile|project_context",
  "text": "한 문장",
  "importance": 1~5,
  "ttl_days": 7|30|180|365
}

규칙:
- text는 20~120자 사이를 권장(너무 짧거나 길면 제외 대상)
- importance가 4~5인 것만 저장 후보로 간주
"""

async def extract_memory_candidates(user_text: str, assistant_text: str) -> list[dict]:
    c = openai_client()
    resp = await c.chat.completions.create(
        model=model_name(),
        messages=[
            {"role": "system", "content": MEMORY_EXTRACT_SYSTEM.strip()},
            {"role": "user", "content": f"[USER]\n{user_text}\n\n[ASSISTANT]\n{assistant_text}"},
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
                "importance": it.get("importance"),
                "ttl_days": it.get("ttl_days"),
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
    cands = await extract_memory_candidates(user_text, assistant_text)
    if not cands:
        return {"saved": 0, "skipped_duplicate": 0}

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
        insert_memory_item(user_id=user_id, session_id=session_id, kind=kind, text=txt, source="chat")
        recent_texts.append(txt)  # 이번 턴 내 중복 방지
        saved += 1

        if saved >= MAX_SAVE_PER_TURN:
            break

    if saved > 0:
        upsert_memory(user_id=user_id, items=vectors)

    return {"saved": saved, "skipped_duplicate": skipped_dup}
