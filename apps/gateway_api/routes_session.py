from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from repos.supabase_repo import (
    create_session,
    end_session,
    get_character_by_id,
    get_scenario_by_id,
)

router = APIRouter(prefix="/session", tags=["session"])

class SessionCreateRequest(BaseModel):
    user_id: str
    character_id: str
    scenario_id: str

@router.post("/create")
def session_create(req: SessionCreateRequest):
    character = get_character_by_id(req.character_id)
    if not character:
        raise HTTPException(status_code=400, detail="Invalid character_id")

    scenario = get_scenario_by_id(req.scenario_id)
    if not scenario:
        raise HTTPException(status_code=400, detail="Invalid scenario_id")

    sess = create_session(req.user_id, req.character_id, req.scenario_id)
    if not sess:
        raise HTTPException(status_code=500, detail="Failed to create session")

    return {
        "ok": True,
        "session": sess,
        "character": {
            "id": character["id"],
            "name": character.get("name"),
        },
        "scenario": {
            "id": scenario["id"],
            "name": scenario.get("name"),
            "first_message": scenario.get("first_message"),
            "story": scenario.get("story"),
        },
    }

class SessionEndRequest(BaseModel):
    session_id: str

@router.post("/end")
def session_end(req: SessionEndRequest):
    sess = end_session(req.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True, "session": sess}
