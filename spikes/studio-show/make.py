"""Studio-show spike (P24.1): build, check and render the samples of The Daily Habit show.

    uv run python spikes/studio-show/make.py --list                 every variant
    uv run python spikes/studio-show/make.py build <variant>...     HyperFrames project(s) in out/studio-show/<variant>/
    uv run python spikes/studio-show/make.py check <variant>...     build + hyperframes check (frameflow.build.check)
    uv run python spikes/studio-show/make.py render <variant>...    build + check + render to out/studio-show/<variant>.mp4
    uv run python spikes/studio-show/make.py sheets                 look sheet, layout sheet (stills via hyperframes snapshot)
    uv run python spikes/studio-show/make.py safe                   safe-zone check of the four framings against the platform UI
    uv run python spikes/studio-show/make.py mouth                  Habit's mouth moves only while the voice speaks (every variant)

Inputs: episode.json (the sample script, shots and graphics), the voice in out/studio-show/voice/ (frameflow.voice tts
of out/studio-show/voice-script.json, one WAV per line, words.json from frameflow.captions.align). One composition
(show.js) draws every variant: set x Habit look x sequence. Nothing here touches the daily make.
"""
import json
import shutil
import subprocess
import sys
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from frameflow import build, captions  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = ROOT / "out" / "studio-show"
VOICE = OUT / "voice"
FPS = 30
STING = 1.5
GAP = 0.22          # breath between lines
END_HOLD = 2.6      # end card hold after the outro line
SETS, LOOKS = ["riso", "paper", "night"], ["pixel", "puppet"]

EP = json.loads((HERE / "episode.json").read_text())
BEATS = {b["id"]: b for b in EP["beats"]}
WALL = {"loop": ("$3M", "PER AI SERVER RACK"), "payoff": ("TRUST", "THE WEAK SPOT"), "ending": ("?", "WHAT ELSE DO WE TRUST"),
        "intro-breaking": ("BREAKING", "AI FREIGHT THEFT"), "intro-greeting": ("28 OCT", "THE DAILY HABIT")}
CLAIMS = {"loop", "gps", "ninety", "fake", "link", "driver", "ram", "cornell", "fix"}


def line(id_, **over):
    b = BEATS.get(id_, {})
    item = {"line": id_, "shot": b.get("shot", "wide"), "vis": b.get("vis")}
    if id_ == "loop":
        item["shots"] = [[0, "wide"], [3.4, "split"]]
    if id_ == "payoff":
        item["shots"] = [[0, "wide"]]
    item.update(over)
    return item


def sequences():
    story = ["loop", "gps", "ninety", "broker", "fake", "link", "imagine", "driver", "ram", "cornell", "payoff", "fix", "ending"]
    episode = [line("hook"), {"sting": STING}, *[line(i) for i in story], line("outro", shot="end", vis=None)]
    trailer = [line("hook"), {"sting": STING}, line("loop"), line("gps"), line("ninety"), line("fake"), line("payoff"), line("outro", shot="end", vis=None)]
    talk = [line("intro-talk", shots=[[0, "wide"], [2.2, "split"], [4.4, "pip"]], vis="lading")]
    intros = {
        "cold": [line("hook"), {"sting": STING}, line("loop")],
        "breaking": [line("intro-breaking", shot="wide", breaking=True), {"sting": STING}, line("loop")],
        "teaser": [line("intro-teaser", shot="pip", vis="today"), {"sting": STING}, line("loop")],
        "greeting": [{"sting": STING}, line("intro-greeting", shot="wide"), line("hook")],
    }
    v = {}
    for s in SETS:
        v[f"set-{s}"] = {"set": s, "look": "puppet", "seq": trailer}
    v["episode"] = {"set": "riso", "look": "puppet", "seq": episode}
    for lk in LOOKS:
        v[f"talk-{lk}"] = {"set": "riso", "look": lk, "seq": talk}
        for s in SETS:
            v[f"still-{s}-{lk}"] = {"set": s, "look": lk, "seq": [{"silent": 2.0, "shot": "wide", "wall": "TRUST"}]}
    for k, seq in intros.items():
        v[f"intro-{k}"] = {"set": "riso", "look": "puppet", "seq": seq}
    v["layout"] = {"set": "riso", "look": "puppet", "ui": True, "seq": [
        {"silent": 2.0, "shot": "wide", "wall": "TRUST", "cap": "Captions sit here"},
        {"silent": 3.0, "shot": "split", "vis": "map", "cap": "Captions on the seam"},
        {"silent": 3.0, "shot": "pip", "vis": "board", "cap": "Captions beside Habit"},
        {"silent": 3.0, "shot": "full", "vis": "stat", "cap": "Captions under the graphic"}]}
    v["package"] = {"set": "riso", "look": "puppet", "seq": [
        {"silent": 1.2, "shot": "wide", "wall": "TRUST"}, {"sting": STING},
        {"silent": 4.5, "shot": "wide", "wall": "$3M", "l3": True},
        {"silent": 3.0, "shot": "pip", "vis": "board", "claim": True},
        {"silent": 3.5, "shot": "wide", "wall": "?", "ticker": True}], "end": 2.5}
    return v


