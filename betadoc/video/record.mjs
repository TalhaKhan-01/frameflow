// Deterministic 60 fps capture of the live betadoc and Studio for the narrated tour (betadoc skill, step 5).
// A virtual clock is injected before any page script (rAF, performance.now, Date, timers, CSS/WAAPI animations and
// <video> playback); every frame advances it by exactly 1/60 s, waits for two real paints and takes a screenshot.
// Scenes are timed to the narration in build/durations.json; each scene gets its voice slot so moves fill it.
//
// Usage (from betadoc/):  FRAMEFLOW_WEB_PIN=... node video/record.mjs [--only <scene-id>]
// Then:                   node video/mix.mjs
import { chromium } from "playwright";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";

const argv = process.argv.slice(2);
const opt = (k, d) => (argv.includes(k) ? argv[argv.indexOf(k) + 1] : d);
const SITE = opt("--site", "https://frameflow-betadoc.vercel.app");
const STUDIO = opt("--studio", "https://frameflow-studio-tau.vercel.app");
const ONLY = opt("--only", "");
const PIN = process.env.FRAMEFLOW_WEB_PIN;
if (!PIN) { console.error("FRAMEFLOW_WEB_PIN is not set"); process.exit(2); }
const FPS = 60;
const W = 1280, H = 800;
const DIR = new URL(".", import.meta.url).pathname;
const durations = JSON.parse(readFileSync(DIR + "build/durations.json", "utf8"));
const script = JSON.parse(readFileSync(DIR + "script.json", "utf8"));
const FRAMES = DIR + "frames/";

// ---------------------------------------------------------------- virtual clock (runs before page scripts)
const CLOCK = () => {
  let now = 0;
  const epoch = 1793000000000;
  const realRAF = window.requestAnimationFrame.bind(window);
  const RealDate = Date;
  let raf = [];
  let rafId = 0;
  const timers = new Map();
  let tid = 1;
  Object.defineProperty(window, "__realRAF", { value: realRAF });
  performance.now = () => now;
  class VDate extends RealDate {
    constructor(...a) { if (a.length) super(...a); else super(epoch + now); }
    static now() { return epoch + now; }
  }
  window.Date = VDate;
  window.requestAnimationFrame = (cb) => { raf.push([++rafId, cb]); return rafId; };
  window.cancelAnimationFrame = (id) => { raf = raf.filter(([i]) => i !== id); };
  window.setTimeout = (fn, ms = 0, ...args) => { const id = tid++; timers.set(id, { at: now + Math.max(0, +ms || 0), fn, args }); return id; };
  window.setInterval = (fn, ms = 0, ...args) => { const id = tid++; timers.set(id, { at: now + Math.max(1, +ms || 0), every: Math.max(1, +ms || 0), fn, args }); return id; };
  window.clearTimeout = window.clearInterval = (id) => timers.delete(id);
  // <video>: never really plays; "playing" videos are stepped by the clock (seek per frame, loop aware).
  const playing = new Set();
  const realPause = HTMLMediaElement.prototype.pause;
  HTMLMediaElement.prototype.play = function () { realPause.call(this); playing.add(this); return Promise.resolve(); };
  HTMLMediaElement.prototype.pause = function () { playing.delete(this); realPause.call(this); };
  window.__media = () => [...playing].map((v) => v.readyState >= 2 && !v.seeking).every(Boolean);
  window.__advance = (ms) => {
    const target = now + ms;
    for (;;) {
      let next = null;
      for (const [id, t] of timers) if (t.at <= target && (!next || t.at < next[1].at)) next = [id, t];
      if (!next) break;
      const [id, t] = next;
      now = t.at;
      if (t.every) t.at += t.every; else timers.delete(id);
      try { typeof t.fn === "function" ? t.fn(...t.args) : 0; } catch (e) { console.error(e); }
    }
    now = target;
    for (const a of document.getAnimations()) {
      if (a.playState === "running") a.pause();
      if (a.playState === "paused") a.currentTime = (Number(a.currentTime) || 0) + ms;
    }
    for (const v of playing) {
      if (!v.isConnected) { playing.delete(v); continue; }
      const d = v.duration || 0;
      let t = v.currentTime + ms / 1000;
      if (d && t >= d) t = v.loop ? t % d : d;
      v.currentTime = t;
    }
    const q = raf; raf = [];
    for (const [, cb] of q) { try { cb(now); } catch (e) { console.error(e); } }
  };
  window.__cursor = (x, y, down) => {
    let c = document.getElementById("__cur");
    if (!c) {
      c = document.createElement("div");
      c.id = "__cur";
      c.style.cssText = "position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;";
      c.innerHTML = '<svg viewBox="0 0 26 26" width="26" height="26"><path d="M3 2 L3 21 L8 16 L12 24 L15.5 22.5 L11.5 14.5 L18.5 14.5 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
      document.documentElement.appendChild(c);
    }
    c.style.transform = `translate(${x - 3}px, ${y - 2}px) scale(${down ? 0.86 : 1})`;
  };
};

