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
    "Both live pill checks failed with OpenAIError because this key was missing.\n"
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


def test_live_path_passes_each_photo_without_printing_the_key(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", PLANTED)
    calls = []

    def fake(jpeg, layout):
        calls.append(layout)
        assert isinstance(jpeg, bytes) and jpeg
        return {"pillbox_visible": True}

    monkeypatch.setattr("vision.pills.read_organizer", fake)
    from vision.livecheck import PHOTOS, main

    photos = [path for path in PHOTOS.iterdir() if path.suffix.lower() in {".jpg", ".jpeg"}]
    assert main() == 0
    captured = capsys.readouterr()
    count = len(photos)
    assert f"vision key: present\npill model: PASS ({count}/{count})\nbreathing: PASS\n" in captured.out
    assert PLANTED not in captured.out
    assert PLANTED not in captured.err
    assert calls == ["7x2"] * count


def test_pill_failure_prints_the_class_not_the_message(capsys, monkeypatch):
    _block_network(monkeypatch)
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", PLANTED)

    def fake(*_args, **_kwargs):
        raise RuntimeError(f"request echoed {PLANTED}")

    monkeypatch.setattr("vision.pills.read_organizer", fake)
    from vision.livecheck import main

    assert main() == 1
    captured = capsys.readouterr()
    assert "pill model: FAIL (RuntimeError on 01-all-empty.jpg)" in captured.out
    assert PLANTED not in captured.out
    assert PLANTED not in captured.err
    assert "request echoed" not in captured.out
    assert "breathing: PASS" in captured.out


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
