import copy
import json
from pathlib import Path

from frameflow.scene_plan import MAX_SECONDS, total_seconds, validate

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "sample-plan.json").read_text())


def plan():
    return copy.deepcopy(SAMPLE)


def test_sample_plan_is_valid():
    assert validate(plan()) == []
    assert total_seconds(plan()) <= MAX_SECONDS


def test_unknown_scene_type_is_rejected():
    p = plan()
    p["scenes"][1]["type"] = "spinning-logo"
    assert any("not a scene in the library" in e for e in validate(p))


def test_missing_field_is_rejected():
    p = plan()
    del p["scenes"][2]["data"]["label"]
    assert any("data.label" in e for e in validate(p))


def test_plan_over_95_seconds_is_rejected():
    p = plan()
    p["scenes"] += [copy.deepcopy(p["scenes"][1]) for _ in range(30)]
    assert any("over 95 s" in e for e in validate(p))


def test_claim_without_source_is_rejected():
    p = plan()
    p["scenes"][0]["sources"] = []
    assert any("no source URL" in e for e in validate(p))


def test_claim_with_non_url_source_is_rejected():
    p = plan()
    p["scenes"][2]["sources"] = ["trust me"]
    assert any("no source URL" in e for e in validate(p))


def test_unknown_lane_is_rejected():
    p = plan()
    p["lane"] = "cooking"
    assert any(e.startswith("lane") for e in validate(p))
