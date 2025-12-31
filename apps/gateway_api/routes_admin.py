from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from repos.supabase_repo import (
    list_memory_items,
    get_memory_item_by_id,
    delete_memory_item_by_id,
)
from repos.pinecone_repo import delete_memory_vectors

router = APIRouter(prefix="/admin", tags=["admin"])

class UpsertUserBody(BaseModel):
    id: str
    tone: str | None = None
    goal: str | None = None
    expertise: str | None = None
    age_band: str | None = None

# === Memory ===

@router.get("/memory")
def admin_list_memory(user_id: str = Query(...), limit: int = Query(100, ge=1, le=1000)):
    items = list_memory_items(user_id=user_id, limit=limit)
    return {"ok": True, "items": items}

@router.delete("/memory/{memory_id}")
def admin_delete_memory(memory_id: str):
    row = get_memory_item_by_id(memory_id)
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")

    user_id = row["user_id"]
    pinecone_vector_id = row.get("pinecone_vector_id")

    # 1) Pinecone 삭제(정석)
    if pinecone_vector_id:
        delete_memory_vectors(user_id=user_id, vector_ids=[pinecone_vector_id])

    # 2) Supabase 삭제
    delete_memory_item_by_id(memory_id)

    return {"ok": True, "deleted": {"memory_id": memory_id, "pinecone_vector_id": pinecone_vector_id}}
