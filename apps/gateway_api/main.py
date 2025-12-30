from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="AI Human Gateway API")

@app.get("/health")
def health():
    return JSONResponse({"ok": True, "service": "gateway_api"})
