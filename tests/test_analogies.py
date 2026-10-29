"""Analogy visuals (P25.2.4): the writer may only pick catalogue treatments and images, at most max_per_episode; the
render spec is timed to the witty line, after the real visuals, and dropped when its picture is missing."""
from frameflow import show

SAY = "An IIT Kanpur startup wants sensors a hundred times cheaper. Designed to see through smoke, unlike most startup pitches."
WITTY = "Designed to see through smoke, unlike most startup pitches."


def seg(story, an, witty=""):
    return {"story": story, "say": SAY, "witty": witty, "analogy": an}


def test_lint_catalogue_only_and_cap():
    ok = {"treatment": "compare", "left": "rice-grain", "right": "smartphone", "left_label": "chip", "right_label": "phone", "joiner": "="}
    assert show.lint_analogies({"segments": [seg(1, ok)]}) == []
    bad = show.lint_analogies({"segments": [seg(1, {"treatment": "photo", "image": "eiffel-tower", "caption": "x"}),
                                            seg(2, {"treatment": "stamp", "word": "THIS IS FAR TOO LONG"}),
                                            seg(3, {"treatment": "scale", "image": "ant"}),
                                            seg(4, {"treatment": "none"})]})
    assert any("image from the image list" in e for e in bad)
    assert any("stamp word" in e for e in bad) and any("scale needs big" in e for e in bad)
    four = {"segments": [seg(i, {"treatment": "stamp", "word": "OUCH"}) for i in range(4)]}
    assert any("4 analogies" in e for e in show.lint_analogies(four))


def test_gag_timed_to_the_witty_line_after_media():
    words = [{"w": w, "s": 10 + i * 0.4, "e": 10.3 + i * 0.4} for i, w in enumerate(SAY.split())]
    sg = {"start": 10.0, "dur": 9.0, "media": {"dur": 4.0}}
    pics = {"analogy": {"rice-grain": {"src": "a.jpg"}, "smartphone": {"src": "b.jpg"}}}
    g = seg(8, {"treatment": "compare", "left": "rice-grain", "right": "smartphone", "left_label": "chip", "right_label": "phone"}, WITTY)
    spec = show.gag_for(g, sg, words, pics)
    k = show.words(SAY[:SAY.index(WITTY)])
    assert spec["at"] == round(min(max(words[k]["s"] - 10.0, 4.3), 9.0 - 2.4 - 0.2), 2)
    assert spec["left"]["src"] == "a.jpg" and spec["dur"] == 2.4
    # missing picture: no half gag; stamp needs no picture
    assert show.gag_for(g, sg, words, {"analogy": {"rice-grain": {"src": "a.jpg"}}}) is None
    assert show.gag_for(seg(8, {"treatment": "stamp", "word": "OUCH"}), sg, words, {})["treatment"] == "stamp"
    assert show.gag_for(seg(8, {"treatment": "none"}), sg, words, pics) is None
