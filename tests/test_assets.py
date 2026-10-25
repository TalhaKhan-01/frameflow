"""Stock media guards: only CC0 / public domain / CC BY pass, NASA's spaced links get quoted, Unsplash without a key is an error row, not a crash."""
from frameflow import assets


def test_licence_filter_keeps_free_and_drops_sharealike():
    assert assets.licence_ok("CC BY 4.0") and assets.licence_ok("Public domain") and assets.licence_ok("CC0")
    assert not assets.licence_ok("CC BY-SA 4.0")
    assert not assets.licence_ok("CC BY-NC 2.0") and not assets.licence_ok("CC BY-ND 3.0")
    assert not assets.licence_ok("GFDL")


def test_nasa_links_quoted_and_https():
    u = assets.quoted("http://images-assets.nasa.gov/video/Mars 2020/Mars 2020~medium.mp4")
    assert u == "https://images-assets.nasa.gov/video/Mars%202020/Mars%202020~medium.mp4"


def test_unsplash_without_key_is_reported(monkeypatch):
    monkeypatch.setattr(assets.secrets, "SECRETS_FILE", assets.ROOT / "no-such-secrets.env")
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    monkeypatch.setattr(assets, "SOURCES", {"unsplash": assets.unsplash})
    res, errs = assets.search("robot")
    assert res == [] and "UNSPLASH_ACCESS_KEY" in errs["unsplash"]
