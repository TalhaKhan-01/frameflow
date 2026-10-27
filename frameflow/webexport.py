"""Snapshot for the Studio web app (web/) and the betadoc's live numbers (betadoc/).

    frameflow web export      write web/public/data/studio.enc (+ media) and betadoc/public/live.json (+ media)
    frameflow web refresh     export, then commit + push only web/public and betadoc/public
    frameflow web pin         print where the PIN lives (never the PIN itself)
    frameflow web open|lock   switch the Studio between open (no PIN) and PIN-locked, then export

Access lives in web/access.json ({"open": true|false}, tracked in git so the state is visible and reversible).
Open: the snapshot is published as plain data/studio.json and the page shows it straight away.
Locked: the snapshot is AES-GCM encrypted into data/studio.enc under a key derived from FRAMEFLOW_WEB_PIN
(PBKDF2-SHA256); the page asks for the PIN and decrypts in the browser. Only one of the two files exists at a time.
Media is copied only for items already posted in public. Paths, tokens and chat ids never leave the machine.
"""
import base64
import json
import os
import re
import secrets as pysecrets
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from . import boardview, secrets

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "frameflow.db"
PLAN_DB = ROOT / "phasedoc" / "plan.db"
WEB = ROOT / "web" / "public"
ACCESS = ROOT / "web" / "access.json"
BETA = ROOT / "betadoc" / "public"
ITERATIONS = 600_000
LANES = {"ai-news": "AI", "global-tech": "Tech", "india-tech": "India tech", "how-tech-works": "How tech works",
         "dev-tools": "Dev tools", "ai-money": "Money"}
CHANNELS = {"youtube": "https://www.youtube.com/channel/UCrcF7Q5J4kEENdJuA8BPQxQ",
            "instagram": "https://www.instagram.com/madebythirdspace/"}


def _json(text, default=None):
    try:
        return json.loads(text) if text else default
    except (TypeError, ValueError):
        return default


def _read(path, default=None):
    p = Path(path)
    return _json(p.read_text(), default) if p.exists() else default


def _jsonl(path):
    p = Path(path)
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _out_dir(row):
    d = Path(row["out_dir"] or "")
    return d if d.name == "render" else d / "render"


def _scrub(obj):
    """Drop absolute paths from strings (keep the file name)."""
    if isinstance(obj, str):
        return re.sub(r"/home/[^\s\"']+/([^/\s\"']+)", r"\1", obj)
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items()}
    return obj


def _jpg(src, dst, width):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", f"scale={width}:-2", "-q:v", "3", str(dst)],
                   check=True)


def _copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, dst)


def _media(render, slug, roots):
    """Posted video: 720p preview + cover (jpg) into each root's media/<slug>/. Returns relative urls."""
    urls = {}
    for root in roots:
        if (render / "preview-720.mp4").exists():
            _copy(render / "preview-720.mp4", root / "media" / slug / "preview.mp4")
            urls["video"] = f"media/{slug}/preview.mp4"
        if (render / "cover.png").exists():
            _jpg(render / "cover.png", root / "media" / slug / "cover.jpg", 720)
            urls["cover"] = f"media/{slug}/cover.jpg"
        if (render / "keyframes.jpg").exists():
            _jpg(render / "keyframes.jpg", root / "media" / slug / "keyframes.jpg", 1600)
            urls["keyframes"] = f"media/{slug}/keyframes.jpg"
    return urls


def _slug(video_id):
    return re.sub(r"[^a-z0-9-]", "", video_id.lower())[:60]


