import hashlib
import uuid
from typing import Dict, Any

from services.embeddings_service import embed_text
from repos.pinecone_repo import query_memory, upsert_memory
from repos.supabase_repo import supabase_client, insert_memory_item, list_recent_memory_texts
from services.memory_dedupe import is_text_duplicate

def _simple_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

async def retrieve_personal_memory(user_id: str, query: str | None = None, query_text: str | None = None, top_k: int = 5) -> list[str]:
    q = (query_text or query or "").strip()
    if not q:
        return []
    v = await embed_text(q)
    try:
        res = query_memory(user_id=user_id, vector=v, top_k=top_k)
    except Exception:
        return []
    matches = getattr(res, "matches", None) or res.get("matches", [])
    out: list[str] = []
    for m in matches:
        md = getattr(m, "metadata", None) or m.get("metadata", {})
        txt = (md.get("text") or "").strip()
        if txt:
            out.append(txt)
    return out

async def maybe_save_personal_memory(
    user_id: str,
    user_text: str,
    assistant_text: str,
    session_id: str | None = None,
) -> Dict[str, Any]:
    stats = {"saved": 0, "skipped_dup": 0, "skipped_low": 0}

    candidate = (assistant_text or "").strip()
    if len(candidate) < 40:
        stats["skipped_low"] += 1
        return {"saved": False, "stats": stats}

    recent_texts = list_recent_memory_texts(user_id=user_id, limit=50)
    if is_text_duplicate(candidate, recent_texts):
        stats["skipped_dup"] += 1
        return {"saved": False, "stats": stats}

    vec = await embed_text(candidate)
    pinecone_vector_id = str(uuid.uuid4())
    upsert_memory(
        user_id=user_id,
        items=[{
            "id": pinecone_vector_id,
            "values": vec,
            "metadata": {
                "text": candidate,
                "text_hash": _simple_hash(candidate),
                "session_id": session_id,
            },
        }],
    )

    ins = insert_memory_item(
        user_id=user_id,
        session_id=session_id,
        kind=None,
        text=candidate,
        source="chat",
        pinecone_vector_id=pinecone_vector_id,
    )

    memory_id = None
    if isinstance(ins, dict):
        memory_id = ins.get("id")

    stats["saved"] += 1
    return {
        "saved": True,
        "memory_id": memory_id,
        "pinecone_vector_id": pinecone_vector_id,
        "stats": stats,
    }
