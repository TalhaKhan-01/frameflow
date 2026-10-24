"""Build step: turn a scene plan (+ voice) into a HyperFrames project, then render it.

    python -m frameflow.build project <plan.json> <out-dir> [--voice <voice-dir>] [--no-captions]
    python -m frameflow.build render <project-dir> [--out video.mp4] [--quality draft|looks|delivery]
    python -m frameflow.build scene <type> [--out-dir DIR]     build + render a template's sample.json on its own

Project layout written to <out-dir>:
    index.html                 root composition, 1080x1920, one host slot per scene (+ captions, voice)
    compositions/s<N>.html     one sub-composition per scene, from scenes/<type>/scene.html
    assets/                    theme.css, vendor/ (GSAP, fonts), voice.wav, scene assets
Scene timing: from the voice's durations.json when given (each scene lasts as long as its line, at least the
template minimum), else the plan's estimate (frameflow.scene_plan.scene_seconds).
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

from frameflow import scene_plan

ROOT = Path(__file__).resolve().parent.parent
SCENES = ROOT / "scenes"
SHARED = SCENES / "_shared"
HYPERFRAMES = ["npx", "--yes", "hyperframes@0.8.143"]
WIDTH, HEIGHT, PAD = 1080, 1920, scene_plan.PAD
TAIL = 0.6   # seconds of hold after the last line
HOUSE_THEME = "paper-press"   # accepted visual identity (vault: Decisions/Visual Identity)


def node_env():
    env = dict(os.environ, HYPERFRAMES_NO_TELEMETRY="1", HYPERFRAMES_SKIP_SKILLS="1")
    nvm = Path.home() / ".nvm/versions/node/v24.21.0/bin"
    if nvm.is_dir():
        env["PATH"] = f"{nvm}:{env['PATH']}"
    return env


def json_for_html(data):
    """JSON safe to place inside a <script type="application/json"> block."""
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def timings(plan, voice_dir=None):
    """(start, duration) per scene. With a voice, scenes follow it exactly: scene i starts when its line starts and
    lasts until the next line starts (the pause before a line belongs to the scene before it, a held beat)."""
    scenes = plan["scenes"]
    if voice_dir:
        info = json.loads((Path(voice_dir) / "durations.json").read_text())
        by_scene = {}
        for l in info["lines"]:   # ids "s3" or "s3.0", "s3.1" (a scene with several lines)
            by_scene.setdefault(int(l["id"][1:].split(".")[0]), []).append(l)
        starts = [by_scene[i][0]["start"] if i in by_scene else None for i in range(len(scenes))]
        out = []
        for i, s in enumerate(scenes):
            st = starts[i] if starts[i] is not None else (out[-1][0] + out[-1][1] if out else 0.0)
            if i == 0:
                st = 0.0
            nxt = next((x for x in starts[i + 1:] if x is not None), None)
            last = by_scene[i][-1] if i in by_scene else None
            end = nxt if nxt is not None else (last["start"] + last["seconds"] + PAD if last else st + scene_plan.scene_seconds(s))
            out.append((round(st, 3), round(max(end - st, 0.4), 3)))
        return out
    out, t = [], 0.0
    for s in scenes:
        d = scene_plan.scene_seconds(s) + PAD
        out.append((round(t, 3), round(d, 3)))
        t += d
    return out


WORD = re.compile(r"[a-z0-9]+")


def cue_times(scene, start, dur, words):
    """Resolve a scene's named cues ({"name": "phrase from the say line"}) to seconds from the scene's start, using the
    voice's word timings. A cue lands 0.06 s before its first word, so the picture moves with the voice. Built-ins:
    start (0) and end (0.35 s before the scene ends)."""
    cues = {"start": 0.0, "end": round(max(dur - 0.35, 0.0), 3)}
    inside = [w for w in words if start - 0.05 <= w["s"] < start + dur]
    toks = [(WORD.findall(w["w"].lower()), w["s"]) for w in inside]
    flat = [(tok, s) for ws, s in toks for tok in ws]
    for name, phrase in (scene.get("data", {}).get("cues") or {}).items():
        want = WORD.findall(phrase.lower())
        if not want:
            continue
        for i in range(len(flat) - len(want) + 1):
            if [f[0] for f in flat[i:i + len(want)]] == want:
                cues[name] = round(max(flat[i][1] - start - 0.06, 0.0), 3)
                break
        else:   # Whisper heard the phrase differently: match its first word alone, else leave the template's fallback
            hit = next((s for tok, s in flat if tok == want[0]), None)
            if hit is not None:
                cues[name] = round(max(hit - start - 0.06, 0.0), 3)
    return cues


# transition -> the sound it makes at the cut (library names from frameflow.music / data/library/sfx)
TRANSITION_SFX = {"whip-left": "whoosh", "whip-right": "whoosh", "whip-up": "whoosh", "glitch": "glitch",
                  "punch": "slam", "drop": "impact"}


def sfx_sheet(plan, slots, cues_per_scene):
    """Absolute-time sound cues: each scene's declared sfx ({at: seconds or cue, name, gain}) plus one sound per transition."""
    sheet = []
    for i, (scene, (start, dur)) in enumerate(zip(plan["scenes"], slots)):
        enter = scene.get("enter")
        if i > 0 and enter in TRANSITION_SFX:
            sheet.append({"t": round(max(start - 0.12, 0), 3), "name": TRANSITION_SFX[enter], "gain": -14, "why": f"s{i} {enter}"})
        for cue in scene.get("sfx", []):
            at = cue.get("at", 0)
            rel = at if isinstance(at, (int, float)) else cues_per_scene[i].get(at)
            if rel is None:
                continue
            sheet.append({"t": round(start + rel, 3), "name": cue["name"], "gain": cue.get("gain", -12), "why": f"s{i} {at}"})
    return sorted(sheet, key=lambda c: c["t"])


