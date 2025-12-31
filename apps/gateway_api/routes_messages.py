from fastapi import APIRouter, HTTPException, Query
from repos.supabase_repo import get_session_by_id, list_messages

router = APIRouter(prefix="/session", tags=["session"])

@router.get("/{session_id}/messages")
def get_session_messages(session_id: str, limit: int = Query(200, ge=1, le=1000)):
    sess = get_session_by_id(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    items = list_messages(session_id=session_id, limit=limit)
    return {"ok": True, "items": items}
