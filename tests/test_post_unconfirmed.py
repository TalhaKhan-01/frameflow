"""A post the site accepted but whose link wasn't found counts as posted, never as missing (27 Oct: live Reels were reported
'Not posted', and a retry would have posted them twice)."""
import json

from frameflow import daily, pilot, publish, telegram


def test_unconfirmed_counts_as_posted(monkeypatch):
    assert str(pilot.Unconfirmed("x")).startswith("UNCONFIRMED")
    run = {"video_id": "v1", "day": "d"}
    state, sent = {}, []
    monkeypatch.setattr(daily, "get", lambda day: run)
    monkeypatch.setattr(daily, "update", lambda day, **kw: state.update(kw))
    monkeypatch.setattr(daily, "cfg", lambda: {"platforms": ["youtube", "instagram", "facebook"]})
    monkeypatch.setattr(telegram, "send", lambda text, *a, **k: sent.append(text))

    class Row(dict):
        pass
    class DB:
        def execute(self, *a):
            return self
        def fetchone(self):
            return {"out_dir": "/nonexistent"}
    monkeypatch.setattr(publish.videos, "db", lambda: DB())
    monkeypatch.setattr(publish, "publish", lambda vid: None)
    monkeypatch.setattr(publish, "upload", lambda vid, platforms: {
        "youtube": {"url": "https://youtube.com/shorts/abc"},
        "instagram": {"url": "https://www.instagram.com/reel/X/"},
        "facebook": {"error": "UNCONFIRMED: Facebook took the Reel", "unconfirmed": True, "url": pilot.where("facebook")}})
    import frameflow.webexport as we
    monkeypatch.setattr(we, "refresh", lambda *a, **k: "skipped")
    daily.post("d")
    assert state["state"] == "posted"
    assert "facebook" in json.loads(state["links"])
    assert "couldn't confirm" in sent[0] and "Not posted" not in sent[0]
