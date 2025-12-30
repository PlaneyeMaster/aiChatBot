import os
from pydantic import BaseModel

class Settings(BaseModel):
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    ENV: str = "prod"

def get_settings() -> Settings:
    missing = []
    for k in ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]:
        if not os.getenv(k):
            missing.append(k)
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

    return Settings(
        SUPABASE_URL=os.environ["SUPABASE_URL"],
        SUPABASE_SERVICE_ROLE_KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        ENV=os.getenv("ENV", "prod"),
    )
