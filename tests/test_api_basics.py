"""API-1: health, schema, log_event, optional routers."""

import os
import sys
import types

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    from api.main import app

    with TestClient(app) as c:
        yield c


def test_health_creates_tables_and_log_event(client):
    res = client.get("/v1/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}

    from api import db

    with db.conn() as c:
        tables = {row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "patients",
        "med_schedules",
        "vitals",
        "scheduled_calls",
        "call_results",
        "flags",
        "approvals",
        "message_log",
        "events",
    } <= tables

    row_id = db.log_event("demo.seed", "demo", {"n": 1})
    assert row_id >= 1
    with db.conn() as c:
        row = c.execute("SELECT name, actor, payload FROM events WHERE id = ?", (row_id,)).fetchone()
    assert row["name"] == "demo.seed"
    assert row["actor"] == "demo"
    assert '"n": 1' in row["payload"]


def test_missing_optional_routers_do_not_crash():
    from api.main import include_optional

    fresh = FastAPI()
    # approvals.routes exists once APPR-2 lands; this still checks a missing router.
    assert include_optional(fresh, names=("vision.routes", "no.such.routes")) == []


def test_mounts_router_when_the_module_exists():
    from fastapi import APIRouter

    from api.main import include_optional

    mod = types.ModuleType("ingest.routes")
    mod.router = APIRouter()

    @mod.router.get("/v1/ingest-probe")
    def probe():
        return {"ok": True}

    sys.modules["ingest.routes"] = mod
    try:
        fresh = FastAPI()
        assert include_optional(fresh, names=("ingest.routes",)) == ["ingest.routes"]
        res = TestClient(fresh).get("/v1/ingest-probe")
        assert res.status_code == 200
        assert res.json() == {"ok": True}
    finally:
        sys.modules.pop("ingest.routes", None)


def test_token_helper(monkeypatch):
    from api.main import require_agent, require_dashboard

    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    require_agent(None)

    monkeypatch.setenv("AGENT_API_TOKEN", "agent-secret")
    require_agent("Bearer agent-secret")
    with pytest.raises(HTTPException) as ei:
        require_agent("Bearer wrong")
    assert ei.value.status_code == 401

    monkeypatch.setenv("DASHBOARD_TOKEN", "dash-secret")
    require_dashboard("Bearer dash-secret")
    with pytest.raises(HTTPException) as ei:
        require_dashboard(None)
    assert ei.value.status_code == 401