// ---------------------------------------------------------------- frame helpers
let frame = 0;
let page;
const cur = { x: W * 0.72, y: H * 0.6, down: false };

async function tick() {
  await page.evaluate(async ({ ms, x, y, down }) => {
    window.__advance(ms);
    window.__cursor(x, y, down);
    for (let i = 0; i < 100 && !window.__media(); i++) await new Promise((r) => window.__realRAF(r));
    await new Promise((r) => window.__realRAF(() => window.__realRAF(r)));
  }, { ms: 1000 / FPS, x: cur.x, y: cur.y, down: cur.down });
  await page.screenshot({ path: `${FRAMES}${String(frame).padStart(6, "0")}.jpg`, type: "jpeg", quality: 90 });
  frame++;
}
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const n = (sec) => Math.max(1, Math.round(sec * FPS));
async function hold(sec) { for (let i = 0, k = n(sec); i < k; i++) await tick(); }
async function moveTo(x, y, sec = 0.7) {
  const x0 = cur.x, y0 = cur.y, k = n(sec);
  for (let i = 1; i <= k; i++) {
    const e = ease(i / k);
    cur.x = x0 + (x - x0) * e; cur.y = y0 + (y - y0) * e;
    await page.mouse.move(cur.x, cur.y);
    await tick();
  }
}
async function box(locator) {
  await locator.first().waitFor({ state: "visible" });
  const b = await locator.first().boundingBox();
  return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
}
async function clickOn(locator, sec = 0.6) {
  const p = await box(locator);
  await moveTo(p.x, p.y, sec);
  cur.down = true; await tick(); await tick();
  await page.mouse.click(p.x, p.y);
  cur.down = false; await tick();
}
async function scrollTo(y1, sec = 1.2, curve = ease) {
  const y0 = await page.evaluate(() => window.scrollY), k = n(sec);
  for (let i = 1; i <= k; i++) {
    await page.evaluate((y) => window.scrollTo(0, y), y0 + (y1 - y0) * curve(i / k));
    await tick();
  }
}
const top = (sel, offset = 0) => page.evaluate(({ sel, offset }) =>
  document.querySelector(sel).getBoundingClientRect().top + window.scrollY - offset, { sel, offset });
async function settle(steps = 30) { for (let i = 0; i < steps; i++) await page.evaluate(() => window.__advance(1000 / 60)); }
async function open(url, anchor) {
  await page.goto(url, { waitUntil: "load" });
  await page.locator(anchor).first().waitFor({ state: "visible" });
  await page.evaluate(() => document.fonts.ready);
  await settle();
}
const linear = (t) => t;
// pinned build section: ScrollTrigger pins at the section's top for 2.6 viewports
const pinRange = async () => { const s = await top(".build"); return [s, s + H * 2.6]; };