def voice_script(plan):
    """The voice step's script.json for a plan: one line per scene that has something to say. Version-2 plans use
    the Chatterbox house voice, with each scene's delivery markup (energy 0-1, pause_before seconds)."""
    v = plan.get("voice", {})
    if plan.get("version", 1) >= 2:
        lines = []
        for i, s in enumerate(plan["scenes"]):
            parts = s.get("lines") or ([{"say": s["say"], "delivery": s.get("delivery", {})}] if s.get("say", "").strip() else [])
            for j, part in enumerate(parts):   # a scene may carry several lines, each with its own delivery
                d = part.get("delivery", {})
                lines.append({"id": f"s{i}" if len(parts) == 1 else f"s{i}.{j}", "say": part["say"],
                              "energy": d.get("energy", s.get("energy", 0.6)), "pause_before": d.get("pause_before", 0.0)})
        return {"engine": v.get("engine", "chatterbox"), "model": v.get("model", "standard"), "tempo": v.get("tempo", 1.0),
                "seed": v.get("seed", 7), "voice": v.get("voice", "af_heart"), "speed": v.get("speed", 1.1), "pad": v.get("pad", 0.12),
                "lines": lines}
    return {"voice": v.get("voice", "af_heart"), "speed": v.get("speed", 1.1), "pad": PAD,
            "lines": [{"id": f"s{i}", "say": s["say"]} for i, s in enumerate(plan["scenes"]) if s.get("say", "").strip()]}


SOURCE_NAMES = {"livemint.com": "Mint", "economictimes.indiatimes.com": "The Economic Times", "indianexpress.com": "The Indian Express",
                "theverge.com": "The Verge", "techcrunch.com": "TechCrunch", "arstechnica.com": "Ars Technica", "inc42.com": "Inc42",
                "technologyreview.com": "MIT Technology Review", "reuters.com": "Reuters", "github.com": "GitHub",
                "news.google.com": "Google News", "apple.com": "Apple", "nvidia.com": "Nvidia", "gov.in": "Government of India"}


def source_name(url):
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    for domain, name in SOURCE_NAMES.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host