# ---------- voice: per-line WAVs, timings, envelope, words ----------
def durations():
    d = json.loads((VOICE / "durations.json").read_text())
    return {l["id"]: l for l in d["lines"]}


def envelope(wav):
    """RMS per 1/30 s, normalised to the line's 95th percentile (0-1): drives Habit's mouth."""
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(wav), "-ac", "1", "-ar", "12000", "-f", "s16le", "-"], capture_output=True).stdout
    a = array("h"); a.frombytes(raw)
    hop = 12000 // FPS
    vals = []
    for i in range(0, len(a), hop):
        chunk = a[i:i + hop]
        vals.append((sum(x * x for x in chunk) / max(len(chunk), 1)) ** 0.5)
    ref = sorted(vals)[int(len(vals) * 0.95)] or 1
    return [round(min(v / ref, 1.0), 3) for v in vals]


def line_words():
    """Script spelling with Whisper timing, cut per line and made relative to the line's start."""
    lines = json.loads((VOICE / "durations.json").read_text())["lines"]
    heard = json.loads((VOICE / "words.json").read_text())
    script = json.loads((OUT / "voice-script.json").read_text())
    shown = captions.respell(heard, " ".join(l["say"] for l in script["lines"]))
    out = {}
    for l in lines:
        a, b = l["start"] - 0.05, l["start"] + l["seconds"] + 0.05
        out[l["id"]] = [{"w": w["w"], "s": round(w["s"] - l["start"], 3), "e": round(w["e"] - l["start"], 3)} for w in shown if a <= w["s"] < b]
    return out


# ---------- a variant: timeline, audio, config ----------
def plan(name, spec):
    D = durations()
    W = line_words()
    t, segs, audio, words, env, cfg = 0.3, [], [], [], [], {}
    for item in spec["seq"]:
        if "sting" in item:
            cfg["stingAt"] = round(t, 3)
            segs.append({"start": t, "dur": item["sting"], "shot": "wide", "wall": "THE DAILY HABIT"})
            t += item["sting"]
            continue
        if "silent" in item:
            seg = {"start": t, "dur": item["silent"], "shot": item["shot"], "vis": item.get("vis"), "wall": item.get("wall"), "claim": item.get("claim", False)}
            if item.get("cap"):
                ws = item["cap"].split()
                words += [{"w": w, "s": round(t + 0.2 + i * 0.01, 3), "e": round(t + item["silent"] - 0.1, 3), "g": f"cap{len(segs)}"} for i, w in enumerate(ws)]
            if item.get("l3"): cfg["l3At"] = round(t + 0.3, 3)
            if item.get("ticker"): cfg["tickerAt"] = round(t + 0.2, 3)
            segs.append(seg); t += item["silent"]
            continue
        lid = item["line"]
        info = D[lid]
        t += BEATS.get(lid, {}).get("pause_before", 0)
        wall = WALL.get(lid, (None, None))
        seg = {"start": round(t, 3), "dur": round(info["seconds"] + GAP, 3), "shot": item["shot"], "vis": item.get("vis"),
               "wall": wall[0], "wallSub": wall[1], "claim": lid in CLAIMS, "id": lid}
        if "shots" in item: seg["shots"] = item["shots"]
        if lid == "loop": cfg.setdefault("l3At", round(t + 0.3, 3))
        if lid == "ending": cfg["tickerAt"] = round(t + 0.2, 3)
        if item.get("breaking"): cfg["breakingAt"], cfg["breakingDur"] = round(t + 0.1, 3), info["seconds"]
        if lid == "outro": cfg["endAt"] = round(t - 0.2, 3)
        audio.append((VOICE / info["file"], t))
        words += [{"w": w["w"], "s": round(t + w["s"], 3), "e": round(t + w["e"], 3), "g": f"{len(segs)}-{i // 3}"} for i, w in enumerate(W.get(lid, []))]
        e = envelope(VOICE / info["file"])
        start_f = int(round(t * FPS))
        if len(env) < start_f: env += [0.0] * (start_f - len(env))
        env[start_f:start_f + len(e)] = e
        segs.append(seg)
        t += info["seconds"] + GAP
    end_dur = 0.0
    if "endAt" in cfg:
        t += END_HOLD; end_dur = t - cfg["endAt"]; segs[-1]["dur"] = round(t - segs[-1]["start"], 3)
    elif spec.get("end"):
        cfg["endAt"] = round(t, 3); segs.append({"start": t, "dur": spec["end"], "shot": "end"}); t += spec["end"]; end_dur = spec["end"]
    dur = round(t + 0.3, 3)
    segs[-1]["dur"] = round(dur - segs[-1]["start"], 3)
    return {**cfg, "set": spec["set"], "look": spec["look"], "ui": spec.get("ui", False), "dur": dur, "segments": segs,
            "words": words, "env": env, "envFps": FPS, "endDur": end_dur, "lane": EP["lane"], "date": EP["date"],
            "storyTitle": EP["story_title"], "source": EP["source"], "ticker": EP["ticker"]}, audio


