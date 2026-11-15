"""VISION-3: python -m vision.eval on the synthetic organizers, VISION_FAKE."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
PHOTOS = REPO / "vision" / "eval" / "photos"

# VISION_FAKE names SAT-PM full, SUN-AM empty, SUN-PM full. Other labeled cells count wrong.
# That score is the canned read, not the live-model gate (real photos stay off the Mac).


def test_cli_on_synthetic_set():
    env = os.environ.copy()
    env["VISION_FAKE"] = "fixtures"
    env["MAC_DRY_RUN"] = "1"
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.run(
        [sys.executable, "-m", "vision.eval"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "01-all-empty.jpg fail 1/14" in out
    assert "02-all-full.jpg fail 2/14" in out
    assert "03-sat-pm.jpg fail 2/14" in out
    assert "04-sun-am.jpg fail 0/14" in out
    assert "05-sat-pm-sun-pm.jpg fail 3/14" in out
    assert "06-partial.jpg fail 2/4" in out
    assert "per-compartment accuracy: 21/186 on non-unknown" in out
    assert "unknown rate: 0/14" in out
    assert "reader: VISION_FAKE fixtures (one canned read for every photo)" in out
    jpgs = sorted(PHOTOS.glob("*.jpg"))
    assert [path.name for path in jpgs] == [
        "01-all-empty.jpg",
        "02-all-full.jpg",
        "03-sat-pm.jpg",
        "04-sun-am.jpg",
        "05-sat-pm-sun-pm.jpg",
        "06-partial.jpg",
        "07-mon-am.jpg",
        "08-am-row.jpg",
        "09-sun-pm.jpg",
        "10-fri-both.jpg",
        "11-weekend.jpg",
        "12-three-days.jpg",
        "13-blur.jpg",
        "14-occlusion.jpg",
    ]
    for path in jpgs:
        with Image.open(path) as img:
            img.load()
            assert img.format == "JPEG"


def test_pixel_reader_clears_nine_tenths():
    env = os.environ.copy()
    env["MAC_DRY_RUN"] = "1"
    env["PYTHONPATH"] = str(REPO)
    env.pop("OPENAI_API_KEY", None)
    env.pop("GOOGLE_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-m", "vision.eval", "--reader", "pixels"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    match = re.search(r"per-compartment accuracy: (\d+)/(\d+) on non-unknown", proc.stdout)
    assert match
    correct, labeled = int(match.group(1)), int(match.group(2))
    assert labeled and correct / labeled >= 0.9
    spec = json.loads((REPO / "vision" / "eval" / "labels.json").read_text())
    expected_unknown = [row["file"] for row in spec["photos"] if row.get("expect") == "unknown"]
    assert expected_unknown == ["13-blur.jpg", "14-occlusion.jpg"]
    for name in expected_unknown:
        assert f"{name} unknown" in proc.stdout
    assert "01-all-empty.jpg pass 14/14" in proc.stdout
    assert "reader: pixels" in proc.stdout


def test_empty_photo_dir_skips():
    env = os.environ.copy()
    env["MAC_DRY_RUN"] = "1"
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.run(
        [sys.executable, "-m", "vision.eval", "--dir", "vision/eval/preston"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "real photos: 0 (skipped)"


def test_dir_without_a_key_marks_the_fixture_reader(tmp_path):
    shot = tmp_path / "shots"
    shot.mkdir()
    (shot / "01-all-empty.jpg").write_bytes((PHOTOS / "01-all-empty.jpg").read_bytes())
    (tmp_path / "labels.json").write_text(json.dumps({"photos": [{"file": "01-all-empty.jpg", "filled": []}]}))
    env = os.environ.copy()
    env["MAC_DRY_RUN"] = "1"
    env["PYTHONPATH"] = str(REPO)
    env.pop("OPENAI_API_KEY", None)
    env.pop("GOOGLE_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-m", "vision.eval", "--dir", str(shot), "--labels", str(tmp_path / "labels.json")],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "real photos: 1" in proc.stdout
    assert "per-compartment accuracy: 1/14 on non-unknown" in proc.stdout
    assert "reader: VISION_FAKE fixtures (not a model score)" in proc.stdout


def test_unknown_photos_are_out_of_the_accuracy():
    from contracts.models import ObservedCompartment, PillCheck
    from vision.eval import report

    truth = {"MON-AM": "empty", "MON-PM": "has_pills"}
    unknown = PillCheck(state="unknown", image_quality="partial", confidence=0.2)
    scored = PillCheck(
        state="ok",
        image_quality="good",
        confidence=0.9,
        observed=[ObservedCompartment(compartment="MON-AM", state="empty")],
    )
    text = report([("a.jpg", unknown, truth), ("b.jpg", scored, truth)])
    assert "a.jpg unknown" in text
    assert "b.jpg fail 1/2" in text
    assert "per-compartment accuracy: 1/2 on non-unknown" in text
    assert "unknown rate: 1/2" in text


def test_missing_photo_is_drawn(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_FAKE", "fixtures")
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"photos": [{"file": "01-all-empty.jpg", "filled": []}]}))
    photos = tmp_path / "photos"
    monkeypatch.setattr("vision.eval.LABELS", labels)
    monkeypatch.setattr("vision.eval.PHOTOS", photos)
    from vision.eval import evaluate

    text = evaluate()
    saved = photos / "01-all-empty.jpg"
    assert saved.is_file()
    with Image.open(saved) as img:
        img.load()
        assert img.format == "JPEG"
    assert "01-all-empty.jpg fail 1/14" in text
    assert "unknown rate: 0/1" in text
