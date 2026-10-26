"""P15.6.3: the rounds level (run after every make) takes the animatic's draft and earlier rounds, never the deliverables."""
from frameflow import cleanup


def test_rounds_level_takes_the_animatic_draft(tmp_path):
    base = tmp_path / "slug"
    render = base / "render"
    (render / "animatic").mkdir(parents=True)
    (base / "render-r1").mkdir()
    for n in ("animatic.mp4", "final.mp4", "cover.png", "animatic.jpg", "raw.mp4"):
        (render / n).write_bytes(b"x")
    from frameflow import videos
    row = {"id": "p15-cleanup-test", "plan": str(base / "plan.json"), "out_dir": str(render), "status": "awaiting-approval",
           "updated_at": videos.now()}   # made today: the posted level must not apply
    rounds, posted = cleanup.targets(row)
    names = {p.name for p in rounds}
    assert {"animatic.mp4", "animatic", "render-r1"} <= names
    assert not names & {"final.mp4", "cover.png", "animatic.jpg", "raw.mp4"}, "deliverables, the sheet and the frames stay"
    assert posted == [], "the raw render waits for the posted level"
