"""API-3: 60s heart-rate median, stale flag, resting-HR z."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    from api.main import app

    with TestClient(app) as c:
        yield c


def _seed(baseline=True):
    from api import db

    patient = json.loads((EXAMPLES / "patient.json").read_text())
    if not baseline:
        patient["baseline"] = {"rhr_bpm_mean": None, "rhr_bpm_sd": None, "source": "mock"}
    with db.conn() as c:
        c.execute(
            "INSERT INTO patients (id, doc, is_mock) VALUES (?, ?, 1)",
            (patient["id"], json.dumps(patient)),
        )
    return patient


def _vital(metric, value, when, source="mock_replay"):
    from api import db

    with db.conn() as c:
        c.execute(
            "INSERT INTO vitals (t, patient_id, metric, value, source, quality) VALUES (?, ?, ?, ?, ?, NULL)",
            (_iso(when), "pat_rosa01", metric, value, source),
        )


def test_median_stale_flip_and_hand_calculated_z(client):
    from contracts.models import LiveVitals

    _seed()
    now = datetime.now(timezone.utc)
    for bpm in (70, 80, 90):
        _vital("hr", bpm, now - timedelta(seconds=10))
    _vital("hr", 140, now - timedelta(seconds=90))
    _vital("rhr", 73, now - timedelta(days=1))
    _vital("rhr", 73, now - timedelta(days=2))
    local_now = datetime.now(ZoneInfo("America/Chicago"))
    _vital("steps", 100, local_now - timedelta(days=1))
    _vital("steps", 412, local_now - timedelta(minutes=1))
    _vital("hrv_sdnn", 28, now - timedelta(hours=8))
    _vital("rr_sleep", 17.5, now - timedelta(hours=8))

    res = client.get("/v1/patients/pat_rosa01/vitals/live")
    assert res.status_code == 200
    body = res.json()
    assert LiveVitals.model_validate(body)
    assert body["hr_median_60s"] == 80
    assert body["hr_n_60s"] == 3
    assert body["stale"] is False
    assert body["hr_last_t"] is not None
    # (73 - 66) / 3.5 = 2, from patient.baseline, not from the sample mean.
    assert body["rhr_7d_bpm"] == 73
    assert body["rhr_baseline_bpm"] == 66
    assert body["rhr_z"] == 2
    assert body["steps_today"] == 412
    assert body["hrv_sdnn_ms_last_night"] == 28
    assert body["rr_sleep_last_night"] == 17.5

    ctx = client.get("/v1/patients/pat_rosa01/context").json()
    assert ctx["live_vitals"]["hr_median_60s"] == 80
    assert ctx["live_vitals"]["stale"] is False


def test_stale_when_newest_hr_is_older_than_30s(client):
    _seed()
    now = datetime.now(timezone.utc)
    _vital("hr", 77, now - timedelta(seconds=45))
    body = client.get("/v1/patients/pat_rosa01/vitals/live").json()
    assert body["stale"] is True
    assert body["hr_n_60s"] == 1
    assert body["hr_median_60s"] == 77

    _vital("hr", 77, now - timedelta(seconds=120))
    # The 45s sample is still inside 60s, so this stays one sample. A lone 2-minute sample:
    from api import db

    with db.conn() as c:
        c.execute("DELETE FROM vitals")
    _vital("hr", 77, datetime.now(timezone.utc) - timedelta(seconds=120))
    body = client.get("/v1/patients/pat_rosa01/vitals/live").json()
    assert body["stale"] is True
    assert body["hr_n_60s"] == 0
    assert body["hr_median_60s"] is None


def test_z_from_60_day_rows_when_baseline_is_empty(client):
    _seed(baseline=False)
    now = datetime.now(timezone.utc)
    _vital("rhr", 80, now - timedelta(days=1))
    _vital("rhr", 80, now - timedelta(days=2))
    _vital("rhr", 60, now - timedelta(days=30))
    _vital("rhr", 60, now - timedelta(days=31))
    body = client.get("/v1/patients/pat_rosa01/vitals/live").json()
    # 7-day mean 80. 60-day values 80, 80, 60, 60 → mean 70, population sd 10.
    # z = (80 - 70) / 10 = 1.
    assert body["rhr_7d_bpm"] == 80
    assert body["rhr_baseline_bpm"] == 70
    assert body["rhr_z"] == 1


def test_history_filters_metric_and_since(client):
    from contracts.models import VitalSample

    _seed()
    now = datetime.now(timezone.utc)
    _vital("rhr", 73, now - timedelta(days=1))
    _vital("rhr", 60, now - timedelta(days=30))
    _vital("hr", 80, now - timedelta(seconds=5), source="watch_workout")
    since = _iso(now - timedelta(days=3))
    res = client.get("/v1/patients/pat_rosa01/vitals", params={"metric": "rhr", "since": since})
    assert res.status_code == 200
    rows = res.json()
    assert [row["value"] for row in rows] == [73]
    assert VitalSample.model_validate(rows[0])
    assert client.get("/v1/patients/pat_missing1/vitals/live").status_code == 404
