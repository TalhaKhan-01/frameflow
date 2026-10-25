// Mix the narration onto the recorded frames (betadoc skill, step 5).
// Each scene's voice clip is padded with silence to the scene's real length (build/timing.json), so the voice
// stays in sync even when a scene's actions ran longer than its line. Writes a streaming MP4 (index at the
// front), WebVTT captions from script.json, and a poster frame.
// Usage (from betadoc/):  node video/mix.mjs
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const DIR = new URL(".", import.meta.url).pathname;
const OUT = new URL("../public/video/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
const script = JSON.parse(readFileSync(DIR + "script.json", "utf8"));
const durations = JSON.parse(readFileSync(DIR + "build/durations.json", "utf8"));
const timing = JSON.parse(readFileSync(DIR + "build/timing.json", "utf8"));
const fps = timing.fps;

const inputs = ["-framerate", String(fps), "-i", DIR + "frames/%06d.jpg"];
const parts = [];
script.scenes.forEach((sc, i) => {
  const t = timing.scenes.find((s) => s.id === sc.id);
  inputs.push("-i", `${DIR}build/${String(i).padStart(2, "0")}-${sc.id}.wav`);
  parts.push(`[${i + 1}:a]aresample=48000,apad=whole_dur=${(t.frames / fps).toFixed(4)}[a${i}]`);
});
const filter = parts.join(";") + ";" + script.scenes.map((_, i) => `[a${i}]`).join("") + `concat=n=${script.scenes.length}:v=0:a=1[aout]`;

execFileSync("ffmpeg", [
  "-y", "-loglevel", "error", ...inputs,
  "-filter_complex", filter, "-map", "0:v", "-map", "[aout]",
  "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-pix_fmt", "yuv420p", "-r", String(fps),
  "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest",
  OUT + "frameflow-tour.mp4",
], { stdio: "inherit" });

const ts = (s) => {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = (s % 60).toFixed(3).padStart(6, "0");
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${sec}`;
};
let vtt = "WEBVTT\n\n";
script.scenes.forEach((sc, i) => {
  const t = timing.scenes.find((s) => s.id === sc.id);
  vtt += `${i + 1}\n${ts(t.start)} --> ${ts(t.start + durations.scenes[sc.id])}\n${sc.caption}\n\n`;
});
writeFileSync(OUT + "frameflow-tour.vtt", vtt);

execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", DIR + "frames/000150.jpg", "-vf", "scale=960:-2", "-q:v", "4", OUT + "tour-poster.jpg"]);
console.log("wrote", OUT + "frameflow-tour.mp4", "+ captions + poster");
