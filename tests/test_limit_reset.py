import datetime as dt

from frameflow import daily


def test_limit_reset_reads_the_session_and_the_dated_weekly_message(monkeypatch):
    monkeypatch.setattr(daily, "now", lambda: dt.datetime(2026, 10, 31, 14, 1))
    assert daily.limit_reset("You've hit your session limit · resets 8:20pm (Asia/Kolkata)") == "2026-10-31T20:22:00"
    assert daily.limit_reset("You've hit your weekly limit · resets Nov 1, 3:30pm (Asia/Kolkata)") == "2026-11-01T15:32:00"
    assert daily.limit_reset("You've hit your weekly limit · resets 3:30pm (Asia/Kolkata)") == "2026-10-31T15:32:00"
    assert daily.limit_reset("some other error") is None


def test_a_scout_waiting_on_the_limit_restarts_as_scouting(monkeypatch):
    src = open(daily.__file__).read()
    assert '{"post": "posting", "scout": "scouting"}.get(m.group(2), "making")' in src


def test_a_revise_that_failed_at_the_card_only_resumes_at_the_card():
    log = "x video card sent (approvable: True)\ny show revise done\nz send video card failed: network unreachable"
    assert daily.card_pending({"log": log})
    assert not daily.card_pending({"log": log + "\nw video card sent (approvable: True)"})
    assert not daily.card_pending({"log": "a spawned revise"})