def mix(audio, dur, out):
    if not audio:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", str(dur), str(out)], check=True)
        return
    args, parts = ["ffmpeg", "-v", "error", "-y"], []
    for i, (f, start) in enumerate(audio):
        args += ["-i", str(f)]
        ms = int(round(start * 1000))
        parts.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    graph = ";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(len(audio))) + f"amix=inputs={len(audio)}:normalize=0,apad,atrim=0:{dur}[out]"
    subprocess.run(args + ["-filter_complex", graph, "-map", "[out]", "-ar", "48000", "-ac", "1", str(out)], check=True)


def project(name, spec):
    cfg, audio = plan(name, spec)
    out = OUT / name
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(build.SHARED, out / "assets")
    with open(out / "assets" / "theme.css", "a") as f:   # FF Serif (Fraunces) comes with the Paper Press tokens
        f.write("\n" + (build.SHARED / "themes" / "paper-press.css").read_text())
    shutil.copy(HERE / "show.js", out / "assets" / "show.js")
    mix(audio, cfg["dur"], out / "assets" / "voice.wav")
    fonts = "\n    ".join(f'<link rel="preload" href="assets/vendor/fonts/{f.name}" as="font" type="font/woff2" crossorigin />'
                          for f in sorted((build.SHARED / "vendor" / "fonts").glob("*.woff2")))
    warm = ('<div aria-hidden="true" style="position:absolute;opacity:0">' + "".join(
        f'<span style="font-family:{ff};font-weight:{w}">Aa₹</span>' for ff, w in
        [('"FF Serif"', 800), ('"FF Display"', 700), ('"FF Body"', 700), ('"FF Mono"', 700), ('"FF Hand"', 700)]) + "</div>")
    html = f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <title>The Daily Habit · {name}</title>
    <link rel="stylesheet" href="assets/theme.css" />
    {fonts}
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/DrawSVGPlugin.min.js"></script>
    <script src="assets/vendor/MotionPathPlugin.min.js"></script>
    <script src="assets/vendor/rough.min.js"></script>
    <script>gsap.registerPlugin(DrawSVGPlugin, MotionPathPlugin);</script>
    <script src="assets/ff-kit.js"></script>
    <script src="assets/show.js"></script>
    <style>#root {{ position: relative; width: 100%; height: 100%; overflow: hidden; }}</style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{cfg['dur']}" data-width="1080" data-height="1920">
      {warm}
      <audio id="voice" src="assets/voice.wav" data-start="0" data-duration="{cfg['dur']}" data-track-index="0"></audio>
      <div id="show"></div>
    </div>
    <script type="application/json" id="cfg">{build.json_for_html(cfg)}</script>
    <script>
      window.__timelines = window.__timelines || {{}};
      SHOW.build(JSON.parse(document.getElementById("cfg").textContent));
    </script>
  </body>
