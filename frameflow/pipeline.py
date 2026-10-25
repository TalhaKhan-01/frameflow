"""One command from scene plan to finished Short.

    frameflow render <plan.json> [--out out/<id>] [--quality looks|delivery] [--mood MOOD]

Steps: validate → voice (Kokoro) → word timings (Whisper) → HyperFrames project with captions → render →
music bed + transition sounds, ducked under the voice → loudness to -14 LUFS → asset ledger.
Writes out/<id>/: script.json, voice/, project/, raw.mp4, final.mp4, assets.json, report.json.
"""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from frameflow import build, captions, media, music, scene_plan, sound, voice

ROOT = Path(__file__).resolve().parent.parent
LANE_MOOD = {"global-tech": "upbeat", "ai-news": "news", "india-tech": "warm", "how-tech-works": "curious",
             "dev-tools": "calm-tech", "ai-money": "tense"}
MUSIC_DB = -8    # bed gain before ducking; aim: music about 15-20 dB under the voice
SFX_DB = -16
TARGET_LUFS, TRUE_PEAK = -14.0, -2.0   # -2 leaves room for AAC overshoot (measured -0.9 dBTP at -1.5)


def ledger_rows(plan, mood, sfx_used, project_dir=None):
    lib = {r["file"]: r for r in json.loads((music.LIBRARY / "ledger.json").read_text())}
    rows = [{"asset": "voice", "source": "Kokoro-82M text-to-speech, generated locally", "licence": "Apache-2.0 model; output is ours",
             "url": "https://github.com/thewh1teagle/kokoro-onnx", "author": "Frameflow"},
            {"asset": "fonts", "source": "Space Grotesk, Inter, JetBrains Mono (bundled)", "licence": "OFL-1.1",
             "url": "https://fontsource.org", "author": "font authors"},
            {"asset": "music", **lib[f"music/bed-{mood}.wav"]}]
    rows += [{"asset": "sfx", **lib[f"sfx/{name}.wav"]} for name in sorted(set(sfx_used))]
    for i, s in enumerate(plan["scenes"]):
        for a in s.get("assets", []):  # scene-specific assets declared in the plan carry their own ledger rows
            rows.append({"asset": f"scene {i}", **a})
    manifest = Path(project_dir or "") / "assets-manifest.json"
    if project_dir and manifest.exists():    # assets the build step created (page snapshots)
        rows += json.loads(manifest.read_text())
    return rows


