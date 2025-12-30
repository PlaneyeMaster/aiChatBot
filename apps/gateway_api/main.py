from fastapi import FastAPI
from fastapi.responses import JSONResponse

from repos.supabase_repo import supabase_client
from apps.gateway_api.routes_catalog import router as catalog_router
from apps.gateway_api.routes_seed import router as seed_router

app = FastAPI(title="AI Human Gateway API")

app.include_router(catalog_router)
app.include_router(seed_router)

@app.get("/health")
def health():
    # Supabase ping(가벼운 쿼리로 확인)
    try:
        _ = supabase_client().table("characters").select("id").limit(1).execute()
        supabase_ok = True
    except Exception:
        supabase_ok = False

    return JSONResponse({"ok": True, "service": "gateway_api", "supabase": supabase_ok})
