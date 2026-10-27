"""P15.6.7 acceptance replay: the 28 Oct make's round-2 notes through the scope-aware revise(), on a copy."""
import json, shutil, sys
from pathlib import Path

ROOT = Path.home() / "Talha_Khan/Code/frameflow"
sys.path.insert(0, str(ROOT))
from frameflow import direct

src = ROOT / "out/2026-10-27-highway-thieves-are-spoofing-gps-to"
copy = ROOT / "out/_replay-p1567"
brief = ROOT / "briefs/2026-10-27-highway-thieves-are-spoofing-gps-to.json"
shutil.rmtree(copy, ignore_errors=True)
shutil.copytree(src, copy, ignore=shutil.ignore_patterns("*.mp4", "frames", "*.wav"))
for f in copy.glob("review*-notes.txt"):   # the replay is round 1 of the copy
    f.rename(f.with_suffix(".orig"))
for f in copy.glob("**/*-usage.jsonl"):
    f.unlink()

fx = json.loads((ROOT / "tests/fixtures/notes-2026-10-28-round2.json").read_text())
lines = list(dict.fromkeys(fx["writer"] + fx["director"]))
fixes = [{"row": l.split(": ", 1)[0], "fix": l.split(": ", 1)[1]} for l in lines]
before = json.loads((copy / "writer/script.json").read_text())["beats"]
board_before = json.loads((copy / "director/storyboard.json").read_text())["scenes"]

direct.revise(str(brief), copy, {"fixes": fixes})

after = json.loads((copy / "writer/script.json").read_text())["beats"]
board_after = json.loads((copy / "director/storyboard.json").read_text())["scenes"]
print("beats", len(before), "->", len(after))
print("beats changed", [i for i, (a, b) in enumerate(zip(before, after)) if a != b])
print("scenes", len(board_before), "->", len(board_after),
      "changed", [i for i, (a, b) in enumerate(zip(board_before, board_after)) if a != b])
for f in copy.glob("**/*-usage.jsonl"):
    for l in f.read_text().splitlines():
        u = json.loads(l)
        print(f.name, u["purpose"], u["model"], u["input"] + u["cache_read"] + u["cache_create"] + u["output"], f"{u['seconds']}s")
print("writer notes:", (copy / "review1-writer-notes.txt").exists(), "| director notes tail:",
      (copy / "review1-director-notes.txt").read_text().splitlines()[-1][:120])