def videos(con):
    out = []
    for r in con.execute("SELECT * FROM videos ORDER BY created_at DESC"):
        render = _out_dir(r)
        posted = r["status"] == "posted"
        qa = _read(render / "qa.json", {})
        review = _read(render / "review.json", {})
        report = _read(render / "report.json", {})
        pub = _read(render / "publish.json", {})
        script = _read(render / "script.json", {})
        v = {"id": r["id"], "title": r["title"], "lane": LANES.get(r["lane"], r["lane"]), "status": r["status"],
             "created": r["created_at"], "review_total": r["review_total"], "review_pass": bool(r["review_pass"]),
             "qa_pass": bool(r["qa_pass"]),
             "gates": {k: g for k, g in (qa.get("gates") or {}).items()}, "warnings": qa.get("warnings", []),
             "scores": review.get("scores", {}), "fixes": review.get("fixes", []),
             "rounds": len(list(render.glob("review-round*.json"))) + (1 if review else 0),
             "seconds": report.get("seconds"), "lufs": report.get("lufs"), "wpm": report.get("wpm"),
             "words": report.get("words"), "voice": report.get("voice_engine"),
             "links": {k: u for k, u in (("youtube", r["youtube_url"]), ("instagram", r["instagram_url"])) if u},
             "review_max": review.get("max"), "board": boardview.for_video(con, r["id"]),
             "timeline": boardview.timeline_for_video(con, r["id"]),
             "animatic_total": _read(render / "animatic-review.json", {}).get("total")}
        if posted:
            v["yt_title"] = pub.get("yt_title")
            v["script"] = [line.get("say") for line in script.get("lines", []) if line.get("say")]
            v["media"] = _media(render, _slug(r["id"]), [WEB])
        out.append(v)
    return out


def runs(con):
    out = []
    for r in con.execute("SELECT * FROM runs ORDER BY day DESC"):
        opts = (_json(r["options"], {}) or {}).get("list", [])
        story = _json(r["story"], {}) or {}
        links = _json(r["links"], {}) or {}
        out.append({"day": r["day"], "lane": LANES.get(r["lane"], r["lane"]), "state": r["state"],
                    "options": [{"title": re.sub(r"\s+-\s+[^-]+$", "", o.get("title", "")), "score": o.get("score"),
                                 "hook": o.get("hook")} for o in opts],
                    "pick": r["pick"], "story": story.get("title") if isinstance(story, dict) else None,
                    "video_id": r["video_id"], "revisions": r["revisions"], "approved_at": r["approved_at"],
                    "post_at": r["post_at"], "posted_at": r["posted_at"], "links": links,
                    "created": r["created_at"], "updated": r["updated_at"]})
    return out


def cards(con):
    out = []
    for r in con.execute("SELECT * FROM card_runs ORDER BY created_at DESC"):
        folder = ROOT / "out" / "cards" / r["id"]
        deck = _read(folder / "deck.json", {})
        c = {"id": r["id"], "state": r["state"], "day": r["day"], "post_at": r["post_at"],
             "title": deck.get("title") or (_json(r["chosen"], {}) or {}).get("title"),
             "slides_text": [{"type": s.get("type"), "heading": s.get("heading"), "stat": s.get("stat"),
                              "body": s.get("body"), "source": s.get("source")} for s in deck.get("slides", [])],
             "links": _json(r["links"], {}) or {}, "created": r["created_at"]}
        if r["state"] == "posted":
            slug = _slug(r["id"])
            c["slides"] = []
            for png in sorted(folder.glob("slide-*.png")):
                _jpg(png, WEB / "media" / slug / (png.stem + ".jpg"), 720)
                c["slides"].append(f"media/{slug}/{png.stem}.jpg")
            if (folder / "ig.txt").exists():
                c["caption"] = (folder / "ig.txt").read_text().strip()
        out.append(c)
    return out


def library():
    a = ROOT / "research" / "assets"
    know, hooks = _jsonl(a / "knowledge.jsonl"), _jsonl(a / "hooks.jsonl")
    anal, scenes = _jsonl(a / "analogies.jsonl"), _jsonl(a / "scenes.jsonl")
    return {"counts": {"knowledge": len(know), "hooks": len(hooks), "analogies": len(anal), "scenes": len(scenes)},
            "knowledge": [{"text": k.get("text"), "source": k.get("source"), "verified": k.get("verified")} for k in know],
            "hooks": sorted([{"text": h.get("text"), "family": h.get("family"), "score": h.get("score")} for h in hooks],
                            key=lambda h: -(h["score"] or 0)),
            "analogies": [{"text": x.get("text"), "from": x.get("from")} for x in anal],
            "scenes": [{"template": s.get("template"), "metaphor": s.get("metaphor"), "text": s.get("world"),
                        "why": s.get("why"), "from": s.get("from")} for s in scenes]}


def lessons():
    return [{"id": x.get("id"), "area": x.get("area"), "text": x.get("text"), "source": x.get("source"),
             "status": x.get("status"), "seen": x.get("seen"), "helped": x.get("helped"), "hurt": x.get("hurt"),
             "updated": x.get("updated")} for x in _jsonl(ROOT / "research" / "lessons.jsonl")]


