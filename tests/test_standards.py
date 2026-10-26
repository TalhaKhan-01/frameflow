"""P15.3.3: the standards desk fails each policy breach with a precise message, and passes the real past videos."""
import json
from pathlib import Path

import pytest

from frameflow import standards

ROOT = Path(__file__).resolve().parent.parent


def _render(tmp_path, scenes, manifest=()):
    out = tmp_path / "render"
    (out / "project").mkdir(parents=True)
    (out / "plan.json").write_text(json.dumps({"scenes": scenes}))
    (out / "project" / "assets-manifest.json").write_text(json.dumps(list(manifest)))
    return out


def chat(note):
    d = {"prompt": "Paid Kimi campaign?", "reply": "Skip the paid-partnership label.", **({"note": note} if note is not None else {})}
    return {"type": "chat", "lines": [{"say": "A user posted screenshots."}], "data": d}


def test_labels(tmp_path):
    r = standards.run(_render(tmp_path, [chat("re-enactment - unverified claim")]))
    assert not r["pass"] and "31 characters" in r["checks"]["labels"]["problems"][0]
    r = standards.run(_render(tmp_path / "b", [chat(None)]))
    assert "needs an on-screen note" in r["checks"]["labels"]["problems"][0]
    assert standards.run(_render(tmp_path / "c", [chat("re-enactment")]))["checks"]["labels"]["pass"]


def test_licences(tmp_path):
    rows = [{"asset": "scene 3 snapshot", "source": "screenshot", "licence": "fair use", "url": "https://x.example", "author": ""}]
    r = standards.run(_render(tmp_path, [], rows))
    assert r["checks"]["licences"]["problems"] == ["scene 3 snapshot: no author"]


def test_numbers(tmp_path):
    scene = {"type": "stat", "lines": [{"say": "It scored eighty-three point two percent on three hundred and four cases."}],
             "data": {"value": "83.2%", "label": "of 304 cases", "sub": "doctors 36.1%"}}
    r = standards.run(_render(tmp_path, [scene]))
    assert r["checks"]["numbers"]["problems"] == ["scene 0 (stat): on-screen number(s) 36.1 are not said in the script nor in the brief's facts"]
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"facts": [{"text": "Generalist doctors scored 36.1% on the same cases."}]}))
    assert standards.run(_render(tmp_path / "b", [scene]), brief)["pass"]
    assert [f["row"] for f in standards.fixes(r)] == ["sources"]


@pytest.mark.parametrize("slug,brief", [("2026-10-26-china-s-moonshot-ai-launches-kimi", "2026-10-26-china-s-moonshot-ai-launches-kimi"),
                                        ("2026-10-25-microsoft-develops-ai-tool-that-can", "2026-10-25-microsoft-develops-ai-tool-that-can"),
                                        ("black-october", "black-october")])
def test_past_videos_pass(slug, brief):
    out = ROOT / "out" / slug / "render"
    if not (out / "plan.json").exists():
        pytest.skip("video not here")
    assert standards.run(out, ROOT / "briefs" / f"{brief}.json")["pass"]
