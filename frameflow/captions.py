"""Captions: word timings from the real voice track, and the word-pop caption layer.

    python -m frameflow.captions align <voice-dir>      voice.wav -> words.json (local Whisper, word timestamps)
    python -m frameflow.captions wer <voice-dir>        word error rate of words.json against the script lines

words.json: [{"w": "The", "s": 0.00, "e": 0.18}, ...]  (seconds on the video's timeline)
The caption layer shows short chunks (up to 3 words, broken at pauses and punctuation) in the caption band,
and highlights each word from the moment it is spoken.
"""
import argparse
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path

TRANSCRIBER = ["uvx", "--quiet", "whisper-ctranslate2@0.5.8", "--model", "base.en", "--device", "cpu",
               "--compute_type", "int8"]
MAX_WORDS, PAUSE = 3, 0.35


def align(voice_dir):
    vd = Path(voice_dir)
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(TRANSCRIBER + [str(vd / "voice.wav"), "--word_timestamps", "True", "--output_format", "json",
                                          "--output_dir", tmp], capture_output=True, text=True, timeout=900)
        out = Path(tmp) / "voice.json"
        if not out.exists():
            raise SystemExit(f"transcription failed: {r.stderr[-800:]}")
        segs = json.loads(out.read_text())["segments"]
    words = []
    for s in segs:
        for w in s.get("words", []):
            text = w["word"].strip()
            if not text:
                continue
            # Whisper splits "20,000" into "20" + ",000" and sometimes emits bare punctuation: glue them back.
            if words and (re.match(r"^[,.]\d", text) or not re.search(r"\w", text)):
                words[-1]["w"] += text
                words[-1]["e"] = round(w["end"], 3)
                continue
            words.append({"w": text, "s": round(w["start"], 3), "e": round(w["end"], 3)})
    (vd / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=0))
    return words


ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def spell(n):
    """Integer to English words (international scale), for comparing '20,000' with 'twenty thousand'."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + spell(n % 100))
    for size, name in ((10**9, "billion"), (10**6, "million"), (1000, "thousand")):
        if n >= size:
            return spell(n // size) + " " + name + ("" if n % size == 0 else " " + spell(n % size))


def norm(text):
    """Lowercase word tokens; numbers spelled out, ₹ read as rupees, spelled letters (G.S.T.) joined."""
    text = text.lower().replace("₹", " rupees ").replace("%", " percent ")
    text = re.sub(r"\b(?:[a-z]\.){2,}", lambda m: m.group(0).replace(".", ""), text)
    def number(m):
        raw = m.group(0)
        n = int(raw.replace(",", ""))
        if "," not in raw and 1900 <= n <= 2099:   # years are said "twenty twenty-seven", not "two thousand ..."
            return f" {spell(n // 100)} {spell(n % 100) if n % 100 else 'hundred'} "
        return " " + spell(n) + " "
    text = re.sub(r"\d[\d,]*", number, text)
    return re.findall(r"[a-z]+", text)


def wer(reference, hypothesis):
    """Word error rate (edit distance over words) of hypothesis against reference."""
    ref, hyp = norm(reference), norm(hypothesis)
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1] / max(len(ref), 1)


def chunks(words):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if (len(cur) >= MAX_WORDS or re.search(r"[.,!?;:]$", w["w"]) or nxt is None
                or nxt["s"] - w["e"] > PAUSE):
            out.append(cur)
            cur = []
    return out


def composition(words, total):
    """HyperFrames sub-composition (id 'captions') with the word-pop layer."""
    groups = chunks(words)
    data = []
    for gi, g in enumerate(groups):
        end = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else min(g[-1]["e"] + 0.6, total)
        data.append({"start": g[0]["s"], "end": round(end, 3), "words": [{"w": w["w"], "s": w["s"]} for w in g]})
    return """<!doctype html>
<html>
  <head><meta charset="UTF-8" /></head>
  <body>
    <template>
      <style>
        #captions-root { position: absolute; inset: 0; pointer-events: none; }
        #captions-band { position: absolute; left: var(--ff-safe-x); right: var(--ff-safe-right); top: var(--ff-caption-top);
          height: 260px; display: flex; align-items: center; justify-content: center; }
        .cap-chunk { position: absolute; left: 0; right: 0; text-align: center; opacity: 0; }
        .cap-w { display: inline-block; margin: 0 0.26em; transform-origin: 50% 60%; font: 800 84px/1.1 var(--ff-display); letter-spacing: -0.02em;
          color: var(--ff-fg); text-transform: uppercase; -webkit-text-stroke: 10px rgba(5, 7, 12, 0.85); paint-order: stroke fill; }
        .cap-w.on { color: var(--ff-accent-2); }
      </style>
      <div id="captions-root" data-composition-id="captions" data-width="1080" data-height="1920" data-duration="__TOTAL__">
        <div id="captions-band"></div>
      </div>
      <script>
        (() => {
          const C = __DATA__;
          const band = document.getElementById("captions-band");
          const tl = gsap.timeline({ paused: true });
          C.forEach((c, ci) => {
            const chunk = document.createElement("div");
            chunk.className = "cap-chunk";
            chunk.id = "cap-c" + ci;
            c.words.forEach((w, wi) => {
              const span = document.createElement("span");
              span.className = "cap-w";
              span.id = "cap-c" + ci + "-w" + wi;
              span.textContent = w.w;
              chunk.append(span);
            });
            band.append(chunk);
            tl.set(chunk, { opacity: 1 }, c.start);
            tl.fromTo(chunk, { y: 18 }, { y: 0, duration: 0.12, ease: "power2.out" }, c.start);
            tl.set(chunk, { opacity: 0 }, c.end);
            c.words.forEach((w, wi) => {
              const el = "#cap-c" + ci + "-w" + wi;
              tl.set(el, { attr: { class: "cap-w on" } }, w.s);
              tl.fromTo(el, { scale: 1.1 }, { scale: 1, duration: 0.16, ease: "power2.out" }, w.s);
              if (wi + 1 < c.words.length) tl.set(el, { attr: { class: "cap-w" } }, c.words[wi + 1].s);
            });
          });
          window.__timelines["captions"] = tl;
        })();
      </script>
    </template>
  </body>
</html>
""".replace("__TOTAL__", f"{total:.3f}").replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))


def main():
    ap = argparse.ArgumentParser(description="Frameflow captions.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("align")
    a1.add_argument("voice_dir")
    a2 = sub.add_parser("wer")
    a2.add_argument("voice_dir")
    a2.add_argument("--script", help="script.json with the spoken lines (default: <voice-dir>/script.json)")
    a = ap.parse_args()
    if a.cmd == "align":
        words = align(a.voice_dir)
        print(f"{len(words)} words, {words[0]['s']:.2f}-{words[-1]['e']:.2f} s -> {Path(a.voice_dir) / 'words.json'}")
    else:
        script = json.loads(Path(a.script or Path(a.voice_dir) / "script.json").read_text())
        ref = " ".join(l["say"] for l in script["lines"])
        hyp = " ".join(w["w"] for w in json.loads((Path(a.voice_dir) / "words.json").read_text()))
        print(f"WER {wer(ref, hyp):.1%}")


if __name__ == "__main__":
    main()