def usage():
    by_day = {}
    for u in _jsonl(ROOT / "data" / "llm-usage.jsonl"):
        d = by_day.setdefault(u["ts"][:10], {"calls": 0, "tokens": 0, "seconds": 0.0})
        d["calls"] += 1
        d["tokens"] += sum(u.get(k) or 0 for k in ("input", "cache_create", "output"))
        d["seconds"] += u.get("seconds") or 0
    return [{"day": k, **v} for k, v in sorted(by_day.items())]


def phasedoc():
    con = sqlite3.connect(f"file:{PLAN_DB}?mode=ro", uri=True)
    rows = con.execute("SELECT id, parent, title, status FROM tasks").fetchall()
    parents = {p for _, p, _, _ in rows}
    top = {i: t for i, p, t, _ in rows if not p}
    def phase(i):
        return i.split(".")[0]
    out = {k: {"id": k, "title": t, "done": 0, "partial": 0, "open": 0, "total": 0} for k, t in top.items()}
    for i, _, _, s in rows:
        if i in parents or i in top or s == "cancelled":
            continue
        ph = out[phase(i)]
        ph["total"] += 1
        ph[s if s in ("done", "partial") else "open"] += 1
    return sorted(out.values(), key=lambda x: int(x["id"][1:]))


def snapshot():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    ideas = con.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
    data = {"generated": datetime.now().isoformat(timespec="seconds"), "channels": CHANNELS,
            "ideas": ideas, "runs": runs(con), "videos": videos(con), "cards": cards(con),
            "lessons": lessons(), "library": library(), "usage": usage(), "phasedoc": phasedoc()}
    made = [v for v in data["videos"] if v.get("board")]   # videos made by the studio board (P15)
    data["board"] = {"desks": [{"desk": k, "label": l} for k, l in boardview.DESKS], "videos": len(made),
                     "one_render": sum(1 for v in made if v["board"]["renders"] == 1),
                     "first_render_passed": sum(1 for v in made if v["board"]["renders"] == 1 and v["review_pass"] and v["qa_pass"]),
                     "animatic_within_1": sum(1 for v in made if v.get("animatic_total") is not None and v["review_total"] is not None
                                              and abs(v["animatic_total"] - v["review_total"]) <= 1)}
    return _scrub(data)


def live(data):
    """Public numbers for the betadoc hero (no internals)."""
    posted = [v for v in data["videos"] if v["status"] == "posted"]
    latest = posted[0] if posted else None
    media = {}
    if latest:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM videos WHERE id=?", (latest["id"],)).fetchone()
        media = _media(_out_dir(row), "latest", [BETA])
    pd = data["phasedoc"]
    gates = latest["gates"] if latest else {}
    return {"generated": data["generated"], "ideas": data["ideas"], "videos_made": len(data["videos"]),
            "videos_posted": len(posted), "card_posts": sum(c["state"] == "posted" for c in data["cards"]),
            "lessons": sum(x["status"] == "active" for x in data["lessons"]),
            "library": sum(data["library"]["counts"].values()),
            "leaves_done": sum(p["done"] for p in pd), "leaves_partial": sum(p["partial"] for p in pd),
            "leaves_total": sum(p["total"] for p in pd),
            "today": next(({"day": r["day"], "lane": r["lane"], "state": r["state"]} for r in data["runs"]), None),
            "latest": latest and {"title": latest["yt_title"] or latest["title"], "lane": latest["lane"],
                                  "seconds": latest["seconds"], "lufs": latest["lufs"], "wpm": latest["wpm"],
                                  "review_total": latest["review_total"], "links": latest["links"],
                                  "gates": {k: g["pass"] for k, g in gates.items()}, "media": media},
            "channels": data["channels"],
            "board": {**{k: v for k, v in (data.get("board") or {}).items() if k != "desks"},
                      "latest": next(({"title": v.get("yt_title") or v["title"], "renders": v["board"]["renders"],
                                       "fix_rounds": v["board"]["fix_rounds"], "minutes": v["board"]["minutes"],
                                       "animatic": v.get("animatic_total"), "final": v["review_total"], "max": v.get("review_max"),
                                       "desks": [{"label": d["label"], "gate": d["gate"]} for d in v["board"]["desks"]],
                                       "timeline": v.get("timeline")}
                                      for v in data["videos"] if v.get("board")), None)}}


