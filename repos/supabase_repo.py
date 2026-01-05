from supabase import create_client, Client
from apps.gateway_api.settings import get_settings
from datetime import datetime, timezone
from typing import Optional


_supabase: Client | None = None

def _get_supabase() -> Client:
    global _supabase
    if _supabase is not None:
        return _supabase
    settings = get_settings()
    _supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _supabase

def supabase_client() -> Client:
    return _get_supabase()

def get_characters():
    return _get_supabase().table("characters").select("*").eq("is_active", True).execute().data

def get_scenarios():
    return _get_supabase().table("scenarios").select("*").eq("is_active", True).execute().data

def upsert_character(
    id: str,
    name: str,
    persona_prompt: str,
    description: str | None = None,
    image_url: str | None = None,
    is_active: bool = True,
):
    return _get_supabase().table("characters").upsert({
        "id": id,
        "name": name,
        "persona_prompt": persona_prompt,
        "description": description,
        "image_url": image_url,
        "is_active": is_active,
    }).execute().data

def delete_character_by_id(character_id: str):
    return _get_supabase().table("characters").delete().eq("id", character_id).execute().data

def delete_scenario_by_id(scenario_id: str):
    return _get_supabase().table("scenarios").delete().eq("id", scenario_id).execute().data

def upsert_scenario(
    id: str,
    name: str,
    story: str | None,
    goal: str | None,
    outline: str | None,
    scenario_prompt: str,
    first_message: str,
    is_active: bool = True,
):
    return _get_supabase().table("scenarios").upsert({
        "id": id,
        "name": name,
        "story": story,
        "goal": goal,
        "outline": outline,
        "scenario_prompt": scenario_prompt,
        "first_message": first_message,
        "is_active": is_active,
    }).execute().data

def create_session(user_id: str, character_id: str, scenario_id: str):
    payload = {
        "user_id": user_id,
        "character_id": character_id,
        "scenario_id": scenario_id,
        "status": "active",
    }
    res = _get_supabase().table("sessions").insert(payload).execute()
    return res.data[0] if res.data else None

def end_session(session_id: str):
    payload = {
        "status": "ended",
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
    res = _get_supabase().table("sessions").update(payload).eq("id", session_id).execute()
    return res.data[0] if res.data else None

def get_scenario_by_id(scenario_id: str):
    res = _get_supabase().table("scenarios").select("*").eq("id", scenario_id).limit(1).execute()
    return res.data[0] if res.data else None

def get_character_by_id(character_id: str):
    res = _get_supabase().table("characters").select("*").eq("id", character_id).limit(1).execute()
    return res.data[0] if res.data else None

def get_session_by_id(session_id: str):
    res = _get_supabase().table("sessions").select("*").eq("id", session_id).limit(1).execute()
    return res.data[0] if res.data else None

def get_user_by_id(user_id: str) -> Optional[dict]:
    res = (
        _get_supabase().table("users")
        .select("id,tone,goal,expertise,age_band,created_at,updated_at")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return res.data

def insert_message(session_id: str, user_id: str | None, role: str, content: str):
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "content": content,
    }
    res = _get_supabase().table("messages").insert(payload).execute()
    return res.data[0] if res.data else None

def upsert_user(user_id: str, tone=None, goal=None, expertise=None, age_band=None):
    payload = {"id": user_id, "tone": tone, "goal": goal, "expertise": expertise, "age_band": age_band}
    res = _get_supabase().table("users").upsert(payload).execute()
    return res.data[0] if res.data else None

def upsert_user_profile(
    user_id: str,
    tone: str | None,
    goal: str | None,
    expertise: str | None,
    age_band: str | None,
) -> dict:
    payload = {
        "id": user_id,
        "tone": tone,
        "goal": goal,
        "expertise": expertise,
        "age_band": age_band,
    }
    res = (
        _get_supabase().table("users")
        .upsert(payload, on_conflict="id")
        .execute()
    )
    if isinstance(res.data, list) and res.data:
        return res.data[0]
    return payload

def insert_memory_item(
    user_id: str,
    session_id: str | None,
    kind: str | None,
    text: str,
    source: str | None = None,
    pinecone_vector_id: str | None = None,
):
    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "kind": kind,
        "text": text,
        "source": source,
        "pinecone_vector_id": pinecone_vector_id,
    }
    res = _get_supabase().table("memory_items").insert(payload).execute()
    return res.data[0] if res.data else None

def list_messages(session_id: str, limit: int = 200):
    res = (
        _get_supabase().table("messages")
        .select("id,session_id,user_id,role,content,created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return res.data or []

def list_sessions(user_id: str, limit: int = 50):
    res = (
        _get_supabase().table("sessions")
        .select("id,user_id,character_id,scenario_id,created_at,ended_at,status")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []

def list_recent_memory_texts(user_id: str, limit: int = 50):
    res = (
        _get_supabase().table("memory_items")
        .select("text,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    return [r["text"] for r in rows if r.get("text")]

def list_memory_items(user_id: str, limit: int = 100):
    res = (
        _get_supabase().table("memory_items")
        .select("id,user_id,session_id,kind,text,source,pinecone_vector_id,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []

def get_memory_item_by_id(memory_id: str) -> Optional[dict]:
    res = (
        _get_supabase().table("memory_items")
        .select("id,user_id,pinecone_vector_id")
        .eq("id", memory_id)
        .maybe_single()
        .execute()
    )
    return res.data

def delete_memory_item_by_id(memory_id: str) -> None:
    _get_supabase().table("memory_items").delete().eq("id", memory_id).execute()
