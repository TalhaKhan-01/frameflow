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
    """(start, duration) per scene; with a voice, each scene covers its line plus the pause after it."""
    scenes = plan["scenes"]
    if voice_dir:
        info = json.loads((Path(voice_dir) / "durations.json").read_text())
        lines = {l["id"]: l for l in info["lines"]}
        out, t = [], 0.0
        for i, s in enumerate(scenes):
            line = lines.get(f"s{i}")
            minimum = scene_plan.SCENES[s["type"]][0]
            d = max((line["seconds"] if line else 0.0) + PAD, minimum)
            out.append((round(t, 3), round(d, 3)))
            t += d
        return out
    out, t = [], 0.0
    for s in scenes:
        d = scene_plan.scene_seconds(s) + PAD
        out.append((round(t, 3), round(d, 3)))
        t += d
    return out


def voice_script(plan):
    """The voice step's script.json for a plan: one line per scene that has something to say."""
    v = plan.get("voice", {})
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
    font: 600 30px/1 var(--ff-body); color: var(--ff-muted); padding: 12px 18px; border: 2px solid var(--ff-line);
    border-radius: 999px; background: rgba(11, 13, 18, 0.7); }}
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


def render_scene_file(scene, comp_id, duration):
    tpl = (SCENES / scene["type"] / "scene.html").read_text()
    return (tpl.replace("__ID__", comp_id)
               .replace("__DUR__", f"{duration:.3f}")
               .replace("__DATA__", json_for_html(scene.get("data", {}))))


def project(plan, out_dir, voice_dir=None, captions=True):
    errs = scene_plan.validate(plan)
    if errs:
        raise SystemExit("plan is not valid:\n" + "\n".join(errs))
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    (out / "compositions").mkdir(parents=True)
    shutil.copytree(SHARED, out / "assets")
    slots = timings(plan, voice_dir)
    total = round(slots[-1][0] + slots[-1][1] + TAIL, 3)
    hosts = []
    for i, (scene, (start, dur)) in enumerate(zip(plan["scenes"], slots)):
        cid = f"s{i}"
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
        (out / "compositions" / "captions.html").write_text(cap.composition(json.loads((Path(voice_dir) / "words.json").read_text()), total))
        caption_host = (f'<div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" '
                        f'data-start="0" data-duration="{total}" data-track-index="2" data-width="{WIDTH}" data-height="{HEIGHT}"></div>')
    index = f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={WIDTH}, height={HEIGHT}" />
    <title>{html.escape(plan["title"])}</title>
    <link rel="stylesheet" href="assets/theme.css" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; background: var(--ff-bg); }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{WIDTH}" data-height="{HEIGHT}">
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
    (out / "package.json").write_text(json.dumps({"name": plan["id"], "private": True, "type": "module"}, indent=1))
    return out, total


def check(project_dir):
    r = subprocess.run(HYPERFRAMES + ["check"], cwd=project_dir, env=node_env(), capture_output=True, text=True, timeout=900)
    return r.returncode, (r.stdout + r.stderr)


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