// ---------------------------------------------------------------- scenes (ids match script.json)
const SCENES = {
  async intro(slot) {
    await open(SITE + "/", ".hero h1");
    await hold(Math.min(3, slot * 0.35));
    const p = await box(page.locator(".phone-frame"));
    await moveTo(p.x, p.y, 1.6);
    await hold(Math.max(0, slot - 3 - 1.6 - 1.2));
    await moveTo(W * 0.32, H * 0.82, 1.2);
  },
  async build(slot) {
    const [s, e] = await pinRange();
    await scrollTo(s, 1.6);
    await scrollTo(s + (e - s) * 0.58, Math.max(1, slot - 1.6), linear);
  },
  async checks(slot) {
    const [s, e] = await pinRange();
    await scrollTo(e - 4, Math.max(1, slot - 1.4), linear);
    await hold(1.4);
  },
  async approve(slot) {
    await scrollTo(await top(".clock", 70), 1.6);
    const end = await top(".timeline li:nth-child(4)", H * 0.45);
    await scrollTo(end, Math.max(1, slot - 2.2), linear);
    await hold(0.6);
  },
  async studio(slot) {
    await open(STUDIO + "/", "#pin");
    await hold(0.5);
    await clickOn(page.locator("#pin"), 0.7);
    for (const ch of PIN) { await page.keyboard.type(ch); await hold(0.08); }
    await clickOn(page.locator("button[type=submit]"), 0.5);
    for (let i = 0; i < 400 && !(await page.locator(".mast").count()); i++) await tick();   // PBKDF2 runs in real time
    await hold(0.8);
    const opt = await box(page.locator(".options li.picked"));
    await moveTo(opt.x - 120, opt.y, 1.2);
    await hold(Math.max(0.5, slot - 6));
    const q = await box(page.locator(".run .pill"));
    await moveTo(q.x, q.y, 0.9);
  },
  async video(slot) {
    await page.goto(STUDIO + "/#/video/2026-10-25-black-october");
    await page.locator("video").waitFor({ state: "visible" });
    await page.evaluate(() => { const v = document.querySelector("video"); v.muted = true; v.play(); });
    await settle(10);
    const v = await box(page.locator("video"));
    await moveTo(v.x, v.y, 0.8);
    await hold(Math.min(2.5, slot * 0.3));
    await scrollTo(await top(".gates", 120), 1.6);
    await hold(Math.max(0.5, (slot - 6.5) / 2));
    await scrollTo(await top(".scores", 140), 1.4);
    await hold(Math.max(0.5, (slot - 6.5) / 2));
  },
  async lessons(slot) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await settle(4);
    await clickOn(page.locator('nav a[href="#/lessons"]'), 0.8);
    await settle(10);
    await hold(1.2);
    await clickOn(page.locator('.filters button[data-a="writer"]'), 0.8);
    await hold(0.6);
    await scrollTo(260, Math.max(1, slot - 4.2));
  },
  async outro(slot) {
    await open(SITE + "/", ".hero h1");
    await page.evaluate((y) => window.scrollTo(0, y), await top(".cta", 120));
    await settle(30);
    const p = await box(page.locator(".cta .btn").first());
    await moveTo(p.x, p.y, 1.2);
    await hold(Math.max(0.5, slot - 1.2));
  },
};

// ---------------------------------------------------------------- run
if (!ONLY) rmSync(FRAMES, { recursive: true, force: true });
mkdirSync(FRAMES, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--autoplay-policy=no-user-gesture-required"] });
const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, colorScheme: "dark" });
await ctx.addInitScript(CLOCK);
page = await ctx.newPage();
page.on("pageerror", (e) => console.error("page error:", String(e)));
const pad = durations.pad ?? 0.7;
const timing = [];
for (const sc of script.scenes) {
  if (ONLY && sc.id !== ONLY) continue;
  const slot = durations.scenes[sc.id] + pad;
  const target = Math.round(slot * FPS);
  const start = frame;
  await SCENES[sc.id](slot);
  const used = frame - start;
  if (used > target) console.warn(`scene ${sc.id}: actions took ${(used / FPS).toFixed(2)} s, voice slot is ${slot.toFixed(2)} s`);
  while (frame - start < target) await tick();
  timing.push({ id: sc.id, frames: frame - start, start: start / FPS });
  console.log(`${sc.id.padEnd(10)} ${(frame - start).toString().padStart(5)} frames`);
}
await browser.close();
writeFileSync(DIR + "build/timing.json", JSON.stringify({ fps: FPS, scenes: timing }, null, 1));
console.log("frames", frame);
