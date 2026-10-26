"""The Quality Bar every desk reads: research/quality-bar.json (P15 Studio board).

    python -m frameflow.bar show          the bar in force
    python -m frameflow.bar calibrate     re-measure the voice's words per second from recent videos, copy to the skills

One file, so no desk aims at a different target (before 26 Oct the numbers sat in qa.py, review.py and the profiles,
and the director planned scene timing at 3.3 words a second while the voice speaks about 2.9: too few drawn beats,
caught only after the render). The writer and director skills keep their own configs (they are generic tools), so
sync() copies the numbers they use into research/shorts-writer.json and research/shorts-director.json.
"""
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "research" / "quality-bar.json"
SKILL_KEYS = {   # skill config file -> {its key: (bar section, bar key)}
    "shorts-writer.json": {"words_per_second": ("speech", "words_per_second"), "max_rehook_gap": ("pacing", "max_rehook_gap")},
    "shorts-director.json": {"words_per_second": ("speech", "words_per_second"), "max_event_gap": ("pacing", "max_event_gap")},
}


def load():
    return json.loads(FILE.read_text())


def get(section, key):
    return load()[section][key]


def sync():
    """Copy the bar's numbers into the writer's and director's configs (only the keys they read)."""
    bar = load()
    changed = {}
    for name, keys in SKILL_KEYS.items():
        p = ROOT / "research" / name
        cfg = json.loads(p.read_text()) if p.exists() else {}
        for k, (sec, bk) in keys.items():
            if cfg.get(k) != bar[sec][bk]:
                cfg[k] = bar[sec][bk]
                changed[f"{name}:{k}"] = bar[sec][bk]
        p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    return changed


def measure(render_dir):
    """Words per second of one voiced video (pauses included), or None."""
    d = Path(render_dir)
    try:
        script = json.loads((d / "script.json").read_text())
        total = json.loads((d / "voice" / "durations.json").read_text())["total"]
    except (OSError, ValueError, KeyError):
        return None
    words = sum(len(l["say"].split()) for l in script.get("lines", []))
    return round(words / total, 3) if total and words else None


def calibrate(last=5):
    """Median words per second over the most recently voiced videos -> the bar -> the skills."""
    renders = sorted((p.parent.parent for p in ROOT.glob("out/*/render/voice/durations.json")),
                     key=lambda p: (p / "voice" / "durations.json").stat().st_mtime, reverse=True)
    rates = [(p.parent.name, measure(p)) for p in renders]
    rates = [(n, r) for n, r in rates if r][:last]
    if not rates:
        return {"changed": {}, "note": "no voiced videos yet"}
    bar = load()
    bar["speech"]["words_per_second"] = round(statistics.median(r for _, r in rates), 2)
    bar["speech"]["measured_from"] = [n for n, _ in rates]
    FILE.write_text(json.dumps(bar, ensure_ascii=False, indent=2) + "\n")
    return {"words_per_second": bar["speech"]["words_per_second"], "from": dict(rates), "changed": sync()}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    print(json.dumps(calibrate() if cmd == "calibrate" else load(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