</html>
"""
    (out / "index.html").write_text(html)
    (out / "package.json").write_text(json.dumps({"name": f"studio-show-{name}", "private": True, "type": "module"}))
    (out / "plan.json").write_text(json.dumps({k: v for k, v in cfg.items() if k not in ("env", "words")}, indent=1))
    return out, cfg


def check(name, spec):
    out, cfg = project(name, spec)
    code, log = build.check(out)
    print(f"{name}: {cfg['dur']:.1f} s · check exit {code}\n  " + "\n  ".join(log.splitlines()[-12:]))
    return out, cfg, code


def render(name, spec):
    out, cfg, code = check(name, spec)
    if code:
        raise SystemExit(f"{name}: check failed")
    mp4 = build.render(out, OUT / f"{name}.mp4", quality="looks")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,r_frame_rate", "-of", "json", str(mp4)],
                           capture_output=True, text=True).stdout
    p = json.loads(probe)
    v = next(s for s in p["streams"] if "width" in s)
    got = float(p["format"]["duration"])
    black = subprocess.run(["ffmpeg", "-v", "info", "-i", str(mp4), "-vf", "blackdetect=d=0.5:pix_th=0.05", "-an", "-f", "null", "-"],
                           capture_output=True, text=True).stderr.count("black_start")
    print(f"{mp4.name}: {v['width']}x{v['height']} {v['r_frame_rate']} {got:.2f} s (plan {cfg['dur']:.2f}) black stretches: {black}")
    return mp4


# ---------- safe zones ----------
UI = [(0, 1500, 1080, 1920), (900, 1000, 1080, 1920)]   # union of YouTube Shorts / IG Reels / FB Reels overlays (x0, y0, x1, y1)


def safe():
    """Habit's face box in each framing (mirrors framing() in show.js; face radius ~125 px in set space)."""
    face = {"wide": (540, 1090, 1.0), "split": (540, 1320, 1.6), "pip": (208, 1310, 1.12)}
    zones = [(60, 150, 1020, 1000), (60, 1000, 890, 1080)]   # graphic content: full width to 1000 px, left of the buttons below
    bad = []
    for shot, (x, y, s) in face.items():
        r = 125 * s
        box = (x - r, y - r, x + r, y + r * 0.9)   # to the chin
        for u in UI:
            if box[0] < u[2] and box[2] > u[0] and box[1] < u[3] and box[3] > u[1]:
                bad.append(f"{shot}: face {tuple(round(v) for v in box)} overlaps UI {u}")
        print(f"{shot:6} face box {tuple(round(v) for v in box)}")
    for g in zones:
        for u in UI:
            if g[0] < u[2] and g[2] > u[0] and g[1] < u[3] and g[3] > u[1]:
                bad.append(f"graphics zone {g} overlaps UI {u}")
    pip = (48, 1120, 368, 1440)
    if any(pip[0] < u[2] and pip[2] > u[0] and pip[1] < u[3] and pip[3] > u[1] for u in UI):
        bad.append("PiP window overlaps UI")
    print("SAFE OK" if not bad else "\n".join(bad))
    return not bad


def mouth():
    """The mouth value show.js computes (clamp((env - 0.06) / 0.5)) must be 0 in every silent stretch and open on most
    voiced frames: Habit never talks over silence and never sits still while he speaks."""
    ok = True
    for name, spec in sequences().items():
        cfg, audio = plan(name, spec)
        env = cfg["env"]
        m = [min(max((v - 0.06) / 0.5, 0), 1) for v in env]
        D = durations()
        voiced = set()
        for f, start in audio:
            secs = next(l["seconds"] for l in D.values() if l["file"] == f.name)
            voiced |= set(range(int(start * FPS), int((start + secs) * FPS) + 1))
        silent_open = [i for i, v in enumerate(m) if v > 0 and i not in voiced]
        talk = [i for i in voiced if i < len(m) and m[i] > 0]
        share = len(talk) / max(len(voiced), 1)
        bad = silent_open or (audio and share < 0.5)
        ok &= not bad
        print(f"{name:24} silent frames with an open mouth: {len(silent_open):3}  voiced frames talking: {share:4.0%}  {'FAIL' if bad else 'ok'}")
    print("MOUTH OK" if ok else "MOUTH FAIL")
    return ok


