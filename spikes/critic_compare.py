"""P25.7.1 acceptance: the video-critic skill scores a made episode within 1 point of the old desks (show.py's own
table read and screening, as stored in that episode's review.json). The new "seen_heard" row is left out of the
comparison (the old desks had no such row) and reported on its own.

    uv run python spikes/critic_compare.py 2026-10-29-daily-habit-ep2
"""
import json
import sys

from frameflow import show


def main():
    ep = show.OUT / sys.argv[1]
    old = json.loads((ep / "review.json").read_text())
    script, data = json.loads((ep / "script.json").read_text()), json.loads((ep / "research.json").read_text())
    c = json.loads((ep / "show-plan.json").read_text())
    times = [c["breakingAt"] + 1.0, c["stingAt"] + 0.7] + [s["start"] + s["dur"] * f for s in c["segments"] if s.get("topic") for f in (0.3, 0.8)] + [c["endAt"] + 1.0]
    tr = show.table_read(script, data)
    sc = show.screening(ep / "contact.png", times, script)
    shared = [k for k in sc["rows"] if k != "seen_heard"]
    res = {"episode": ep.name,
           "text": {"old": old["table_read"]["total"], "new": tr["total"], "diff": round(tr["total"] - old["table_read"]["total"], 2), "rows": tr["rows"]},
           "stills": {"old": old["screening"]["total"], "new_shared_rows": round(sum(sc["rows"][k] for k in shared), 2),
                      "seen_heard": sc["rows"].get("seen_heard"), "rows": sc["rows"]}}
    res["stills"]["diff"] = round(res["stills"]["new_shared_rows"] - res["stills"]["old"], 2)
    res["within_1"] = abs(res["text"]["diff"]) <= 1 and abs(res["stills"]["diff"]) <= 1
    (ep / "critic-compare.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