def credits_composition(credits, total):
    """A small 'Source: …' chip above the caption band while each claim scene is on screen."""
    chips = json.dumps([{"s": s, "e": round(s + d, 3), "name": n} for s, d, n in credits], ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html><head><meta charset="UTF-8" /></head><body><template>
<style>
  #credits-root {{ position: absolute; inset: 0; pointer-events: none; }}
  .credit {{ position: absolute; left: var(--ff-safe-x); top: calc(var(--ff-caption-top) - 92px); opacity: 0;
    font: 600 34px/1 var(--ff-body); color: var(--ff-muted); padding: 14px 20px; border: 2px solid var(--ff-line);
    border-radius: 999px; background: var(--ff-chip-bg); }}
  .credit b {{ color: var(--ff-fg); font-weight: 700; }}
</style>
<div id="credits-root" data-composition-id="credits" data-width="1080" data-height="1920" data-duration="{total:.3f}"></div>
<script>
  (() => {{
    const C = {chips};
    const root = document.getElementById("credits-root");
    const tl = gsap.timeline({{ paused: true }});
    C.forEach((c, i) => {{
      const el = document.createElement("div");
      el.className = "credit";
      el.id = "credit-" + i;
      el.append("Source: ");
      const b = document.createElement("b");
      b.textContent = c.name;
      el.append(b);
      root.append(el);
      tl.fromTo(el, {{ opacity: 0 }}, {{ opacity: 1, duration: 0.25 }}, c.s + 0.4);
      tl.set(el, {{ opacity: 0 }}, c.e);
    }});
    window.__timelines["credits"] = tl;
  }})();
</script>
</template></body></html>
"""


CODE_COLOURS = {"Keyword": "#a78bfa", "Name.Function": "#7dd3c0", "Name.Class": "#7dd3c0", "Name.Builtin": "#7aa2f7",
                "String": "#9ece6a", "Number": "#f6c177", "Comment": "#8b93ad", "Operator": "#f7768e", "Name.Decorator": "#f6c177"}


def highlight_code(code, language):
    """Syntax-coloured HTML lines (inline colours; Pygments escapes every text node)."""
    from pygments import lex
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.token import Token
    try:
        lexer = get_lexer_by_name(language)
    except Exception:
        lexer = guess_lexer(code)
    out = []
    for ttype, value in lex(code, lexer):
        colour = None
        t = ttype
        while t is not Token and colour is None:
            colour = CODE_COLOURS.get(str(t).removeprefix("Token."))
            t = t.parent
        text = html.escape(value)
        out.append(f'<span style="color:{colour}">{text}</span>' if colour else text)
    return "".join(out).rstrip("\n")


def render_scene_file(scene, comp_id, duration):
    tpl = (SCENES / scene["type"] / "scene.html").read_text()
    return (tpl.replace("__ID__", comp_id)
               .replace("__DUR__", f"{duration:.3f}")
               .replace("__DATA__", json_for_html(scene.get("data", {}))))


def project(plan, out_dir, voice_dir=None, captions=True, theme=None):
    errs = scene_plan.validate(plan)
    if errs:
        raise SystemExit("plan is not valid:\n" + "\n".join(errs))
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    (out / "compositions").mkdir(parents=True)
    shutil.copytree(SHARED, out / "assets")
    theme = theme or plan.get("theme") or HOUSE_THEME
    if theme and theme != "midnight-signal":   # a visual identity = a few token overrides appended to the shared theme
        extra = SHARED / "themes" / f"{theme}.css"
        if not extra.exists():
            raise SystemExit(f"no theme {theme} in {SHARED / 'themes'}")
        with open(out / "assets" / "theme.css", "a") as f:
            f.write("\n" + extra.read_text())
    slots = timings(plan, voice_dir)
    total = round(slots[-1][0] + slots[-1][1] + TAIL, 3)
    words = json.loads((Path(voice_dir) / "words.json").read_text()) if voice_dir and (Path(voice_dir) / "words.json").exists() else []
    cues_per_scene = [cue_times(s, st, d, words) for s, (st, d) in zip(plan["scenes"], slots)]
    hosts = []
    manifest = []
    for i, (scene, (start, dur)) in enumerate(zip(plan["scenes"], slots)):
        cid = f"s{i}"
        nxt = plan["scenes"][i + 1] if i + 1 < len(plan["scenes"]) else {}
        scene = {**scene, "data": {**scene.get("data", {}), "_cues": cues_per_scene[i],
                                   "_enter": scene.get("enter", "cut") if i > 0 else "cut", "_exit": nxt.get("enter", "cut")}}
        if scene["type"] == "code-card":
            scene = {**scene, "data": {**scene["data"], "_html": highlight_code(scene["data"]["code"], scene["data"]["language"])}}
        if scene["type"] == "news-snapshot":
            from frameflow import capture
            snap = f"assets/{cid}-snap.png"
            capture.capture(scene["data"]["url"], out / snap)
            scene = {**scene, "data": {**scene["data"], "_image": snap}}
            manifest.append({"file": snap, "asset": f"scene {i} snapshot", "source": f"screenshot of {scene['data']['url']}",
                             "licence": "short screenshot for news reporting and commentary (fair dealing), source credited on screen",
                             "url": scene["data"]["url"], "author": scene["data"].get("source", "")})
        (out / "compositions" / f"{cid}.html").write_text(render_scene_file(scene, cid, dur + (TAIL if i == len(slots) - 1 else 0)))
        for asset in (SCENES / scene["type"]).glob("asset-*"):
            shutil.copy(asset, out / "assets" / asset.name)
        hosts.append(f'<div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
                     f'data-start="{start}" data-duration="{dur + (TAIL if i == len(slots) - 1 else 0):.3f}" '
                     f'data-track-index="1" data-width="{WIDTH}" data-height="{HEIGHT}"></div>')
    audio = ""
    if voice_dir:
        shutil.copy(Path(voice_dir) / "voice.wav", out / "assets" / "voice.wav")
        audio = f'<audio id="voice" src="assets/voice.wav" data-start="0" data-duration="{total}" data-track-index="0"></audio>'
    credit_host = ""
    credits = [(start, dur, source_name(s["sources"][0])) for s, (start, dur) in zip(plan["scenes"], slots)
               if s.get("claim") and s.get("sources")]
    if credits:
        (out / "compositions" / "credits.html").write_text(credits_composition(credits, total))
        credit_host = (f'<div id="credits" data-composition-id="credits" data-composition-src="compositions/credits.html" '
                       f'data-start="0" data-duration="{total}" data-track-index="3" data-width="{WIDTH}" data-height="{HEIGHT}"></div>')
    caption_host = ""
    if captions and voice_dir and (Path(voice_dir) / "words.json").exists():
        from frameflow import captions as cap
        heard = json.loads((Path(voice_dir) / "words.json").read_text())
        script_text = " ".join(l["say"] for l in voice_script(plan)["lines"])
        shown = cap.respell(heard, script_text)   # script spelling, Whisper timing
        (Path(voice_dir) / "words-shown.json").write_text(json.dumps(shown, ensure_ascii=False, indent=0))
        (out / "compositions" / "captions.html").write_text(cap.composition(shown, total))
        caption_host = (f'<div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" '
                        f'data-start="0" data-duration="{total}" data-track-index="2" data-width="{WIDTH}" data-height="{HEIGHT}"></div>')
    # Load every bundled font with the page (not when a scene first uses it), so no render worker draws a fallback font.
    font_preloads = "\n    ".join(f'<link rel="preload" href="assets/vendor/fonts/{f.name}" as="font" type="font/woff2" crossorigin />'
                                   for f in sorted((SHARED / "vendor" / "fonts").glob("*.woff2")))
    font_warm = ('<div aria-hidden="true" style="position:absolute;opacity:0;pointer-events:none">'
                      '<span style="font-family:var(--ff-display)">₹Aa</span><span style="font-family:var(--ff-body)">₹Aa</span>'
                      '<span style="font-family:var(--ff-mono)">Aa</span>'
                      '<span style="font-family:var(--ff-hand);font-weight:700">Aa</span><span style="font-family:var(--ff-hand);font-weight:400">Aa</span></div>')
    three_script = ('\n    <script src="assets/vendor/three.min.js"></script>'
                    if any(s["type"] == "explainer-3d" for s in plan["scenes"]) else "")
    index = f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={WIDTH}, height={HEIGHT}" />
    <title>{html.escape(plan["title"])}</title>
    <link rel="stylesheet" href="assets/theme.css" />
    {font_preloads}
    <script src="assets/vendor/gsap.min.js"></script>
    <script src="assets/vendor/DrawSVGPlugin.min.js"></script>
    <script src="assets/vendor/MotionPathPlugin.min.js"></script>
    <script src="assets/vendor/MorphSVGPlugin.min.js"></script>
    <script src="assets/vendor/SplitText.min.js"></script>
    <script src="assets/vendor/CustomEase.min.js"></script>
    <script src="assets/vendor/rough.min.js"></script>
    <script>
      gsap.registerPlugin(DrawSVGPlugin, MotionPathPlugin, MorphSVGPlugin, SplitText, CustomEase);
    </script>
    <script src="assets/ff-kit.js"></script>{three_script}
    <style>
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; background: var(--ff-bg); }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{WIDTH}" data-height="{HEIGHT}">
      {font_warm}
      {audio}
      {chr(10).join("      " + h for h in hosts).strip()}
      {caption_host}
      {credit_host}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
    (out / "index.html").write_text(index)
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    (out / "assets-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    (out / "sfx.json").write_text(json.dumps(sfx_sheet(plan, slots, cues_per_scene), indent=1))
    (out / "cues.json").write_text(json.dumps([{"scene": i, "start": st, "dur": d, "cues": c} for i, ((st, d), c) in enumerate(zip(slots, cues_per_scene))], indent=1))
    (out / "package.json").write_text(json.dumps({"name": plan["id"], "private": True, "type": "module"}, indent=1))
    return out, total


def false_positive(f):
    """HyperFrames 0.8.143's contrast audit samples SVG <text> as sitting on pure black (it can't hide an SVG text's
    fill before sampling), so drawn labels on light paper fail at about 1.2:1. Readability of drawn scenes is checked
    on rendered frames instead (keyframe review). Every other finding still counts."""
    return f.get("code") == "contrast_aa_failure" and f.get("bg") == "rgb(0,0,0)"   # no frameflow theme paints pure black


def check(project_dir):
    """HyperFrames check (lint, runtime, layout, motion, contrast). Returns (exit code, readable log)."""
    r = subprocess.run(HYPERFRAMES + ["check", "--json"], cwd=project_dir, env=node_env(), capture_output=True, text=True, timeout=900)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return (r.returncode or 1), (r.stdout + r.stderr)[-3000:]
    lines, errors = [], 0
    for section in ("lint", "runtime", "layout", "motion", "contrast"):
        for f in (d.get(section) or {}).get("findings", []):
            if f.get("severity") not in ("error", "warning"):
                continue
            ignored = false_positive(f)
            if f.get("severity") == "error" and not ignored:
                errors += 1
            lines.append(f"{'ignored ' if ignored else ''}{f['severity']} {section}/{f.get('code')}: {f.get('message', '')} "
                         f"{f.get('text', '')!r} {f.get('selector', '')[-80:]} t={f.get('time', '')}")
    if d.get("browserSkipped"):
        errors += 1
        lines.append("error: browser checks were skipped (lint errors?)")
    return (1 if errors else 0), "\n".join(["✗ " + l if not l.startswith("ignored") else "  " + l for l in lines]) or "clean"


def render(project_dir, out_file=None, quality="looks"):
    out_file = Path(out_file or Path(project_dir) / "video.mp4").resolve()
    r = subprocess.run(HYPERFRAMES + ["render", "--quality", quality, "--output", str(out_file)], cwd=project_dir,
                       env=node_env(), capture_output=True, text=True, timeout=3600)
    if r.returncode or not out_file.exists():
        raise SystemExit(f"render failed:\n{(r.stdout + r.stderr)[-2000:]}")
    return out_file


def scene_sample(scene_type, out_dir=None):
    sample = json.loads((SCENES / scene_type / "sample.json").read_text())
    plan = {"id": f"sample-{scene_type}", "lane": "global-tech", "title": f"Sample: {scene_type}",
            "scenes": [sample]}
    out = Path(out_dir or ROOT / "out" / "samples" / scene_type)
    return project(plan, out)


def main():
    ap = argparse.ArgumentParser(description="Frameflow build step (HyperFrames).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("project")
    p.add_argument("plan")
    p.add_argument("out_dir")
    p.add_argument("--voice")
    p.add_argument("--no-captions", action="store_true")
    r = sub.add_parser("render")
    r.add_argument("project_dir")
    r.add_argument("--out")
    r.add_argument("--quality", default="looks", choices=["draft", "looks", "delivery"])
    s = sub.add_parser("scene")
    s.add_argument("type")
    s.add_argument("--out-dir")
    s.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    if a.cmd == "project":
        out, total = project(json.loads(Path(a.plan).read_text()), a.out_dir, a.voice, not a.no_captions)
        print(f"project {out} ({total:.2f} s)")
    elif a.cmd == "render":
        print(render(a.project_dir, a.out, a.quality))
    else:
        out, total = scene_sample(a.type, a.out_dir)
        code, log = check(out)
        print(f"check exit {code}\n" + "\n".join(l for l in log.splitlines() if l.strip())[-1500:])
        if not a.no_render:
            print(render(out))


if __name__ == "__main__":
    main()
