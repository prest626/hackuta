"""Offline checks for vision.livecheck. No network. Not a medical device."""

import os
import socket
import subprocess
from pathlib import Path

PLANTED = "planted-vision-key-9f3c1a7e"
ROOT = Path(__file__).resolve().parents[1]
INSTRUCTION = (
    "vision key: MISSING\n"
    "Set OPENAI_API_KEY in the environment of the process that runs the API, then run make vision-test again.\n"
    "Or, for a demo fallback only, run: VISION_FAKE=fixtures make vision-test\n"
    "That fallback does not call the model and is not a live score.\n"
)


def _block_network(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr(socket, "create_connection", blocked)


def _clear(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    monkeypatch.delenv("VISION_FAKE", raising=False)
    monkeypatch.delenv("CHERT_FRAMES", raising=False)
    from vision import livecheck

    monkeypatch.setattr(livecheck, "FRAMES_ROOT", Path("/tmp/livecheck-no-frames"))


def _refuse_model(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("read_organizer must not be called")

    monkeypatch.setattr("vision.pills.read_organizer", boom)


def test_planted_key_is_absent_from_stdout(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", PLANTED)
    monkeypatch.setenv("VISION_FAKE", "fixtures")
    _refuse_model(monkeypatch)
    from vision.livecheck import main

    assert main() == 0
    captured = capsys.readouterr()
    assert PLANTED not in captured.out
    assert PLANTED not in captured.err
    assert "FALLBACK" in captured.out


def test_missing_key_prints_instruction_and_skips_model(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("VISION_FAKE", "")
    _refuse_model(monkeypatch)
    from vision.livecheck import main

    assert main() == 1
    out = capsys.readouterr().out
    assert INSTRUCTION in out
    assert "Both live pill checks failed" not in out
    assert "OpenAIError" not in out
    assert "breathing: PASS" in out
    assert "read_organizer" not in out


def test_vision_fake_prints_fallback_and_skips_model(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("VISION_FAKE", "fixtures")
    _refuse_model(monkeypatch)
    from vision.livecheck import main

    assert main() == 0
    out = capsys.readouterr().out
    assert "pill model: FALLBACK (VISION_FAKE is set; not a live score)" in out
    assert "vision key: MISSING" not in out
    assert "breathing: PASS" in out


def test_synthetic_clip_passes(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("VISION_FAKE", "fixtures")
    _refuse_model(monkeypatch)
    from vision.livecheck import main

    assert main() == 0
    assert "breathing: PASS" in capsys.readouterr().out


def test_gemini_instruction_names_google_key(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    _refuse_model(monkeypatch)
    from vision.livecheck import main

    assert main() == 1
    out = capsys.readouterr().out
    assert "Set GOOGLE_API_KEY in the environment" in out
    assert "OPENAI_API_KEY" not in out
    assert "breathing: PASS" in out


def _rows():
    import json

    from vision.eval import LABELS

    return json.loads(LABELS.read_text())["photos"]


def _matching_read(row):
    from vision.eval import cells

    if row.get("expect") == "unknown":
        return {"pillbox_visible": False, "compartments": [], "confidence": 0.1, "reason": "blur"}
    truth = cells(row)
    return {
        "pillbox_visible": True,
        "compartments": [{"label": name, "has_pills": state == "has_pills"} for name, state in truth.items()],
        "confidence": 0.95,
        "reason": "mock",
    }


def _mock_labeled_reads(monkeypatch, wrong):
    rows = {row["file"]: row for row in _rows()}
    blobs = {}
    from vision.livecheck import PHOTOS

    for path in PHOTOS.iterdir():
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            blobs[path.read_bytes()] = path.name
    calls = []

    def fake(jpeg, layout):
        calls.append(layout)
        name = blobs[jpeg]
        if name in wrong:
            return {"pillbox_visible": True, "compartments": [{"label": "MON-AM", "has_pills": True}], "confidence": 0.99, "reason": "no"}
        return _matching_read(rows[name])

    monkeypatch.setattr("vision.pills.read_organizer", fake)
    return calls


def test_live_path_scores_labels_without_printing_the_key(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", PLANTED)
    calls = _mock_labeled_reads(monkeypatch, wrong=set())
    from vision.livecheck import main

    assert main() == 0
    captured = capsys.readouterr()
    assert "01-all-empty.jpg ok" in captured.out
    assert "13-blur.jpg ok" in captured.out
    assert "pill model: PASS (14/14, 100%)" in captured.out
    assert "breathing: PASS" in captured.out
    assert PLANTED not in captured.out
    assert PLANTED not in captured.err
    assert calls == ["7x2"] * 14


def test_score_fails_below_80_percent(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", PLANTED)
    names = sorted(row["file"] for row in _rows())
    _mock_labeled_reads(monkeypatch, wrong=set(names[11:]))
    from vision.livecheck import main

    assert main() == 1
    out = capsys.readouterr().out
    assert "12-three-days.jpg wrong" in out
    assert "pill model: FAIL (11/14, 79%)" in out
    assert PLANTED not in out


def test_score_passes_at_80_percent(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", PLANTED)
    names = sorted(row["file"] for row in _rows())
    _mock_labeled_reads(monkeypatch, wrong=set(names[12:]))
    from vision.livecheck import main

    assert main() == 0
    assert "pill model: PASS (12/14, 86%)" in capsys.readouterr().out


def test_missing_labels_say_ran_not_scored(tmp_path, capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", PLANTED)
    monkeypatch.setattr("vision.livecheck.LABELS", tmp_path / "missing.json")

    def fake(jpeg, layout):
        assert jpeg and layout == "7x2"
        return {"pillbox_visible": True}

    monkeypatch.setattr("vision.pills.read_organizer", fake)
    from vision.livecheck import main

    assert main() == 0
    out = capsys.readouterr().out
    assert "no labels (ran, not scored)" in out
    assert "pill model: PASS (14/14, ran, not scored)" in out
    assert PLANTED not in out


def test_scored_exception_hides_the_message(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", PLANTED)

    def fake(*_args, **_kwargs):
        raise RuntimeError(f"request echoed {PLANTED}")

    monkeypatch.setattr("vision.pills.read_organizer", fake)
    from vision.livecheck import main

    assert main() == 1
    out = capsys.readouterr().out
    assert "01-all-empty.jpg wrong" in out
    assert "pill model: FAIL (0/14, 0%)" in out
    assert PLANTED not in out
    assert "request echoed" not in out


def test_pill_failure_prints_the_class_not_the_message(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", PLANTED)
    monkeypatch.setattr("vision.livecheck.LABELS", Path("/tmp/livecheck-no-labels.json"))

    def fake(*_args, **_kwargs):
        raise RuntimeError(f"request echoed {PLANTED}")

    monkeypatch.setattr("vision.pills.read_organizer", fake)
    from vision.livecheck import main

    assert main() == 1
    captured = capsys.readouterr()
    assert "pill model: FAIL (RuntimeError on 01-all-empty.jpg, ran, not scored)" in captured.out
    assert PLANTED not in captured.out
    assert PLANTED not in captured.err
    assert "request echoed" not in captured.out
    assert "breathing: PASS" in captured.out


def test_real_frames_are_information_only(tmp_path, capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("VISION_FAKE", "fixtures")
    _refuse_model(monkeypatch)
    newest = 1_700_000_000_000
    call = tmp_path / "call"
    call.mkdir()
    kept = {newest - 10_000, newest}
    for stamp in (newest - 30_000, newest - 10_000, newest):
        (call / f"{stamp}.jpg").write_bytes(b"\xff\xd8\xff")
    (call / "not-a-stamp.jpg").write_bytes(b"\xff\xd8\xff")
    monkeypatch.setenv("CHERT_FRAMES", str(call))
    from contracts.models import Breathing
    from vision.breath import measure_breathing as real_measure

    seen = []

    def wrapped(frames):
        if frames and str(call) in frames[0][1]:
            seen.append([stamp for stamp, _ in frames])
            return Breathing(mode="abstained", note="Wellness check only.")
        return real_measure(frames)

    monkeypatch.setattr("vision.livecheck.measure_breathing", wrapped)
    from vision.livecheck import main

    assert main() == 0
    out = capsys.readouterr().out
    assert "breathing: PASS" in out
    assert "breathing (real call frames): mode=abstained, rate=none" in out
    assert seen == [[stamp / 1000.0 for stamp in sorted(kept)]]


def test_newest_call_dir_is_used_when_frames_env_is_unset(tmp_path, capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("VISION_FAKE", "fixtures")
    _refuse_model(monkeypatch)
    older = tmp_path / "older"
    newer = tmp_path / "newer"
    older.mkdir()
    newer.mkdir()
    (older / "1000.jpg").write_bytes(b"\xff\xd8\xff")
    (newer / "2000.jpg").write_bytes(b"\xff\xd8\xff")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    monkeypatch.setattr("vision.livecheck.FRAMES_ROOT", tmp_path)
    from vision.breath import measure_breathing as real_measure

    seen = []

    def wrapped(frames):
        if frames and str(tmp_path) in frames[0][1]:
            seen.append(frames[0][1])
            from contracts.models import Breathing

            return Breathing(mode="abstained", note="Wellness check only.")
        return real_measure(frames)

    monkeypatch.setattr("vision.livecheck.measure_breathing", wrapped)
    from vision.livecheck import main

    assert main() == 0
    assert seen and seen[0].endswith("/newer/2000.jpg")
    assert "breathing (real call frames): mode=abstained, rate=none" in capsys.readouterr().out


def test_make_passes_vision_fake_only_when_the_operator_set_it():
    env = os.environ.copy()
    for name in ("VISION_FAKE", "OPENAI_API_KEY", "GOOGLE_API_KEY", "VISION_PROVIDER"):
        env.pop(name, None)
    plain = subprocess.run(["make", "-n", "vision-test"], cwd=ROOT, env=env, text=True, capture_output=True, check=True)
    assert 'VISION_FAKE=""' in plain.stdout
    explicit = env.copy()
    explicit["VISION_FAKE"] = "fixtures"
    flagged = subprocess.run(["make", "-n", "vision-test"], cwd=ROOT, env=explicit, text=True, capture_output=True, check=True)
    assert 'VISION_FAKE="fixtures"' in flagged.stdout
    cmdline = subprocess.run(
        ["make", "-n", "VISION_FAKE=green", "vision-test"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert 'VISION_FAKE="green"' in cmdline.stdout


def test_no_photos_fails(tmp_path, capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", PLANTED)
    _refuse_model(monkeypatch)
    monkeypatch.setattr("vision.livecheck.PHOTOS", tmp_path)
    from vision.livecheck import main

    assert main() == 1
    out = capsys.readouterr().out
    assert "pill model: FAIL (no photos)" in out
    assert PLANTED not in out
    assert "breathing: PASS" in out
