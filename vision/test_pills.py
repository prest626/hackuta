"""VISION-1: expected_empty, the decision table, and POST /v1/vision/pillcheck."""

import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"
CHICAGO = ZoneInfo("America/Chicago")
SUNDAY = datetime(2026, 11, 15, 13, 30, tzinfo=CHICAGO)
AFTERNOON = [
    "MON-AM", "MON-PM", "TUE-AM", "TUE-PM", "WED-AM", "WED-PM",
    "THU-AM", "THU-PM", "FRI-AM", "FRI-PM", "SAT-AM", "SAT-PM", "SUN-AM",
]


def schedule():
    return json.loads((EXAMPLES / "med_schedule.json").read_text())


def _jpeg(path: Path, checker: bool) -> None:
    img = Image.new("L", (32, 32), 40)
    if checker:
        px = img.load()
        for y in range(32):
            for x in range(32):
                px[x, y] = 255 if (x + y) % 2 == 0 else 0
    img.convert("RGB").save(path, format="JPEG", quality=95)


def test_expected_empty_monday_morning():
    from vision.pills import expected_empty

    med = schedule()
    early = datetime(2026, 11, 9, 7, 59, tzinfo=CHICAGO)
    assert expected_empty(med, early) == []
    assert expected_empty(med, early.replace(hour=8, minute=0)) == ["MON-AM"]


def test_expected_empty_sunday_afternoon_and_evening():
    from vision.pills import expected_empty

    med = schedule()
    assert expected_empty(med, SUNDAY) == AFTERNOON
    evening = SUNDAY.replace(hour=20, minute=0)
    got = expected_empty(med, evening)
    assert got[-1] == "SUN-PM"
    assert len(got) == 14


def test_expected_empty_tz_edge():
    from vision.pills import expected_empty

    med = schedule()
    chicago = datetime(2026, 11, 15, 23, 30, tzinfo=CHICAGO)
    utc = chicago.astimezone(timezone.utc)
    assert utc.date() == datetime(2026, 11, 16, tzinfo=timezone.utc).date()
    local = expected_empty(med, chicago)
    assert local[0] == "MON-AM" and local[-1] == "SUN-PM" and len(local) == 14
    assert expected_empty(med, utc) == []


def _read(**over):
    data = {
        "pillbox_visible": True,
        "compartments": [
            {"label": "sat-pm", "has_pills": True},
            {"label": "SUN-AM", "has_pills": False},
            {"label": "SUN-PM", "has_pills": True},
            {"label": "not-a-day", "has_pills": True},
        ],
        "confidence": 0.86,
        "reason": "Saturday evening still has pills.",
        "model": "fixture",
    }
    data.update(over)
    return data


def test_decision_table():
    from vision.pills import decision

    missed = decision(_read(), AFTERNOON)
    assert missed.state == "missed_possible"
    assert missed.mismatches == ["SAT-PM"]
    assert missed.image_quality == "good"
    assert [row.compartment for row in missed.observed] == ["SAT-PM", "SUN-AM", "SUN-PM"]

    clear = _read(compartments=[{"label": "SAT-PM", "has_pills": False}, {"label": "SUN-AM", "has_pills": False}])
    assert decision(clear, AFTERNOON).state == "ok"

    low = decision(_read(confidence=0.69), AFTERNOON)
    assert low.state == "unknown" and low.mismatches is None

    hidden = decision(_read(pillbox_visible=False, confidence=0.99), AFTERNOON)
    assert hidden.state == "unknown" and hidden.image_quality == "partial"


def test_fake_read_skips_the_provider(monkeypatch):
    from vision import pills

    monkeypatch.setattr(pills, "_openai", lambda jpeg, layout: (_ for _ in ()).throw(AssertionError("network")))
    read = pills.read_organizer(b"jpeg", "7x2")
    assert read["model"] == "fixture"
    assert read["pillbox_visible"] is True
    assert pills.check_pillbox(b"jpeg", schedule(), SUNDAY).state == "missed_possible"


def test_provider_switch_and_shrink(monkeypatch):
    from vision import pills

    monkeypatch.delenv("VISION_FAKE", raising=False)
    seen = {}

    def grab(jpeg, layout):
        seen["jpeg"] = jpeg
        seen["layout"] = layout
        return {"pillbox_visible": True, "compartments": [], "confidence": 0.9, "reason": "clear"}

    monkeypatch.setattr(pills, "_openai", grab)
    monkeypatch.setattr(pills, "_gemini", grab)
    big = Image.new("RGB", (2000, 10), (10, 20, 30))
    buf = io.BytesIO()
    big.save(buf, format="JPEG")
    read = pills.read_organizer(buf.getvalue(), "7x2")
    assert read["model"] == pills.OPENAI_MODEL
    assert seen["layout"] == "7x2"
    opened = Image.open(io.BytesIO(seen["jpeg"]))
    assert max(opened.size) <= 1024

    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    read = pills.read_organizer(buf.getvalue(), "7x4")
    assert read["model"] == pills.GEMINI_MODEL
    assert seen["layout"] == "7x4"


def test_read_failure_is_unknown(monkeypatch):
    from vision import pills

    monkeypatch.delenv("VISION_FAKE", raising=False)
    monkeypatch.setattr(pills, "_openai", lambda jpeg, layout: (_ for _ in ()).throw(RuntimeError("no key")))
    img = Image.new("RGB", (8, 8), (1, 2, 3))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    pill = pills.check_pillbox(buf.getvalue(), schedule(), SUNDAY)
    assert pill.state == "unknown" and pill.image_quality == "partial"
    assert pill.expected_empty == AFTERNOON


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.setenv("PROOF_DIR", str(tmp_path / "proof"))
    monkeypatch.setenv("VISION_FAKE", "fixtures")
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    from api.main import app

    monkeypatch.setattr("vision.routes.local_now", lambda tz: SUNDAY)

    with TestClient(app) as c:
        yield c


