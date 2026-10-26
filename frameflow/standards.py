"""Standards desk (P15 Studio board): channel policy, checked in code before the animatic.

    python -m frameflow.standards <render-dir> [<brief.json>]     writes <render-dir>/standards.json; exit 0 when all pass

  labels    every invented reply (chat scene) carries an on-screen note such as "re-enactment", within its 30 characters
            (26 Oct: a 31-character note was reported as "missing" and the director never shortened it)
  licences  every image in the project's asset manifest has a source, licence, url and author
  numbers   every number drawn on screen is said in the script or stands in the brief's facts (no invented figures)
Failures come back as review-style fixes for the director (honesty, sources rows), in the same loop as the screening's.
AI disclosure on the platforms is the publisher's job (the Pilot turns the AI label on); the asset ledger's voice row
says the voice is generated.
"""
import json
import re
import sys
from pathlib import Path

NUM = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)*)\s*(%|x|k|m|bn|billion|million|crore|lakh)?", re.I)
UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                                      "sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
SCALE = {"hundred": 100, "thousand": 1000}


def spoken(text):
    """Numbers said in words: 'eighty-three point two' -> 83.2, 'three hundred and four' -> 304, 'thirty-six' -> 36."""
    toks = re.findall(r"[a-z]+|\d+(?:\.\d+)?|[^\sa-z\d]", text.lower().replace("-", " "))   # punctuation ends a number
    found, i = set(), 0
    while i < len(toks):
        if toks[i] not in UNITS and toks[i] not in TENS:
            i += 1
            continue
        total, cur = 0, 0
        while i < len(toks) and (toks[i] in UNITS or toks[i] in TENS or toks[i] in SCALE or (toks[i] == "and" and cur >= 100)):
            t = toks[i]
            if t in UNITS:
                cur += UNITS[t]
            elif t in TENS:
                cur += TENS[t]
            elif t in SCALE:
                cur = max(cur, 1) * SCALE[t]
                if t == "thousand":
                    total, cur = total + cur, 0
            i += 1
        n = str(total + cur)
        if i + 1 < len(toks) and toks[i] == "point" and toks[i + 1] in UNITS:   # decimals digit by digit
            i += 1
            dec = ""
            while i < len(toks) and toks[i] in UNITS and UNITS[toks[i]] < 10:
                dec += str(UNITS[toks[i]])
                i += 1
            n = f"{n}.{dec}"
        found.add(n)
    return found


def numbers(text):
    """Every number in a text as a plain digit string ('83.2', '304'), written in digits or in words."""
    text = str(text)
    out = {m.group(1).replace(",", "") for m in NUM.finditer(text)} | spoken(text)
    return {n.rstrip("0").rstrip(".") if "." in n else n for n in out}


def _strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for k, x in v.items():
            if k not in ("beats", "cues", "at", "until") and not k.startswith("_"):
                yield from _strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x)


def run(render_dir, brief_path=None):
    out = Path(render_dir)
    plan = json.loads((out / "plan.json").read_text())
    checks = {}

    def check(name, problems, row):
        checks[name] = {"pass": not problems, "problems": problems, "row": row}

    labels = []
    for i, s in enumerate(plan["scenes"]):
        d = s.get("data", {})
        if s["type"] == "chat" and d.get("reply"):
            note = d.get("note")
            if not (isinstance(note, str) and note.strip()):
                labels.append(f"scene {i} (chat): an invented reply needs an on-screen note such as \"re-enactment\"")
            elif len(note) > 30:
                labels.append(f"scene {i} (chat): the note \"{note}\" is {len(note)} characters; at most 30 (e.g. \"re-enactment\")")
    check("labels", labels, "honesty")

    lic = []
    manifest = out / "project" / "assets-manifest.json"
    for r in json.loads(manifest.read_text()) if manifest.exists() else []:
        missing = [k for k in ("source", "licence", "url", "author") if not str(r.get(k, "")).strip()]
        if missing:
            lic.append(f"{r.get('asset') or r.get('file') or '?'}: no {', '.join(missing)}")
    check("licences", lic, "sources")

    said = " ".join(l.get("say", "") for s in plan["scenes"] for l in s.get("lines", [{"say": s.get("say", "")}]))
    allowed = numbers(said)
    if brief_path and Path(brief_path).exists():
        allowed |= numbers(" ".join(f.get("text", "") for f in json.loads(Path(brief_path).read_text()).get("facts", [])))
    nums = []
    for i, s in enumerate(plan["scenes"]):
        if s["type"] == "endcard":
            continue
        shown = set()
        for text in _strings(s.get("data", {})):
            shown |= numbers(text)
        extra = sorted(n for n in shown if n not in allowed and n not in ("0", "1") and not (len(n) == 4 and n.startswith("20")))   # years are dates
        if extra:
            nums.append(f"scene {i} ({s['type']}): on-screen number(s) {', '.join(extra)} are not said in the script nor in the brief's facts")
    check("numbers", nums, "sources")

    r = {"pass": all(c["pass"] for c in checks.values()), "checks": checks}
    (out / "standards.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r


def fixes(r):
    return [{"row": c["row"], "fix": f"standards '{k}': {p}"} for k, c in r["checks"].items() for p in c["problems"]]


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: python -m frameflow.standards <render-dir> [<brief.json>]")
    r = run(*sys.argv[1:])
    for k, c in r["checks"].items():
        print(f"{'PASS' if c['pass'] else 'FAIL'}  {k}" + "".join(f"\n      - {p}" for p in c["problems"]))
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
