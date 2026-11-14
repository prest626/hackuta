import socket

from mac.doctor import AUDIO_ARGV, FACETIME_ARGV, blackholes, device_names, failed, format_row, judge, port_free

AUDIO_BOTH = """
Audio:

    Devices:

        MacBook Pro Speakers:

          Default Output Device: Yes

        BlackHole 2ch:

          Manufacturer: Existential Audio Inc.
          Output Channels: 2

        BlackHole 16ch:

          Manufacturer: Existential Audio Inc.
          Output Channels: 16
"""

AUDIO_NO_16 = AUDIO_BOTH.replace("BlackHole 16ch:", "Mac Studio Speakers:")


def test_device_names_are_headers_only():
    names = device_names(AUDIO_BOTH)
    assert names == ["MacBook Pro Speakers", "BlackHole 2ch", "BlackHole 16ch"]


def test_blackholes_pass_and_fail():
    assert blackholes(AUDIO_BOTH) == (True, True)
    assert blackholes(AUDIO_NO_16) == (True, False)
    assert blackholes("BlackHole 2ch is mentioned but not a device header") == (False, False)


def test_judge_pass_fail_from_canned_profiler():
    rows = dict((name, status) for name, status, _ in judge({
        "sox": True,
        "node": False,
        "ffmpeg": True,
        "audio": AUDIO_NO_16,
        "facetime": False,
        "port_free": True,
        "env_local": False,
    }))
    assert rows["sox"] == "PASS"
    assert rows["node"] == "FAIL"
    assert rows["ffmpeg"] == "PASS"
    assert rows["blackhole-2ch"] == "PASS"
    assert rows["blackhole-16ch"] == "FAIL"
    assert rows["facetime"] == "FAIL"
    assert rows["port-8000"] == "PASS"
    assert rows["env-local"] == "FAIL"
    assert failed([(n, s, "") for n, s in rows.items()])


def test_dry_run_skips_mac_probes():
    rows = judge({
        "sox": True,
        "node": True,
        "ffmpeg": True,
        "audio": None,
        "facetime": None,
        "port_free": True,
        "env_local": True,
    })
    status = {name: st for name, st, _ in rows}
    assert status["blackhole-2ch"] == "SKIP"
    assert status["blackhole-16ch"] == "SKIP"
    assert status["facetime"] == "SKIP"
    assert not failed(rows)


def test_format_row_never_includes_a_secret_body():
    line = format_row("env-local", "FAIL", "facetime-bridge/.env.local missing")
    assert "OPENAI" not in line
    assert "=" not in line


def test_probe_commands_match_the_printed_dry_run():
    assert AUDIO_ARGV == ["system_profiler", "SPAudioDataType"]
    assert FACETIME_ARGV == ["pgrep", "-x", "FaceTime"]


def test_port_free_sees_a_listener():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        assert port_free(port) is False
    assert port_free(port) is True
