"""Topic memory on the show's topic card (P25.1.1): repeats leave the list, updates are labelled, a failed memory
call still sends the card with a warning. Model calls and Telegram are stubbed."""
import datetime as dt

from frameflow import daily, ideas, showdesk


def setup(monkeypatch, verdicts):
    now = daily.now()
    rows = [{"id": i, "source": "s", "title": f"Story {i} - Outlet", "url": f"https://x/{i}", "summary": "", "angle": "",
             "hook": "", "score": 9, "lane": "tech", "published": now.isoformat()} for i in range(1, 7)]

    class Q:
        def execute(self, *a):
            return rows
    monkeypatch.setattr(ideas, "collect", lambda: None)
    monkeypatch.setattr(ideas, "rank", lambda **k: None)
    monkeypatch.setattr(ideas, "db", lambda: Q())
    monkeypatch.setattr(ideas, "published_at", lambda p: dt.datetime.now(dt.timezone.utc))
    monkeypatch.setattr(showdesk, "used_urls", lambda: set())
    if isinstance(verdicts, Exception):
        def boom(rows, day):
            raise verdicts
        monkeypatch.setattr(showdesk, "memory", boom)
    else:
        monkeypatch.setattr(showdesk, "memory", lambda rows, day: verdicts)
    seen = {}

    def rank(prompt, *a, **k):
        seen["prompt"] = prompt
        ids = [int(line.split(" | ")[0]) for line in prompt.splitlines() if " | " in line and line.split(" | ")[0].isdigit()]
        return {"stories": [{"id": i, "virality": 90 - i, "headline": f"H{i}", "why": "w", "pun": "p", "lane": "Tech"} for i in ids]}
    monkeypatch.setattr(showdesk.llm, "call", rank)
    return seen


def test_repeats_removed_and_updates_labelled(monkeypatch):
    cov = {"day": "2026-10-28", "episode": 1, "headline": "Anthropic files for IPO"}
    seen = setup(monkeypatch, {"2": {"verdict": "repeat", "covered": cov, "new_info": ""},
                               "3": {"verdict": "update", "covered": cov, "new_info": "IT stocks fell"}})
    cands, removed = showdesk.candidates(n=4, day="2026-10-30")
    assert removed == 1
    assert all(c["idea"] != 2 for c in cands) and "Story 2" not in seen["prompt"]
    up = [c for c in cands if c["idea"] == 3][0]
    assert up["headline"].startswith("Update: ") and up["update"]["new_info"] == "IT stocks fell"
    assert "UPDATE of 'Anthropic files for IPO'" in seen["prompt"]


def test_failed_memory_still_gives_a_card(monkeypatch):
    setup(monkeypatch, RuntimeError("model call failed"))
    cands, removed = showdesk.candidates(n=4, day="2026-10-30")
    assert removed is None and len(cands) == 4
