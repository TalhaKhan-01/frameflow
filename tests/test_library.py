"""Asset library guards: matching needs real topic overlap, recently used assets go last and are flagged, old facts are flagged."""
import datetime as dt
import json

from frameflow import library


def setup_lib(tmp_path, monkeypatch, rows):
    monkeypatch.setattr(library, "LIB", tmp_path)
    for kind, items in rows.items():
        library.save(kind, items)


def test_keys_keep_names_and_drop_stopwords():
    k = library.keys("Microsoft built an AI tool that diagnoses like a doctor")
    assert "microsoft" in k and "doctor" in k and "that" not in k and "an" not in k


def test_suggest_needs_overlap(tmp_path, monkeypatch):
    setup_lib(tmp_path, monkeypatch, {"analogies": [{"id": "a1", "text": "PHP is the cook", "keys": ["php", "cook", "server"], "used": []}]})
    assert library.suggest("A new PHP server bug", "analogies")
    assert not library.suggest("Bitcoin price falls", "analogies")


def test_recently_used_goes_last_and_is_flagged(tmp_path, monkeypatch):
    today = dt.date.today().isoformat()
    setup_lib(tmp_path, monkeypatch, {"hooks": [
        {"id": "h1", "text": "old favourite", "keys": ["php", "server", "bug"], "used": [today], "review": 20},
        {"id": "h2", "text": "fresh one", "keys": ["php", "server", "bug"], "used": [], "review": 15}]})
    got = library.suggest("php server bug", "hooks")
    assert got[0][0]["id"] == "h2" and got[1] == (got[1][0], True)


def test_old_facts_are_flagged_for_recheck(tmp_path, monkeypatch):
    old = (dt.date.today() - dt.timedelta(days=90)).isoformat()
    setup_lib(tmp_path, monkeypatch, {"knowledge": [
        {"id": "k1", "text": "PHP runs 69% of sites", "source": "https://w3techs.com", "keys": ["php", "sites", "runs"], "verified": old, "used": []}]})
    facts = library.known_facts("php sites")
    assert facts and "re-check" in facts[0]
