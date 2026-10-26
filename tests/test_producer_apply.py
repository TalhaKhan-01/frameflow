"""P15.4.2: a confirmed change order runs exactly its stages (every stage stubbed, calls recorded)."""
import json
from pathlib import Path

import pytest

from frameflow import board, daily, pipeline, producer, publish, qa, review


@pytest.fixture()
def world(tmp_path, monkeypatch):
    out = tmp_path / "slug" / "render"
    out.mkdir(parents=True)
    plan = tmp_path / "slug" / "plan.json"
    plan.write_text(json.dumps({"scenes": []}))
    (out / "review.json").write_text(json.dumps({"total": 15, "max": 22, "pass": False}))
    (out / "qa.json").write_text(json.dumps({"pass": True, "gates": {}}))
    calls = []
    run = {"lane": "ai-money", "brief": "brief.json", "order_file": str(tmp_path / "order.json")}
    monkeypatch.setattr(producer, "_video", lambda day: (run, {"id": "v1"}, out, plan))
    monkeypatch.setattr(board, "_revise", lambda brief, p, fixes, lane, label, desk: calls.append(("revise", desk, [f["row"] for f in fixes])) or True)
    monkeypatch.setattr(board, "run", lambda brief, p, lane: calls.append(("board",)) or {"qa": {"pass": True}, "review": {"total": 17, "max": 22}})
    monkeypatch.setattr(pipeline, "build_stage", lambda o, theme=None: calls.append(("scenes",)))
    monkeypatch.setattr(pipeline, "remix_stage", lambda o: calls.append(("remix",)))
    monkeypatch.setattr(pipeline, "voice_stage", lambda *a, **k: calls.append(("VOICE",)))
    monkeypatch.setattr(pipeline, "deliver_stage", lambda *a, **k: calls.append(("RENDER",)))
    monkeypatch.setattr(qa, "run", lambda o: calls.append(("qc",)) or {"pass": True, "gates": {}})
    monkeypatch.setattr(review, "check_final", lambda o, p: calls.append(("final",)) or {"total": 15, "max": 22})
    monkeypatch.setattr(publish, "publish", lambda vid, owner_notes="", require=True: calls.append(("packaging", owner_notes, require)))

    def order(changes, stages, keep=()):
        Path(run["order_file"]).write_text(json.dumps({"gist": "g", "changes": changes, "keep": list(keep), "stages": stages, "minutes": 1,
                                                       "targets": sorted({c["target"] for c in changes})}))
    return calls, order


def test_music_only_remixes_without_voice_or_render(world):
    calls, order = world
    order([{"target": "sound", "scenes": [], "instruction": "music 4 dB lower"}], ["director", "scenes", "remix", "qc"])
    q, r = producer.apply("d")
    assert calls == [("revise", "director", ["sound_plan"]), ("scenes",), ("remix",), ("qc",)]
    assert r["total"] == 15, "pictures and words unchanged: the screening stands"


def test_words_go_through_the_writer_and_the_whole_board(world):
    calls, order = world
    order([{"target": "words", "scenes": [0], "instruction": "sharper hook"}],
          ["writer", "director", "narrator", "checks", "scenes", "standards", "animatic", "screening", "render", "qc", "final-check"],
          keep=["the ending"])
    q, r = producer.apply("d")
    assert calls[0][0] == "revise" and calls[0][1] == "writer" and calls[0][2] == ["story", "visual_storytelling", "flow"]
    assert calls[1:] == [("board",)] and r["total"] == 17


def test_hashtags_only_touch_the_post_text(world):
    calls, order = world
    order([{"target": "post_text", "scenes": [], "instruction": "swap #ai for #aiindia"}], ["packaging"])
    producer.apply("d")
    assert calls == [("packaging", "swap #ai for #aiindia", False)]


def test_fixes_for_routes_voice_as_delivery_only():
    o = {"changes": [{"target": "voice", "scenes": [3], "instruction": "slow down on the price"}], "keep": []}
    f = producer.fixes_for(o)
    assert f[0]["row"] == "persona_humour" and "keep the words" in f[0]["fix"] and "scene(s) 3" in f[0]["fix"]
