from fastapi import APIRouter
from repos.supabase_repo import get_characters, get_scenarios

router = APIRouter(prefix="/catalog", tags=["catalog"])

@router.get("/characters")
def list_characters():
    return {"items": get_characters()}

@router.get("/scenarios")
def list_scenarios():
    return {"items": get_scenarios()}
