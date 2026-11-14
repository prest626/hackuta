# Scaffold for GET /v1/health (LEAD-1). API-1 owns the rest of this app.

import asyncio
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
    "ingest.routes",
    "vision.routes",
    "approvals.routes",
    "scheduler.routes",
)


def presented_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


def check_token(authorization: str | None, env_var: str) -> None:
    # shortcut: unset token leaves the local demo open, upgrade = always require it
    expected = os.environ.get(env_var, "")
    if not expected:
        return
    if presented_token(authorization) != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def require_agent(authorization: Annotated[str | None, Header()] = None) -> None:
    check_token(authorization, "AGENT_API_TOKEN")


def require_dashboard(authorization: Annotated[str | None, Header()] = None) -> None:
    check_token(authorization, "DASHBOARD_TOKEN")


def require_reader(authorization: Annotated[str | None, Header()] = None) -> None:
    """Agent or dashboard token. Open when neither secret is set."""
    needed = [v for v in ("AGENT_API_TOKEN", "DASHBOARD_TOKEN") if os.environ.get(v, "")]
    if not needed:
        return
    got = presented_token(authorization)
    if any(got == os.environ[v] for v in needed):
        return
    raise HTTPException(status_code=401, detail="unauthorized")


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


async def _scheduler_loop() -> None:
    from scheduler.core import tick

    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception as exc:
            try:
                db.log_event("mac.error", "scheduler", {"error": str(exc)})
            except Exception:
                pass
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    with db.conn():
        pass
    # pytest sets PYTEST_CURRENT_TEST; the loop would dial during tests.
    task = None
    if not os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("SCHEDULER", "1") != "0":
        task = asyncio.create_task(_scheduler_loop())
    try:
        yield
    finally:
        if task:
            task.cancel()


app = FastAPI(title="Homeward", lifespan=lifespan)


@app.get("/v1/health")
def health():
    return {"ok": True}


include_optional(app)
import api.routes  # noqa: E402  — routes mounts itself after this app exists

_dash = Path("dashboard")
if (_dash / "index.html").is_file():
    # Mounted last so /v1/* routes win. Dashboard lane owns the files.
    app.mount("/", StaticFiles(directory=_dash, html=True), name="dashboard")
