import re
from passlib.context import CryptContext

ID_RE = re.compile(r"^[A-Za-z]+$")
PW_RE = re.compile(r"^[0-9]+$")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def validate_credentials(user_id: str, password: str) -> None:
    if not user_id or not ID_RE.match(user_id):
        raise ValueError("id는 영문(A-Z, a-z)만 입력 가능합니다.")
    if not password or not PW_RE.match(password):
        raise ValueError("비밀번호는 숫자(0-9)만 입력 가능합니다.")
    if len(password) < 4:
        raise ValueError("비밀번호는 최소 4자리 이상을 권장합니다.")  # MVP 정책 (원하면 제거)

def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_ctx.verify(password, password_hash)