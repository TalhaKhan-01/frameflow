"""The cover becomes the thumbnail: its numbers must be numbers the script says (it once showed 80% vs 20% for 83.2% vs 36.1%)."""
from frameflow import cover

SCRIPT = "It scored eighty-three point two percent, against thirty-six point one, on three hundred and four cases, back in twenty twelve."


def test_spoken_numbers_read_decimals_hundreds_and_years():
    said = cover.spoken_numbers(SCRIPT)
    assert {"83.2", "36.1", "304", "2012"} <= said


def test_wrong_cover_numbers_are_caught():
    assert cover.bad_numbers({"title": ["AI BEAT DOCTORS"], "stat": "80% vs 20%"}, SCRIPT) == ["80", "20"]


def test_right_cover_numbers_pass():
    assert cover.bad_numbers({"title": ["SINCE 2012"], "stat": "83.2% vs 36.1%, 304 cases"}, SCRIPT) == []
