"""The studio board as data (P15): which desk each progress step belongs to, and a make's desk-by-desk summary.

Shared by the Studio web export (frameflow.webexport) and the local control panel (Code/frameflow-control), so both show
the same desks in the same order. Steps carry their desk in `detail.desk`; older steps are matched by name.
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKS = [("showrunner", "Showrunner"), ("researcher", "Researcher"), ("factcheck", "Fact-checker"), ("packaging", "Packaging"),
         ("writer", "Writer"), ("editor", "Script editor"), ("director", "Director"), ("narrator", "Narrator"),
         ("standards", "Standards"), ("artdirector", "Art director"), ("animatic", "Animatic"), ("screening", "Screening"),
         ("animator", "Render"), ("qc", "QC"), ("you", "You"), ("publisher", "Publisher"), ("analyst", "Analyst")]
BY_NAME = [("research brief", "researcher"), ("fact", "factcheck"), ("cover", "packaging"), ("card post", "packaging"),
           ("packaging", "packaging"), ("writer", "writer"), ("table read", "editor"), ("director", "director"),
           ("voice", "narrator"), ("caption timing", "narrator"), ("narrator", "narrator"), ("standards", "standards"),
           ("art direct", "artdirector"), ("animatic", "animatic"), ("screening", "screening"), ("review", "screening"),
           ("render frames", "animator"), ("sound mix", "animator"), ("build scenes", "animator"), ("qc", "qc"),
           ("automatic checks", "qc"), ("video card", "you"), ("post to", "publisher"), ("lessons", "analyst"),
           ("library", "analyst"), ("vault note", "analyst"), ("cleanup", "analyst"), ("showrunner", "showrunner"),
           ("change order", "showrunner")]


def desk_of(name, detail=None):
    d = (detail or {}).get("desk")
    if d:
        return d
    name = (name or "").lower()
    return next((k for key, k in BY_NAME if key in name), None)


def _ts(s):
    try:
        return datetime.fromisoformat(s).timestamp()
    except (TypeError, ValueError):
        return None


def make_summary(path, root_step="make"):
    """Desk-by-desk summary of the last `root_step` job in a progress file: per desk its final state, gate, score, time,
    the number of steps (fix rounds show as more than one), plus delivery renders and fix rounds for the whole make."""
    path = Path(path)
    if not path.exists():
        return None
    events = []
    for line in path.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    steps, roots = {}, []
    for e in events:
        if e.get("ev") == "start":
            steps[e["id"]] = {"name": e["step"], "parent": e.get("parent"), "detail": e.get("detail") or {}, "start": _ts(e["t"]),
                              "end": None, "status": "running", "info": {}}
            if e.get("parent") is None and e["step"] == root_step:
                roots.append(e["id"])
        elif e.get("ev") in ("end", "fail") and e.get("id") in steps:
            steps[e["id"]].update(end=_ts(e["t"]), status="done" if e["ev"] == "end" else "failed", info=e.get("info") or {})
    if not roots:
        return None
    root = roots[-1]

    def under(sid):
        while sid:
            if sid == root:
                return True
            sid = steps[sid]["parent"] if sid in steps else None
        return False

    mine = [s for sid, s in steps.items() if sid != root and under(sid)]
    parents = {s["parent"] for s in mine}
    desks = {}
    for sid, s in ((k, v) for k, v in steps.items() if k != root and under(k)):
        d = desk_of(s["name"], s["detail"])
        if not d:
            continue
        b = desks.setdefault(d, {"status": "done", "seconds": 0.0, "steps": 0, "gate": None, "score": None})
        if sid not in parents and s["start"]:
            b["seconds"] += (s["end"] or s["start"]) - s["start"]
        b["steps"] += 1
        if s["status"] != "done":
            b["status"] = s["status"]
        if "pass" in s["info"]:
            b["gate"] = bool(s["info"]["pass"])
            if "total" in s["info"]:
                b["score"] = f"{s['info']['total']}/{s['info'].get('max', '')}"
    rs = steps[root]
    return {"desks": [{"desk": k, "label": label, **desks[k], "seconds": round(desks[k]["seconds"], 1)} for k, label in DESKS if k in desks],
            "renders": sum(1 for s in mine if s["name"] == "render frames"),
            "fix_rounds": sum(1 for s in mine if s["name"].startswith(("text fix", "timing fix", "animatic fix"))),
            "minutes": round(((rs["end"] or datetime.now().timestamp()) - rs["start"]) / 60, 1) if rs["start"] else None,
            "status": rs["status"]}


def for_video(con, video_id):
    """The board of the make that produced a video (its run's day), or None for videos made before the board."""
    row = con.execute("SELECT day FROM runs WHERE video_id=? ORDER BY day DESC", (video_id,)).fetchone()
    return make_summary(ROOT / "logs" / f"progress-{row[0]}.jsonl") if row else None
