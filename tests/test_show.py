"""The Daily Habit show: the topic card's tick buttons, and the rundown lints that guard every episode script."""
import copy

from frameflow import show, showdesk

DATA = {"stories": [
    {"story": 1, "lane": "AI", "headline": "A", "facts": [{"id": "s1f1", "text": "Revenue rose to $16.3 billion, 14 times more.", "source": "u"}]},
    {"story": 3, "lane": "Money", "headline": "B", "facts": [{"id": "s3f1", "text": "Paytm profit was Rs 225 crore, up 10 times.", "source": "u"}]},
]}
SEG = "The story here is short and simple, and it keeps going with plain words, because sixteen point three billion dollars is a lot of money, honestly."
SCRIPT = {
    "title": "Ep", "breaking": "x",
    "open": {"say": "Breaking: a giant AI lab opens its books, and a payments app suddenly prints money today.", "emotion": "excited"},
    "outro": {"say": "That's the show, from big books to tiny profits. See you tomorrow. Make learning a Habit.", "emotion": "smug"},
    "segments": [
        {"story": 1, "say": SEG, "witty": "honestly", "emotion": "surprised", "headline": "AI lab opens its books", "wall": "$16.3B",
         "facts": ["s1f1"], "graphic": {"type": "stat", "value": "$16.3B", "label": "revenue"}},
        {"story": 3, "say": SEG.replace("sixteen point three billion dollars", "two hundred twenty-five crore rupees"), "witty": "honestly",
         "emotion": "laughing", "headline": "Paytm prints money", "wall": "10X", "facts": ["s3f1"],
         "graphic": {"type": "versus", "left": {"label": "before", "value": "1x"}, "right": {"label": "now", "value": "10x"}}},
    ]}


def errs(script):
    show.cfg = lambda: {**showdesk.cfg(), "length": [0, 999]}   # length is measured on a full episode, not this pair
    return show.lint(script, DATA)


def test_clean_script_passes_except_variety():
    e = errs(SCRIPT)
    assert all("emotions too samey" in x for x in e), e   # two segments can't show four emotions


def test_digits_and_unverified_numbers_fail():
    s = copy.deepcopy(SCRIPT)
    s["segments"][0]["say"] = SEG.replace("sixteen point three", "16.3").replace("honestly", "honestly, ninety-nine")
    e = " | ".join(errs(s))
    assert "digits in say" in e and "not in the verified facts" in e and "99" in e


def test_graphic_numbers_checked_and_order_enforced():
    s = copy.deepcopy(SCRIPT)
    s["segments"][0]["graphic"]["value"] = "$77B"
    s["segments"].reverse()
    e = " | ".join(errs(s))
    assert "numbers shown" in e and "77" in e and "in that order" in e


def test_outro_signoff_and_witty_verbatim():
    s = copy.deepcopy(SCRIPT)
    s["outro"]["say"] = "That's the show, from big books to tiny profits. See you tomorrow, friends, same time, okay."
    s["segments"][1]["witty"] = "a pun that isn't there"
    e = " | ".join(errs(s))
    assert "Make learning a Habit" in e and "witty line is not in say" in e


def test_tick_buttons():
    rows = showdesk.buttons("2026-10-28", 15, [2, 5])
    flat = [b for r in rows for b in r]
    assert sum(1 for label, _ in flat if label.startswith("✅")) == 2
    assert ("✅ 2", "stog:2026-10-28:2") in flat
    assert any(data == "smake:2026-10-28" and "(2/" in label for label, data in flat)
    assert all(len(data.encode()) <= 64 for _, data in flat)