def _seed(patient_over=None):
    from api import db

    patient = json.loads((EXAMPLES / "patient.json").read_text())
    if patient_over:
        patient.update(patient_over)
    med = schedule()
    with db.conn() as c:
        c.execute(
            "INSERT INTO patients (id, doc, is_mock) VALUES (?, ?, 1)",
            (patient["id"], json.dumps(patient)),
        )
        c.execute(
            "INSERT INTO med_schedules (patient_id, doc) VALUES (?, ?)",
            (patient["id"], json.dumps(med)),
        )
        c.execute(
            "INSERT INTO scheduled_calls (id, patient_id, day_index, kind, due_at, status, attempts, direction) "
            "VALUES ('call_rosa01d3', 'pat_rosa01', 3, 'checkin', '2026-11-15T19:00:00Z', 'in_call', 1, 'outbound')"
        )
    return patient


def test_route_picks_the_sharpest_frame_and_saves_proof(client, tmp_path, monkeypatch):
    from mac import capture

    _seed()
    ring = tmp_path / "ring"
    ring.mkdir()
    _jpeg(ring / "1000.jpg", checker=False)
    _jpeg(ring / "2000.jpg", checker=True)
    _jpeg(ring / "3000.jpg", checker=False)
    monkeypatch.setattr(capture, "RING", ring)
    monkeypatch.setattr(capture, "capture_once", lambda: (_ for _ in ()).throw(AssertionError("ring has frames")))

    res = client.post("/v1/vision/pillcheck", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "missed_possible"
    assert body["mismatches"] == ["SAT-PM"]
    assert body["expected_empty"] == AFTERNOON
    assert body["model"] == "fixture"
    assert body["image_quality"] == "good"
    assert "reason" not in body
    proof = Path(body["proof_ref"])
    assert proof.name == "call_rosa01d3_pill.jpg"
    assert proof.read_bytes() == (ring / "2000.jpg").read_bytes()

    from api import db

    with db.conn() as c:
        event = c.execute("SELECT name, payload FROM events WHERE name = 'vision.pill_check'").fetchone()
    assert json.loads(event["payload"])["state"] == "missed_possible"
    assert client.post("/v1/vision/pillcheck", json={"call_id": "nope"}).status_code == 404


def test_route_captures_when_the_ring_is_empty(client, tmp_path, monkeypatch):
    from mac import capture

    _seed()
    monkeypatch.setattr(capture, "RING", tmp_path / "empty-ring")
    monkeypatch.setattr(capture, "BURST_DIR", tmp_path / "burst")
    monkeypatch.setattr(capture, "LATEST", tmp_path / "latest.jpg")
    res = client.post("/v1/vision/pillcheck", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    assert res.json()["state"] == "missed_possible"
    assert Path(res.json()["proof_ref"]).read_bytes().startswith(b"\xff\xd8")


def test_route_rejects_a_bad_agent_token(client, monkeypatch):
    from mac import capture

    _seed()
    monkeypatch.setenv("AGENT_API_TOKEN", "secret")
    monkeypatch.setattr(capture, "capture_once", lambda: None)
    bare = client.post("/v1/vision/pillcheck", json={"call_id": "call_rosa01d3"})
    assert bare.status_code == 401
    ok = client.post(
        "/v1/vision/pillcheck",
        json={"call_id": "call_rosa01d3"},
        headers={"authorization": "Bearer secret"},
    )
    assert ok.status_code == 200


def test_route_no_frame_unknown(client, tmp_path, monkeypatch):
    from mac import capture

    _seed()
    monkeypatch.setattr(capture, "RING", tmp_path / "none")
    monkeypatch.setattr(capture, "capture_once", lambda: None)
    res = client.post("/v1/vision/pillcheck", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "unknown" and body["image_quality"] == "no_frame"
    assert body.get("proof_ref") is None


def test_route_consent(client, tmp_path, monkeypatch):
    from api import db
    from mac import capture
    from vision import pills

    patient = json.loads((EXAMPLES / "patient.json").read_text())
    patient["consent"] = {**patient["consent"], "proof_frames": False}
    _seed()
    with db.conn() as c:
        c.execute("UPDATE patients SET doc = ? WHERE id = ?", (json.dumps(patient), patient["id"]))
    ring = tmp_path / "ring-consent"
    ring.mkdir()
    _jpeg(ring / "1000.jpg", checker=True)
    monkeypatch.setattr(capture, "RING", ring)
    res = client.post("/v1/vision/pillcheck", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    assert res.json()["state"] == "missed_possible"
    assert res.json().get("proof_ref") is None
    assert list((tmp_path / "proof").glob("*")) == []

    patient["consent"] = {**patient["consent"], "video_analysis": False, "proof_frames": True}
    with db.conn() as c:
        c.execute("UPDATE patients SET doc = ? WHERE id = ?", (json.dumps(patient), patient["id"]))
    monkeypatch.setattr(
        pills, "read_organizer", lambda jpeg, layout: (_ for _ in ()).throw(AssertionError("no consent"))
    )
    res = client.post("/v1/vision/pillcheck", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    assert res.json()["state"] == "skipped"
    assert list((tmp_path / "proof").glob("*")) == []
