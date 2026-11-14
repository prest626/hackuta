# Scaffold for GET /v1/health (LEAD-1). API-1 owns the rest of this app.

from fastapi import FastAPI

app = FastAPI()


@app.get("/v1/health")
def health():
    return {"ok": True}
