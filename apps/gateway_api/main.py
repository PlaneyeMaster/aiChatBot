import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from repos.supabase_repo import supabase_client
from apps.gateway_api.routes_catalog import router as catalog_router
from apps.gateway_api.routes_seed import router as seed_router
from apps.gateway_api.routes_session import router as session_router
from apps.gateway_api.routes_chat import router as chat_router
from apps.gateway_api.routes_messages import router as messages_router
from apps.gateway_api.routes_admin import router as admin_router
from apps.gateway_api.routes_auth import router as auth_router
# ...

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI Human Gateway API")

app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aichatbot-web.onrender.com",
        "https://aichatbot-admin.onrender.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\\.onrender\\.com",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog_router)
app.include_router(seed_router)
app.include_router(session_router)
app.include_router(chat_router)
app.include_router(messages_router)
app.include_router(admin_router)

@app.get("/health")
def health():
    # Supabase ping(가벼운 쿼리로 확인)
    try:
        _ = supabase_client().table("characters").select("id").limit(1).execute()
        supabase_ok = True
    except Exception:
        supabase_ok = False

    return JSONResponse({"ok": True, "service": "gateway_api", "supabase": supabase_ok})
