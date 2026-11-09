"""The voice step's worker watch (9 Nov): a hung Chatterbox worker is killed with its whole process tree and retried
once, a healthy one reports each line, and two makes never run Chatterbox at the same time. Stand-in workers, no GPU."""
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from frameflow import voice

FAKE = '''
import json, sys, time, os
job = json.load(open(sys.argv[-1]))
mode = os.environ["FAKE_MODE"]
print(json.dumps({"device": "cpu"}), flush=True)
if mode == "hang":
    open(os.environ["FAKE_PID"], "w").write(str(os.getpid()))
    time.sleep(600)
for l in job["lines"]:
    time.sleep(float(os.environ.get("FAKE_DELAY", "0")))
    open(l["out"], "wb").write(b"RIFF")
    print(json.dumps({"done": l["out"]}), flush=True)
'''


@pytest.fixture
def fake(tmp_path, monkeypatch):
    w = tmp_path / "worker.py"
    w.write_text(FAKE)
    monkeypatch.setattr(voice, "CHATTERBOX", [sys.executable, str(w)])
    monkeypatch.setattr(voice, "LOCK", tmp_path / "cb.lock")
    monkeypatch.setattr(voice, "STALL", 2)
    monkeypatch.setattr(voice, "LOAD_STALL", 2)
    return tmp_path


def lines(d, n=3):
    return [(f"line {i}", 0.6, d / f"{i}.raw.wav") for i in range(n)]


def test_healthy_worker_voices_every_line(fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "ok")
    got = voice.chatterbox_lines(lines(fake), fake)
    assert len(got) == 3 and all(Path(p).exists() for p in got)


def test_hung_worker_is_killed_with_its_tree_and_retried_once(fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "hang")
    monkeypatch.setenv("FAKE_PID", str(fake / "pid"))
    t0 = time.time()
    with pytest.raises(RuntimeError, match="stall"):
        voice.chatterbox_lines(lines(fake), fake)
    assert time.time() - t0 < 30                      # two stalls of ~2 s, not the 30-minute timeout
    pid = int((fake / "pid").read_text())
    time.sleep(0.3)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)                               # the worker itself is gone, not only its parent


def test_second_make_waits_for_the_first(fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "ok")
    monkeypatch.setenv("FAKE_DELAY", "0.5")
    ends = {}
    def make(name):
        d = fake / name
        d.mkdir()
        t = time.time()
        voice.chatterbox_lines(lines(d, 2), d)
        ends[name] = (t, time.time())
    a = threading.Thread(target=make, args=("a",))
    b = threading.Thread(target=make, args=("b",))
    a.start(); time.sleep(0.2); b.start(); a.join(); b.join()
    first, second = sorted(ends.values(), key=lambda x: x[1])
    assert second[1] - first[1] >= 0.9               # the second ran after the first, not alongside it