def mix(raw, out, voice_dir, mood, scene_starts, total):
    """Mix voice (already in raw.mp4) with a ducked music bed and a whoosh at each scene change, then loudnorm."""
    work = Path(out).parent
    bed = music.write_wav(work / "bed.wav", music.bed(mood, total + 1))
    starts = [s for s in scene_starts[1:]]
    inputs = ["-i", str(raw), "-i", str(bed)]
    whoosh = music.LIBRARY / "sfx" / "whoosh-short.wav"
    for _ in starts:
        inputs += ["-i", str(whoosh)]
    parts = [f"[1:a]volume={MUSIC_DB}dB,atrim=0:{total:.3f}[bed]",
             "[0:a]asplit=2[vo][key]",
             "[bed][key]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=350,asplit=2[ducked][musicstem]"]
    mixed = ["[vo]", "[ducked]"]
    for i, s in enumerate(starts):
        lab = f"[w{i}]"
        parts.append(f"[{i + 2}:a]volume={SFX_DB}dB,adelay={int(max(s - 0.15, 0) * 1000)}|{int(max(s - 0.15, 0) * 1000)}{lab}")
        mixed.append(lab)
    parts.append("".join(mixed) + f"amix=inputs={len(mixed)}:normalize=0:duration=first[premix]")
    graph = ";".join(parts)
    pre = work / "premix.wav"
    media.ffmpeg(*inputs, "-filter_complex", graph, "-map", "[premix]", "-ar", "48000", pre,
                 "-map", "[musicstem]", "-ar", "48000", work / "music-stem.wav")
    # two-pass loudness normalisation to the platform target
    r = subprocess.run([media.FFMPEG, "-hide_banner", "-i", str(pre), "-af",
                        f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK}:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):])
    norm = (f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    media.ffmpeg("-i", str(raw), "-i", str(pre), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", norm,
                 "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out)
    return out


VOICE_DUCK_DB = 7    # music dips this much more while the voice speaks (on top of the energy gain)


def duck_envelope(vo, sr=sound.SR):
    """0..1 'voice present' envelope from the voice's RMS (20 ms windows, 60 ms attack, 300 ms release)."""
    w = int(0.02 * sr)
    n = len(vo) // w
    rms = np.sqrt((vo[: n * w].reshape(n, w) ** 2).mean(1))
    on = (rms > 0.02).astype(np.float32)
    env = np.zeros(n, np.float32)
    a, r = 1 - np.exp(-1 / 3), 1 - np.exp(-1 / 15)
    acc = 0.0
    for i in range(n):
        acc += (a if on[i] > acc else r) * (on[i] - acc)
        env[i] = acc
    out = np.repeat(env, w) if n else np.zeros(0, np.float32)
    return np.pad(out, (0, max(len(vo) - len(out), 0)), mode="edge" if len(out) else "constant")[: len(vo)]


def cap_peaks(x, ceiling, sr=sound.SR):
    """Gain-reduce only around peaks above `ceiling` (10 ms look-around, 80 ms release), so hits keep their punch
    without poking out over the voice (Black October measured SFX at -0.1 dBFS against a -4.3 dBFS voice)."""
    if ceiling <= 0 or float(np.abs(x).max()) <= ceiling:
        return x
    level = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    g = np.minimum(1.0, ceiling / np.maximum(level, 1e-9))
    w = max(int(0.01 * sr), 1)   # each 10 ms block takes its deepest reduction, so the attack lands before the peak
    padded = np.pad(g, (0, (-len(g)) % w), constant_values=1.0)
    g = padded.reshape(-1, w).min(axis=1).repeat(w)[: len(g)]
    rel = 1 - np.exp(-1 / (0.08 * sr))
    out, acc = np.empty_like(g), 1.0
    for i, v in enumerate(g):   # instant attack, smooth release
        acc = v if v < acc else acc + rel * (v - acc)
        out[i] = acc
    return x * (out[:, None] if x.ndim == 2 else out)


def mix_v2(raw, out, voice_dir, plan, slots, total, sheet):
    """Voice + score (energy-automated, ducked under speech) + sound-effect cue sheet, then two-pass loudnorm."""
    work = Path(out).parent
    vo = sound.load(Path(voice_dir) / "voice.wav")
    n = int((total + 0.5) * sound.SR)
    voice_track = np.zeros((n, 2), np.float32)
    voice_track[: min(len(vo), n)] = vo[:n]
    score, tracks = sound.score(plan, slots, total)
    score = np.pad(score, ((0, max(n - len(score), 0)), (0, 0)))[:n]
    duck = 10 ** (-VOICE_DUCK_DB * duck_envelope(voice_track[:, 0]) / 20)
    sfx = sound.place_sfx(sheet, total)
    sfx = np.pad(sfx, ((0, max(n - len(sfx), 0)), (0, 0)))[:n]
    sfx = cap_peaks(sfx, float(np.abs(vo).max()) * 10 ** (-1 / 20))   # no hit louder than the voice's own peak
    pre = voice_track + score * duck[:, None] + sfx
    pre = pre / max(1.0, float(np.abs(pre).max()) / 0.95)
    music.write_wav(work / "premix.wav", pre)
    music.write_wav(work / "music-stem.wav", score * duck[:, None])
    music.write_wav(work / "sfx-stem.wav", sfx)
    r = subprocess.run([media.FFMPEG, "-hide_banner", "-i", str(work / "premix.wav"), "-af",
                        f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK}:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):])
    norm = (f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    # loudnorm's linear mode can let a short sound-effect transient through: a brickwall at -3 dBFS keeps the
    # encoded true peak under -1 dBTP (sound-effect hits measured 0.0 dBTP without it)
    media.ffmpeg("-i", str(raw), "-i", str(work / "premix.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                 "-af", norm + ",alimiter=limit=0.708:attack=1:release=60:level=disabled",
                 "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", out)
    return out, tracks


def ledger_rows_v2(plan, tracks, sheet, voice_info, project_dir):
    lib = sound.ledger()
    voice_row = ({"asset": "voice", "source": "Chatterbox TTS (Resemble AI), generated locally", "licence": "MIT model; output is ours (carries Resemble's inaudible Perth watermark)",
                  "url": "https://github.com/resemble-ai/chatterbox", "author": "Frameflow"} if voice_info.get("engine") == "chatterbox" else
                 {"asset": "voice", "source": "Kokoro-82M text-to-speech, generated locally", "licence": "Apache-2.0 model; output is ours",
                  "url": "https://github.com/thewh1teagle/kokoro-onnx", "author": "Frameflow"})
    rows = [voice_row,
            {"asset": "fonts", "source": "Fraunces, Inter, Kalam, JetBrains Mono, Space Grotesk (bundled)", "licence": "OFL-1.1", "url": "https://fontsource.org", "author": "font authors"},
            {"asset": "drawing", "source": "rough.js (hand-drawn rendering), GSAP + plugins", "licence": "MIT (rough.js); GSAP standard no-charge licence",
             "url": "https://roughjs.com", "author": "Preet Shihn; GreenSock"}]
    rows += [{"asset": "music", **lib[f"music-cc/{sound.TRACKS[t][0]}"]} for t in tracks]
    rows += [{"asset": "sfx", **lib[f"sfx2/{name}.wav"]} for name in sorted({c["name"] for c in sheet})]
    for i, s in enumerate(plan["scenes"]):
        for a in s.get("assets", []):
            rows.append({"asset": f"scene {i}", **a})
    manifest = Path(project_dir) / "assets-manifest.json"
    if manifest.exists():
        rows += json.loads(manifest.read_text())
    return rows


def render(plan_path, out_dir=None, quality="looks", mood=None, theme=None):
    plan = json.loads(Path(plan_path).read_text())
    errs = scene_plan.validate(plan)
    if errs:
        raise SystemExit("plan is not valid:\n" + "\n".join(errs))
    out = Path(out_dir or ROOT / "out" / plan["id"])
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(plan_path, out / "plan.json")
    script = build.voice_script(plan)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1))
    vdir = out / "voice"
    info = voice.tts(out / "script.json", vdir)
    shutil.copy(out / "script.json", vdir / "script.json")
    words = captions.align(vdir)
    word_error = captions.wer(voice.LAUGH.sub(" ", " ".join(l["say"] for l in script["lines"])), " ".join(w["w"] for w in words))
    proj, total = build.project(plan, out / "project", vdir, theme=theme)
    raw = build.render(proj, out / "raw.mp4", quality)
    slots = build.timings(plan, vdir)
    if plan.get("version", 1) >= 2:
        sheet = json.loads((proj / "sfx.json").read_text())
        final, tracks = mix_v2(raw, out / "final.mp4", vdir, plan, slots, total, sheet)
        rows = ledger_rows_v2(plan, tracks, sheet, info, proj)
        mood = "+".join(tracks) or "none"
    else:
        mood = mood or plan.get("music", {}).get("mood") or LANE_MOOD.get(plan["lane"], "calm-tech")
        starts = [s for s, _ in slots]
        final = mix(raw, out / "final.mp4", vdir, mood, starts, total)
        rows = ledger_rows(plan, mood, ["whoosh-short"] * (len(starts) > 1), proj)
    (out / "assets.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    cover_at = None
    for s, (st, _) in zip(plan["scenes"], slots):   # the end card opens as the cover: save that frame as the thumbnail
        if s["type"] == "endcard":
            cover_at = round(st + s["data"].get("coverAt", 0.7), 3)
            media.ffmpeg("-ss", f"{cover_at:.3f}", "-i", str(final), "-frames:v", "1", out / "cover.png")
    report = {"id": plan["id"], "final": str(final), "cover": str(out / "cover.png") if cover_at else None, "cover_at": cover_at, "seconds": round(media.duration(final), 2), "lufs": media.loudness(final),
              "voice_lufs": info["lufs"], "voice_engine": info.get("engine"), "wpm": info.get("wpm"),
              "music_lufs_premix": media.loudness(out / "music-stem.wav"), "words": len(words), "wer": round(word_error, 4), "mood": mood, "quality": quality}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return report
