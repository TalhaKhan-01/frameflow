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

from frameflow import build, captions, media, music, scene_plan, voice

ROOT = Path(__file__).resolve().parent.parent
LANE_MOOD = {"global-tech": "upbeat", "ai-news": "news", "india-tech": "warm", "how-tech-works": "curious",
             "dev-tools": "calm-tech", "ai-money": "tense"}
MUSIC_DB = -8    # bed gain before ducking; aim: music about 15-20 dB under the voice
SFX_DB = -16
TARGET_LUFS, TRUE_PEAK = -14.0, -1.5


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


def render(plan_path, out_dir=None, quality="looks", mood=None):
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
    word_error = captions.wer(" ".join(l["say"] for l in script["lines"]), " ".join(w["w"] for w in words))
    proj, total = build.project(plan, out / "project", vdir)
    raw = build.render(proj, out / "raw.mp4", quality)
    mood = mood or plan.get("music", {}).get("mood") or LANE_MOOD.get(plan["lane"], "calm-tech")
    starts = [s for s, _ in build.timings(plan, vdir)]
    final = mix(raw, out / "final.mp4", vdir, mood, starts, total)
    rows = ledger_rows(plan, mood, ["whoosh-short"] * (len(starts) > 1), proj)
    (out / "assets.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    report = {"id": plan["id"], "final": str(final), "seconds": round(media.duration(final), 2), "lufs": media.loudness(final),
              "voice_lufs": info["lufs"], "music_lufs_premix": media.loudness(out / "music-stem.wav"), "words": len(words), "wer": round(word_error, 4), "mood": mood, "quality": quality}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return report
