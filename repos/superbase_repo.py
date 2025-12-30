from supabase import create_client, Client
from apps.gateway_api.settings import get_settings

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
