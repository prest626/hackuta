"""The checked-in Swift encoder fixture is a valid WatchHrPost.

JSONEncoder sortedKeys on WatchHrPost: device_id plus samples of {bpm, t_end}.
source is omitted; the model default is workout, which ingest stores as watch_workout.
Runs on Linux. The XCTest file runs on Preston's Mac.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from contracts.models import WatchHrPost

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "watch" / "fixtures" / "watch_hr_post.json"


def test_swift_encoder_fixture_matches_watch_hr_post():
    schema = json.loads((ROOT / "contracts" / "vitals.schema.json").read_text())
    registry = Registry().with_resource(schema["$id"], Resource.from_contents(schema))
    data = json.loads(FIXTURE.read_text())
    Draft202012Validator(
        {"$ref": schema["$id"] + "#/$defs/WatchHrPost"},
        registry=registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    ).validate(data)
    parsed = WatchHrPost.model_validate(data)
    assert parsed.device_id == "watch_team01"
    assert [(s.t_end, s.bpm, s.source) for s in parsed.samples] == [
        ("2026-11-15T19:02:00Z", 80, "workout"),
        ("2026-11-15T19:02:05Z", 81, "workout"),
    ]
    assert set(data["samples"][0]) == {"bpm", "t_end"}
