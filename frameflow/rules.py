"""Automatic checks for the machine-checkable Script Rules (vault/Docs/Script Rules.md).

    check(plan) -> list of failures like "R4: scenes[2].say has 23 words (max 18)"

R1 hook carries a stake · R2 hook spoken at 0 s · R4 short lines · R5 length 30-50 s · R7 numbers shown ·
R8 claims sourced (scene_plan) · R10 payoff before 85% · R11 ends on a question or share prompt ·
R13 digits spelled for the voice · R14 title length and stake. R3, R6, R9, R12 are judged in review.
"""
import re

from frameflow import scene_plan

STAKE = re.compile(r"\d|₹|\$|%|\bvs\.?\b|\bversus\b|\bmore than\b|\bless than\b|\bcheaper\b|\bfaster\b|\bbigger\b|"
                   r"\bmore\b|\bless\b|\bfirst\b|\bonly\b|\brecord\b|\bbiggest\b|\bjust\b|\bnow\b|\bnew\b|\bnever\b|"
                   r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|lakh|crore|million|billion|trillion)\b", re.I)
NUMBER_WORDS = re.compile(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|"
                          r"sixty|seventy|eighty|ninety|hundred|thousand|lakh|crore|million|billion|trillion|percent)\b", re.I)
SHARE = re.compile(r"\?\s*$|\bsend this\b|\bshare this\b|\btag (?:a|someone|your)\b|\bcomment\b|\btell me\b|\bwould you\b|\bwhich\b", re.I)


def data_text(scene):
    d = scene.get("data", {})
    return " ".join(str(v) for v in _flatten(d))


def _flatten(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from _flatten(v)
    elif isinstance(x, list):
        for v in x:
            yield from _flatten(v)
    else:
        yield x


def check(plan):
    fails = list(scene_plan.validate(plan))           # includes R8 (claims need sources)
    scenes = plan.get("scenes") or []
    if not scenes:
        return fails
    says = [s.get("say", "") or "" for s in scenes]
    if not says[0].strip():
        fails.append("R2: the first scene has no spoken line (the hook must be spoken at 0 s)")
    elif not STAKE.search(says[0]):
        fails.append("R1: the hook has no concrete stake (number, comparison or claim word)")
    for i, line in enumerate(says):
        n = len(line.split())
        if n > 18:
            fails.append(f"R4: scenes[{i}].say has {n} words (max 18)")
        if re.search(r"\d", line):
            fails.append(f"R13: scenes[{i}].say contains digits; spell numbers for the voice")
        if NUMBER_WORDS.search(line) and not re.search(r"\d", data_text(scenes[i])) and scenes[i]["type"] != "headline-reveal":
            fails.append(f"R7: scenes[{i}] says a number but shows none on screen")
    total = scene_plan.total_seconds(plan)
    if not 30 <= total <= 50:
        fails.append(f"R5: planned length {total:.1f} s (want 30-50 s)")
    payoff = [i for i, s in enumerate(scenes) if s.get("payoff")]
    if not payoff:
        fails.append("R10: no scene is marked payoff: true")
    else:
        start = sum(scene_plan.scene_seconds(s) + scene_plan.PAD for s in scenes[:payoff[0]])
        if start > 0.85 * total:
            fails.append(f"R10: payoff starts at {start:.1f} s, after 85% of {total:.1f} s")
    if not SHARE.search(says[-1]):
        fails.append("R11: the last line is not a question or share prompt")
    title = plan.get("title", "")
    if len(title) > 60:
        fails.append(f"R14: title has {len(title)} characters (max 60)")
    if not STAKE.search(title):
        fails.append("R14: title carries no stake (number or comparison)")
    return fails
