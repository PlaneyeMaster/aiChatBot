from services.embeddings_service import embed_text
from repos.pinecone_repo import query_memory

async def retrieve_personal_memory(user_id: str, query: str, top_k: int = 5) -> list[str]:
    v = await embed_text(query)
    try:
        res = query_memory(user_id=user_id, vector=v, top_k=top_k)
    except Exception:
        return []
    matches = getattr(res, "matches", None) or res.get("matches", [])
    out = []
    for m in matches:
        md = getattr(m, "metadata", None) or m.get("metadata", {})
        txt = md.get("text")
        if txt:
            out.append(txt)
    return out
