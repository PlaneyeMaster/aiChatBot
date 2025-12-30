from supabase import create_client, Client
from apps.gateway_api.settings import get_settings
from datetime import datetime, timezone


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