def encrypt(obj, pin, iterations=ITERATIONS):
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations).derive(pin.encode())
    ct = AESGCM(key).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode(), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "kdf": "PBKDF2-SHA256", "iter": iterations, "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}


def decrypt(box, pin):
    d = lambda s: base64.b64decode(s)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=d(box["salt"]), iterations=box["iter"]).derive(pin.encode())
    return json.loads(AESGCM(key).decrypt(d(box["iv"]), d(box["ct"]), None))


def pin():
    """The Studio PIN from secrets.env; made once (8 digits) if missing."""
    try:
        return secrets.get("FRAMEFLOW_WEB_PIN")
    except SystemExit:
        value = f"{pysecrets.randbelow(10**8):08d}"
        f = secrets.SECRETS_FILE
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a") as fh:
            fh.write(f"\n# Studio web app PIN (frameflow web export)\nFRAMEFLOW_WEB_PIN={value}\n")
        os.chmod(f, 0o600)
        print(f"made a new Studio PIN in {f} (FRAMEFLOW_WEB_PIN)")
        return value


def is_open():
    try:
        return bool(json.loads(ACCESS.read_text()).get("open"))
    except (OSError, ValueError):
        return False   # no switch file: stay locked


def set_access(open_):
    ACCESS.write_text(json.dumps({"open": open_}) + "\n")
    print(f"Studio is now {'open (no PIN)' if open_ else 'PIN-locked'}; exporting")
    return export()


def write_live(data):
    """betadoc/public/live.json, rewritten only when its content (apart from the time stamp) changed."""
    BETA.mkdir(parents=True, exist_ok=True)
    new = live(data)
    try:
        old = json.loads((BETA / "live.json").read_text())
        if {**old, "generated": None} == {**new, "generated": None}:
            return False
    except (OSError, ValueError):
        pass
    (BETA / "live.json").write_text(json.dumps(new, ensure_ascii=False, indent=1))
    return True


def export():
    data = snapshot()
    enc, plain = WEB / "data" / "studio.enc", WEB / "data" / "studio.json"
    open_ = is_open()
    key = None if open_ else pin()
    try:   # unchanged content (apart from the time stamp) keeps the old file, so a refresh has nothing to commit
        old = json.loads(plain.read_text()) if open_ else decrypt(json.loads(enc.read_text()), key)
        same = {**old, "generated": None} == {**data, "generated": None}
    except Exception:
        same = False
    (enc if open_ else plain).unlink(missing_ok=True)   # one form at a time: the page tries studio.json first
    if same:
        print("snapshot unchanged")
        write_live(data)   # the betadoc's numbers can change shape without the snapshot changing (26 Oct: the board block)
        return old
    enc.parent.mkdir(parents=True, exist_ok=True)
    if open_:
        plain.write_text(json.dumps(data, ensure_ascii=False))
    else:
        enc.write_text(json.dumps(encrypt(data, key)))
    write_live(data)
    print(f"{'studio.json (open)' if open_ else 'studio.enc'}: {len(data['runs'])} runs, {len(data['videos'])} videos, {len(data['cards'])} card posts, "
          f"{len(data['lessons'])} lessons; live.json written")
    return data


def refresh(reason):
    """Re-export and publish only the snapshot folders (commit + push; Vercel deploys the Studio and the betadoc)."""
    try:
        export()
        paths = ["web/public", "betadoc/public"]
        git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
        git("add", "--", *paths)
        if not git("diff", "--cached", "--quiet", "--", *paths).returncode:
            return "no change"
        r = git("commit", "-m", f"Studio snapshot: {reason}", "--", *paths)
        if r.returncode:
            return f"commit failed: {r.stderr.strip()[:200]}"
        r = git("push", "-q", "origin", "HEAD:main")
        return "pushed" if not r.returncode else f"push failed: {r.stderr.strip()[:200]}"
    except Exception as e:   # the Studio is a window, never a reason for a daily step to fail
        return f"refresh failed: {e}"


def main(argv=None):
    a = (argv if argv is not None else sys.argv[1:]) or ["export"]
    if a[0] == "export":
        export()
    elif a[0] == "refresh":
        print(refresh(" ".join(a[1:]) or "by hand"))
    elif a[0] in ("open", "lock"):
        set_access(a[0] == "open")
    elif a[0] == "pin":
        pin()
        print(f"FRAMEFLOW_WEB_PIN is in {secrets.SECRETS_FILE}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
