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


def test_phrase_chunks_keep_numbers_and_never_end_on_a_joining_word():
    from frameflow.show import phrase_chunks, _JOIN
    for text in ["Binance lost six point three billion dollars in one hack, and the FBI says North Korea did it.",
                 "Apple retakes the most valuable company crown from Nvidia this week",
                 "existing staff on AI work, becoming part of the job"]:
        ws = text.split()
        ch = phrase_chunks(ws)
        assert sorted(i for c in ch for i in c) == list(range(len(ws)))   # every word once, in order
        lines = [" ".join(ws[i] for i in c) for c in ch]
        assert all(ws[c[-1]].lower().strip(",.") not in _JOIN for c in ch), lines
        assert all(len(c) > 1 or ws[c[0]].endswith((".", "?", "!", ",")) for c in ch), lines
    ws = "Binance lost six point three billion dollars in one hack,".split()
    assert any(" ".join(ws[i] for i in c) == "six point three billion dollars" for c in phrase_chunks(ws))


def test_set_and_look_are_one_config_value_each():
    """P24.4.1 / P24.4.3: research/show.json names the default set and Habit look; the template has every set and look,
    and the director passes the config through (renders of riso, night and pixel: spikes/show_test_render.py --set/--look)."""
    import json, re
    from pathlib import Path
    from frameflow import show
    root = Path(show.__file__).resolve().parent.parent
    c = json.loads((root / "research" / "show.json").read_text())
    assert (c["set"], c["look"]) == ("paper", "puppet")
    js = (root / "scenes" / "_shared" / "show" / "show.js").read_text()
    for s in ("riso", "paper", "night"):
        assert re.search(rf"\b{s}\s*:", js), s
    assert re.search(r"RIGS\s*=\s*\{\s*pixel:\s*rigPixel,\s*puppet:\s*rigPuppet\s*\}", js)
    src = Path(show.__file__).read_text()
    assert '"set": cfg()["set"], "look": cfg()["look"]' in src


def test_screening_bar_is_judged_on_the_mean_of_two_runs():
    a = {"rows": {"hook": 2, "look": 1, "pace": 2}, "fixes": ["x"]}
    b = {"rows": {"hook": 1, "look": 1, "pace": 2}, "fixes": ["x", "y"]}
    m = show.mean_screening([a, b], 0.8)
    assert m["rows"] == {"hook": 1.5, "look": 1.0, "pace": 2.0} and m["total"] == 4.5 and m["max"] == 6
    assert m["fixes"] == ["x", "y"] and len(m["runs"]) == 2
    assert not m["pass"]                                   # 4.5 < 0.8 * 6
    assert show.mean_screening([a, a], 0.8)["pass"]        # 5 >= 4.8, every row >= 1


def test_banner_follows_the_open_story():
    from frameflow import hookpick
    sc = {"open": {"say": "Breaking: Your next iPhone could cost more, because Apple won't rule out price hikes as memory costs climb."},
          "breaking": "INDIA NO.1 FOR CHATGPT, SAYS OPENAI + A $115B DEAL",
          "segments": [{"story": 1, "headline": "India tops ChatGPT, says OpenAI", "wall": "INDIA: CHATGPT'S BIGGEST MARKET"},
                       {"story": 3, "headline": "Apple's inventory jumps 154.3%", "wall": "APPLE INVENTORY, $ BILLION memory costs"}]}
    assert hookpick.fit_banner(sc)["breaking"] == "Apple's inventory jumps 154.3%"
    ok = dict(sc, breaking="APPLE WARNS ON IPHONE PRICES")
    assert hookpick.fit_banner(ok)["breaking"] == "APPLE WARNS ON IPHONE PRICES"


def test_pages_never_include_a_stale_dated_page():
    s = {"source_name": "Inc42", "url": "https://inc42.com/buzz/india-becomes-chatgpts-largest-market/",
         "facts": [{"source": "https://www.techcrunch.com/2026/02/15/india-has-100m-weekly-active-chatgpt-users/"},
                   {"source": "https://inc42.com/buzz/india-becomes-chatgpts-largest-market/"},
                   {"source": "https://example.com/2026/11/03/fresh-take/"}]}
    pages = show.pages_for(s, day="2026-11-04")
    assert pages == ["https://inc42.com/buzz/india-becomes-chatgpts-largest-market/", "https://example.com/2026/11/03/fresh-take/"]


def test_laugh_tags_are_not_words_and_at_most_one():
    assert show.words("That's one way to pay rent [chuckle] today.") == 7
    assert show.TAG.sub(" ", "rent [laugh] now").split() == ["rent", "now"]


def test_director_fills_every_hold_over_two_and_a_half_seconds():
    c = {"breakingAt": 0.5, "stingAt": 4.0, "endAt": 30.0, "segments": [
        {"topic": 1, "start": 6.0, "dur": 10.0, "shot": "split", "shots": [[0.0, "split"], [5.5, "pip"]],
         "media": {"shot": {"src": "x"}, "dur": 4.5}, "g": {"type": "headline"}}]}
    assert show.event_gaps(dict(c, endAt=16.0))
    show.fill_beats(c["segments"][0], c)
    assert not show.event_gaps(dict(c, endAt=16.0))
    sh = c["segments"][0]["shots"]
    assert all(a[1] != b[1] for a, b in zip(sh, sh[1:]))   # every listed cut changes the framing


def test_voice_respells_names_but_captions_keep_them():
    lex = {"Anthropic": "an-THROP-ik", "Lumentum": "loo-MEN-tum"}
    assert show.pronounce("Anthropic's deal with Lumentum.", lex) == "an-THROP-ik's deal with loo-MEN-tum."
    assert show.pronounce("Anthropically speaking", lex) == "Anthropically speaking"


def test_word_error_reads_numbers_and_split_names_as_said():
    from frameflow import captions
    said = "Marvell pays one hundred fifteen billion dollars, up one hundred fifty-four point three percent, says ChatGPT."
    heard = "Marvell pays $115 billion, up 154.3%, says chat GPT."
    assert captions.wer(said, heard) == 0
