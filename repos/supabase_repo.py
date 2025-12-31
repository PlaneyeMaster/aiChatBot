from supabase import create_client, Client
from apps.gateway_api.settings import get_settings
from datetime import datetime, timezone
from typing import Optional


_settings = get_settings()
_supabase: Client = create_client(_settings.SUPABASE_URL, _settings.SUPABASE_SERVICE_ROLE_KEY)

def supabase_client() -> Client:
    return _supabase

def get_characters():
    return _supabase.table("characters").select("*").eq("is_active", True).execute().data

def get_scenarios():
    return _supabase.table("scenarios").select("*").eq("is_active", True).execute().data

def upsert_character(id: str, name: str, persona_prompt: str, is_active: bool = True):
    return _supabase.table("characters").upsert({
        "id": id,
        "name": name,
        "persona_prompt": persona_prompt,
        "is_active": is_active,
    }).execute().data

def upsert_scenario(id: str, name: str, scenario_prompt: str, first_message: str, is_active: bool = True):
    return _supabase.table("scenarios").upsert({
        "id": id,
        "name": name,
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
    res = _supabase.table("sessions").insert(payload).execute()
    return res.data[0] if res.data else None

def end_session(session_id: str):
    payload = {
        "status": "ended",
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
    res = _supabase.table("sessions").update(payload).eq("id", session_id).execute()
    return res.data[0] if res.data else None

def get_scenario_by_id(scenario_id: str):
    res = _supabase.table("scenarios").select("*").eq("id", scenario_id).limit(1).execute()
    return res.data[0] if res.data else None

def get_character_by_id(character_id: str):
    res = _supabase.table("characters").select("*").eq("id", character_id).limit(1).execute()
    return res.data[0] if res.data else None

def get_session_by_id(session_id: str):
    res = _supabase.table("sessions").select("*").eq("id", session_id).limit(1).execute()
    return res.data[0] if res.data else None

def get_user_by_id(user_id: str):
    res = _supabase.table("users").select("*").eq("id", user_id).limit(1).execute()
    return res.data[0] if res.data else None

def insert_message(session_id: str, user_id: str | None, role: str, content: str):
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "content": content,
    }
    res = _supabase.table("messages").insert(payload).execute()
    return res.data[0] if res.data else None

def upsert_user(user_id: str, tone=None, goal=None, expertise=None, age_band=None):
    payload = {"id": user_id, "tone": tone, "goal": goal, "expertise": expertise, "age_band": age_band}
    res = _supabase.table("users").upsert(payload).execute()
    return res.data[0] if res.data else None

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
    res = _supabase.table("memory_items").insert(payload).execute()
    return res.data[0] if res.data else None

def list_messages(session_id: str, limit: int = 200):
    res = (
        _supabase.table("messages")
        .select("id,session_id,user_id,role,content,created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return res.data or []

def list_recent_memory_texts(user_id: str, limit: int = 50):
    res = (
        _supabase.table("memory_items")
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
        _supabase.table("memory_items")
        .select("id,user_id,session_id,kind,text,source,pinecone_vector_id,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []

def get_memory_item_by_id(memory_id: str) -> Optional[dict]:
    res = (
        _supabase.table("memory_items")
        .select("id,user_id,pinecone_vector_id")
        .eq("id", memory_id)
        .maybe_single()
        .execute()
    )
    return res.data

def delete_memory_item_by_id(memory_id: str) -> bool:
    _ = (
        _supabase.table("memory_items")
        .delete()
        .eq("id", memory_id)
        .execute()
    )
    # supabase python client는 삭제된 row 반환/영향행이 케이스마다 다름 → 성공 여부는 예외 미발생 기준으로 단순 True 처리
    return True
