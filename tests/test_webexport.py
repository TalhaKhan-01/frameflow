"""Studio snapshot: the PIN lock round-trips, a wrong PIN fails, and nothing private reaches the published folders."""
import json
import re
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag

from frameflow import webexport

ROOT = Path(__file__).resolve().parent.parent


def test_round_trip_and_wrong_pin():
    box = webexport.encrypt({"runs": [1, 2], "title": "₹ ok"}, "12345678", iterations=1000)
    assert webexport.decrypt(box, "12345678") == {"runs": [1, 2], "title": "₹ ok"}
    with pytest.raises(InvalidTag):
        webexport.decrypt(box, "00000000")


def test_scrub_drops_home_paths():
    assert webexport._scrub({"a": ["/home/someone/x/y/brief.json"]}) == {"a": ["brief.json"]}


def test_published_folders_hold_nothing_private():
    secrets_file = webexport.secrets.SECRETS_FILE
    values = []
    if secrets_file.exists():
        values = [line.split("=", 1)[1].strip() for line in secrets_file.read_text().splitlines()
                  if "=" in line and not line.lstrip().startswith("#") and len(line.split("=", 1)[1].strip()) >= 8]
    patterns = [r"AIza[0-9A-Za-z_-]{20,}", r"ghp_[0-9A-Za-z]{20,}", r"sk-ant-", r"EAA[0-9A-Za-z]{30,}",
                r"\d{9,10}:[A-Za-z0-9_-]{30,}", r"/home/talha", r"**********"]
    for folder in (ROOT / "web" / "public", ROOT / "betadoc" / "public", ROOT / "web" / "src", ROOT / "betadoc" / "src"):
        for f in folder.rglob("*"):
            if not f.is_file() or f.suffix in (".mp4", ".jpg", ".png", ".webp", ".woff2"):
                continue
            text = f.read_text(errors="ignore")
            for p in patterns:
                assert not re.search(p, text), f"{f}: matches {p}"
            for v in values:
                assert v not in text, f"{f}: holds a secrets.env value"


def test_live_snapshot_decrypts_with_the_pin():
    box = json.loads((ROOT / "web" / "public" / "data" / "studio.enc").read_text())
    data = webexport.decrypt(box, webexport.pin())
    assert data["runs"] and data["videos"] and data["phasedoc"]
    for v in data["videos"]:
        assert ("media" in v) == (v["status"] == "posted")
