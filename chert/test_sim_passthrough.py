"""Offline chert.wire passthrough. Fake request(), no socket, no dial."""

import chert.sim_passthrough as sim
import chert.wire as wire


def test_green_days_use_the_empty_read_and_stay_green():
    for day in (1, 2, 4):
        request = sim.fake_request(day_index=day)
        body = sim.post_green(request)
        assert body["day_index"] == day
        assert body["call_id"] == f"call_rosa01d{day}"
        assert body["pill_check"]["state"] == "ok"
        assert body["pill_check"]["model"] == "green"
        assert [item["value"] for item in body["symptoms"]] == ["same", "no", "no", "no"]
        assert sim.result_tier(body) == "GREEN"
        assert not any("/dial" in (item[1] or "") for item in request.seen)


def test_day3_result_is_posted():
    request = sim.fake_request()
    body = sim.post_day3(request)
    posts = [item for item in request.seen if item[0] == "POST"]
    assert posts == [("POST", "/v1/calls/call_rosa01d3/result", body)]
    assert body["day_index"] == 3
    assert body["pill_check"]["state"] == "missed_possible"
    assert body["symptoms"][0]["value"] == "worse"
    assert not any("/dial" in (item[1] or "") for item in request.seen)


def test_911_phrase_returns_the_fixed_line_and_does_not_dial():
    request = sim.fake_request()
    line, body = sim.on_911(request, "call 911")
    assert line == "This could be serious. Please hang up and call 911 now."
    assert line == wire.EMERGENCY_LINE
    assert body["status"] == "emergency_script"
    assert body["emergency_script_given"] is True
    assert not any("/dial" in (item[1] or "") or "facetime://" in (item[1] or "") for item in request.seen)


def test_skipped_breathing_and_low_sqi_stay_at_or_under_yellow():
    assert sim.at_or_under_yellow(sim.breathing_tier({"mode": "skipped"}))
    low = sim.breathing_tier({"mode": "paced_measured", "rate_per_min": 40, "sqi": 0.2})
    assert sim.at_or_under_yellow(low)
    assert low != "RED"


def test_request_raising_is_api_down(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("dialed")

    monkeypatch.setattr("mac.facetime.dial", boom)
    monkeypatch.setattr("httpx.request", boom)
    request = sim.fake_request(down=True)
    assert sim.run_down(request) != 0
    assert request.seen == []


def test_main_does_not_open_a_socket(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("socket")

    monkeypatch.setattr("httpx.request", boom)
    monkeypatch.setattr("socket.socket", boom)
    assert sim.main() == 0
