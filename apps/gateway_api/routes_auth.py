from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from repos.supabase_repo import supabase_client
from services.auth_service import validate_credentials, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

class SignupRequest(BaseModel):
    id: str
    password: str

class LoginRequest(BaseModel):
    id: str
    password: str

@router.post("/signup")
async def signup(req: SignupRequest):
    user_id = (req.id or "").strip()
    password = (req.password or "").strip()

    try:
        validate_credentials(user_id, password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    sb = supabase_client()

    # 중복 체크
    existing = sb.table("users").select("id").eq("id", user_id).limit(1).execute()
    if getattr(existing, "data", None):
        raise HTTPException(status_code=409, detail="이미 존재하는 id입니다.")

    # 가입 저장 (id를 그대로 user_id로 사용)
    pw_hash = hash_password(password)
    ins = sb.table("users").insert({
        "id": user_id,
        "password_hash": pw_hash,
        # 선택: 초기 프로필 기본값
        # "tone": None, "goal": None, "expertise": None, "age_band": None
    }).execute()

    data = getattr(ins, "data", None) or []
    if not data:
        raise HTTPException(status_code=500, detail="회원가입 저장 실패")

    return {"ok": True, "user": {"id": user_id}}

@router.post("/login")
async def login(req: LoginRequest):
    user_id = (req.id or "").strip()
    password = (req.password or "").strip()

    try:
        validate_credentials(user_id, password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    sb = supabase_client()
    res = sb.table("users").select("id,password_hash").eq("id", user_id).maybe_single().execute()
    user = getattr(res, "data", None) or None
    if not user:
        raise HTTPException(status_code=401, detail="id 또는 비밀번호가 올바르지 않습니다.")

    pw_hash = user.get("password_hash") or ""
    if not pw_hash or not verify_password(password, pw_hash):
        raise HTTPException(status_code=401, detail="id 또는 비밀번호가 올바르지 않습니다.")

    # MVP: 세션 토큰 대신 "로그인 성공"만 반환 (프론트에서 user_id를 저장)
    # 운영형이면 JWT 발급으로 바꾸는 것을 권장
    return {"ok": True, "user": {"id": user_id}}