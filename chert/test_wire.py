import json
import os
from pathlib import Path

import chert.homeward as homeward
import chert.wire as wire


def test_prompt_includes_call_context():
    prompt = wire.load_prompt()
    assert "not a medical device" in prompt
    assert "no diagnosis" in prompt
    call = {
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "day_index": 3,
        "patient": {"id": "pat_rosa01", "display_name": "Rosa"},
    }
    text = wire.instructions(prompt, call)
    assert "pat_rosa01" in text
    assert "call_rosa01d3" in text
    assert '"day_index": 3' in text


def test_metadata_call_fields_win():
    meta = json.dumps({
        "patient_id": "pat_rosa01",
        "call_id": "call_meta01",
        "day_index": 3,
    })

    def request(method, path, body=None):
        if path == "/v1/calls/active":
            return {
                "call_id": "call_other1",
                "patient_id": "pat_luis01",
                "day_index": 1,
                "kind": "checkin",
                "direction": "outbound",
            }
        return {
            "day_index": 1,
            "patient": {
                "id": "pat_luis01",
                "display_name": "Luis",
                "red_flags": {"urgent_911": ["chest pain"]},
            },
        }

    call = wire.fetch_context(meta, request)
    assert call["call_id"] == "call_meta01"
    assert call["patient_id"] == "pat_rosa01"
    assert call["day_index"] == 3
    assert call["phrases"] == ["chest pain"]


def test_emergency_line_matches_the_call_agent():
    assert wire.emergency_line("I have chest pain") == wire.EMERGENCY_LINE
    assert wire.emergency_line("I can't breathe") == wire.EMERGENCY_LINE
    assert wire.emergency_line("please call 911") == wire.EMERGENCY_LINE
    assert wire.emergency_line("my chest feels fine") is None
    assert wire.emergency_line("no chest pain") is None
    assert wire.EMERGENCY_LINE == "This could be serious. Please hang up and call 911 now."


def test_latest_jpeg_is_the_pill_frame(tmp_path, monkeypatch):
    old = tmp_path / "1.jpg"
    new = tmp_path / "2.jpg"
    payload = b"\xff\xd8\xff\xd9"
    old.write_bytes(payload)
    new.write_bytes(payload)
    os.utime(old, (1, 1))
    os.utime(new, (2, 2))
    seen = {}

    def copy(jpeg, ring):
        seen["jpeg"] = Path(jpeg)
        return Path(ring) / "x.jpg"

    def request(method, path, body=None):
        seen["path"] = path
        seen["body"] = body
        return {"state": "ok"}

    monkeypatch.setattr(homeward, "_copy_jpeg", copy)
    monkeypatch.setattr(homeward, "_request", request)
    line, pill = wire.read_pillbox(wire.latest_jpeg(tmp_path), tmp_path / "ring", "call_rosa01d3")
    assert seen["jpeg"] == new
    assert seen["path"] == "/v1/vision/pillcheck"
    assert seen["body"] == {"call_id": "call_rosa01d3"}
    assert line == homeward.EMPTY
    assert pill["state"] == "ok"


def test_result_validates_and_flags_emergency():
    call = {
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "day_index": 3,
        "kind": "checkin",
        "direction": "outbound",
    }
    quiet = wire.build_result(call, started_at="2026-11-15T00:00:00Z", ended_at="2026-11-15T00:02:00Z")
    assert quiet["breathing"] == {"mode": "skipped"}
    assert quiet["pill_check"] == {"state": "skipped"}
    assert quiet["emergency_script_given"] is False
    assert quiet["vitals_snapshot"]["stale"] is True
    flagged = wire.build_result(
        call,
        emergency=True,
        started_at="2026-11-15T00:00:00Z",
        ended_at="2026-11-15T00:01:00Z",
    )
    assert flagged["status"] == "emergency_script"
    assert flagged["emergency_script_given"] is True
    assert "diagnos" not in flagged["summary_text"].lower()
