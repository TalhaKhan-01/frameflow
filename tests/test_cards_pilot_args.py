"""The card post's Pilot fallback passes flags the Pilot accepts (27 Oct: '--in-caption' failed every Instagram fallback)."""
import json
import subprocess

from frameflow import cards


def test_fallback_flags_parse(tmp_path, monkeypatch):
    run = "cards-test"
    out = tmp_path / run
    out.mkdir()
    (out / "slide-01.png").write_bytes(b"x")
    monkeypatch.setattr(cards, "OUT", tmp_path)
    monkeypatch.setattr(cards, "get", lambda r: {"caption": json.dumps({"ig_caption": "ig", "fb_caption": "fb"})})
    monkeypatch.setattr(cards, "update", lambda *a, **k: None)
    monkeypatch.setattr(cards.telegram, "send", lambda *a, **k: None)
    import frameflow.webexport as we
    monkeypatch.setattr(we, "refresh", lambda *a, **k: "skipped")
    seen = []
    def fake_run(cmd, **k):
        seen.append(cmd)
        if "frameflow.pilot" in cmd:
            ap_args = cmd[cmd.index("photos"):]
            flags = [x for x in ap_args if x.startswith("--")]
            assert set(flags) <= {"--fb-caption", "--ig-caption"}, flags
            return subprocess.CompletedProcess(cmd, 0, json.dumps({"facebook": "fb-url", "instagram": "ig-url"}), "")
        return subprocess.CompletedProcess(cmd, 1, "", "token expired")
    monkeypatch.setattr(subprocess, "run", fake_run)
    cards.post(run)
    assert any("--ig-caption" in c for c in seen if "frameflow.pilot" in c)
