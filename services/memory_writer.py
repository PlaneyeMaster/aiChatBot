import json
import uuid
from services.openai_service import client as openai_client, model_name
from services.embeddings_service import embed_text
from repos.pinecone_repo import upsert_memory
from repos.supabase_repo import insert_memory_item

MEMORY_EXTRACT_SYSTEM = """
너는 개인화 메모리를 추출하는 도우미다.
아래 대화에서 "사용자에 대한 장기적으로 유용한 정보"만 추출하라.
- 선호/싫어함, 목표, 제약(시간/예산), 반복되는 프로젝트 맥락, 중요한 사실
- 일회성 잡담, 민감정보(건강/정치성향/종교 등)로 보일 수 있는 내용은 저장하지 마라.
출력은 JSON 배열로만 한다.
각 항목은 { "kind": "...", "text": "..." } 형식.
text는 한 문장으로 짧고 명확하게.
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
    )
    raw = resp.choices[0].message.content or "[]"
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            # 최소 필드 정리
            cleaned = []
            for it in data:
                if not isinstance(it, dict):
                    continue
                txt = (it.get("text") or "").strip()
                if not txt:
                    continue
                cleaned.append({"kind": (it.get("kind") or "").strip(), "text": txt})
            return cleaned
        return []
    except Exception:
        return []

async def write_personal_memory(user_id: str, session_id: str, user_text: str, assistant_text: str):
    cands = await extract_memory_candidates(user_text, assistant_text)
    if not cands:
        return {"saved": 0}

    vectors = []
    saved = 0
    for it in cands[:5]:  # MVP 상한
        txt = it["text"]
        kind = it.get("kind") or None
        emb = await embed_text(txt)
        vid = str(uuid.uuid4())

        # Pinecone upsert
        vectors.append({
            "id": vid,
            "values": emb,
            "metadata": {"text": txt, "kind": kind, "session_id": session_id},
        })

        # Supabase audit log
        insert_memory_item(user_id=user_id, session_id=session_id, kind=kind, text=txt, source="chat")

        saved += 1

    upsert_memory(user_id=user_id, items=vectors)
    return {"saved": saved}
