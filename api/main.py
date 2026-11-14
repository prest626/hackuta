# Scaffold for GET /v1/health (LEAD-1). API-1 owns the rest of this app.

import importlib
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles

from api import db

# Other lanes add routes.py when their issue lands. Missing modules are skipped.
OPTIONAL_ROUTERS = (
    "api.routes",
    "ingest.routes",
    "vision.routes",
    "approvals.routes",
    "scheduler.routes",
)


def check_token(authorization: str | None, env_var: str) -> None:
    # shortcut: unset token leaves the local demo open, upgrade = always require it
    expected = os.environ.get(env_var, "")
    if not expected:
        return
    got = ""
    if authorization:
        parts = authorization.split(" ", 1)
        got = parts[1].strip() if len(parts) == 2 and parts[0].lower() == "bearer" else authorization.strip()
    if got != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def require_agent(authorization: Annotated[str | None, Header()] = None) -> None:
    check_token(authorization, "AGENT_API_TOKEN")


def require_dashboard(authorization: Annotated[str | None, Header()] = None) -> None:
    check_token(authorization, "DASHBOARD_TOKEN")


def include_optional(app: FastAPI, names: tuple[str, ...] = OPTIONAL_ROUTERS) -> list[str]:
    mounted = []
    for name in names:
        try:
            mod = importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        router = getattr(mod, "router", None)
        if router is None:
            continue
        app.include_router(router)
        mounted.append(name)
    return mounted


@asynccontextmanager
async def lifespan(_app: FastAPI):
    with db.conn():
        pass
    yield


app = FastAPI(title="Homeward", lifespan=lifespan)


@app.get("/v1/health")
def health():
    return {"ok": True}


include_optional(app)

_dash = Path("dashboard")
if (_dash / "index.html").is_file():
    # Mounted last so /v1/* routes win. Dashboard lane owns the files.
    app.mount("/", StaticFiles(directory=_dash, html=True), name="dashboard")