# ---------- sheets ----------
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def snap(name, spec, at):
    out, cfg = project(name, spec)
    shots = out / "snaps"
    r = subprocess.run(build.HYPERFRAMES + ["snapshot", str(out), "-o", str(shots), "--at", ",".join(f"{a:.2f}" for a in at), "--no-end", "--describe", "false"],
                       cwd=out, env=build.node_env(), capture_output=True, text=True, timeout=600)
    pngs = sorted(shots.glob("*.png"))
    if len(pngs) < len(at):
        raise SystemExit(f"snapshot {name} failed: {(r.stdout + r.stderr)[-1500:]}")
    return pngs


def label(png, text, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(png), "-vf",
                    f"scale=540:960,drawbox=x=0:y=880:w=540:h=80:color=black@0.75:t=fill,drawtext=fontfile={FONT}:text='{text}':x=(w-tw)/2:y=905:fontsize=34:fontcolor=white",
                    str(out)], check=True)


def grid(tiles, cols, out):
    n = len(tiles)
    layout = "|".join(f"{(i % cols) * 540}_{(i // cols) * 960}" for i in range(n))
    args = ["ffmpeg", "-v", "error", "-y"]
    for t in tiles: args += ["-i", str(t)]
    subprocess.run(args + ["-filter_complex", f"{''.join(f'[{i}:v]' for i in range(n))}xstack=inputs={n}:layout={layout}", str(out)], check=True)


def sheets():
    v = sequences()
    tmp = OUT / "sheet-tiles"; tmp.mkdir(exist_ok=True)
    tiles = []
    for lk in LOOKS:
        for s in SETS:
            png = snap(f"still-{s}-{lk}", v[f"still-{s}-{lk}"], [1.2])[0]
            t = tmp / f"look-{s}-{lk}.png"; label(png, f"{s.upper()} · {lk.upper()}", t); tiles.append(t)
    grid(tiles, 3, OUT / "habit-look-sheet.png")
    cfg, _ = plan("layout", v["layout"])
    at = [s["start"] + s["dur"] - 0.15 for s in cfg["segments"]]
    pngs = snap("layout", v["layout"], at)
    tiles = []
    for png, name in zip(pngs, ["1 STUDIO WIDE", "2 SPLIT CLOSE-UP", "3 SQUARE PIP", "4 FULL GRAPHIC"]):
        t = tmp / f"layout-{name[0]}.png"; label(png, name, t); tiles.append(t)
    grid(tiles, 4, OUT / "framing-layout-sheet.png")
    cfg, _ = plan("package", v["package"])
    pk = [cfg["stingAt"] + 0.9, cfg["l3At"] + 1.2, cfg["segments"][3]["start"] + 2.5, cfg["tickerAt"] + 2.0, cfg["endAt"] + 1.5]
    pngs = snap("package", v["package"], pk)
    tiles = []
    for png, name in zip(pngs, ["STING", "LOWER-THIRD + LANE BUG", "PIP MONITOR + SOURCE CHIP", "TICKER", "END CARD"]):
        t = tmp / f"package-{name.split()[0]}.png"; label(png, name, t); tiles.append(t)
    grid(tiles, 5, OUT / "motion-package-sheet.png")
    print("sheets:", *(OUT / n for n in ["habit-look-sheet.png", "framing-layout-sheet.png", "motion-package-sheet.png"]))


def main():
    v = sequences()
    a = sys.argv[1:]
    if not a or a[0] == "--list":
        for k, s in v.items():
            cfg, _ = plan(k, s)
            print(f"{k:24} set={s['set']:6} look={s['look']:7} {cfg['dur']:6.1f} s")
        return
    cmd, names = a[0], a[1:]
    if cmd == "sheets":
        return sheets()
    if cmd == "safe":
        sys.exit(0 if safe() else 1)
    if cmd == "mouth":
        sys.exit(0 if mouth() else 1)
    fn = {"build": project, "check": check, "render": render}[cmd]
    failed = 0
    for n in names:
        r = fn(n, v[n])
        if cmd == "check" and r[2]: failed += 1
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
