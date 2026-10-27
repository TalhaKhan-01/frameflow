import "./style.css";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { ink } from "./ink";
import { mountHouse, type MakeRef } from "@office/house";

gsap.registerPlugin(ScrollTrigger);
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const field = ink(document.getElementById("ink") as HTMLCanvasElement, reduced);

type Live = {
  ideas: number; videos_posted: number; lessons: number; leaves_done: number; leaves_total: number;
  today?: { day: string; lane: string; state: string };
  latest?: { title: string; seconds: number; links: Record<string, string>; gates: Record<string, boolean> };
  board?: { videos: number; one_render: number; first_render_passed: number; animatic_within_1: number;
    latest?: { title: string; renders: number; fix_rounds: number; minutes: number; animatic: number | null; final: number; max: number;
      desks: { label: string; gate: boolean | null }[]; timeline?: MakeRef["timeline"] } | null };
};
const escH = (x: unknown) => String(x ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
const STATE: Record<string, string> = { "topic-sent": "topic card out", picked: "story picked", making: "being made",
  "video-sent": "waiting for approval", "awaiting-notes": "waiting for notes", queued: "approved, posts at 11:30",
  posting: "posting now", posted: "posted", skipped: "skipped", rejected: "rejected", failed: "stopped, being fixed" };
const GATE: Record<string, string> = { length: "Length", events: "Something new every 2.5 s", rehooks: "Re-hook every 10 s",
  size: "1080×1920", loudness: "−14 LUFS", black: "No black frames", "blank-frames": "No empty frames",
  captions: "Captions match the voice", "voice-start": "Voice in the first 0.1 s", licences: "Every asset licensed" };

// ---------- live wire + counters ----------
fetch("/live.json", { cache: "no-store" }).then((r) => r.json()).then((d: Live) => {
  const t = d.today;
  const day = t ? new Date(t.day + "T12:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "";
  document.getElementById("wire-text")!.textContent = t
    ? `Live wire · ${day} · ${t.lane} lane · ${STATE[t.state] ?? t.state}` : "Live wire · no run today";
  document.querySelectorAll<HTMLElement>("[data-count]").forEach((el) => {
    const v = Number((d as Record<string, unknown>)[el.dataset.count!] ?? 0);
    if (reduced) { el.textContent = v.toLocaleString("en-IN"); return; }
    const o = { n: 0 };
    gsap.to(o, { n: v, duration: 1.6, delay: 1.1, ease: "power3.out", onUpdate: () => { el.textContent = Math.round(o.n).toLocaleString("en-IN"); } });
  });
  if (d.latest) {
    document.getElementById("latest-title")!.textContent = `Latest: ${d.latest.title} · ${Math.round(d.latest.seconds)} s`;
    const yt = d.latest.links.youtube;
    if (yt) (document.getElementById("watch-link") as HTMLAnchorElement).href = yt;
    document.getElementById("gates")!.innerHTML = Object.entries(d.latest.gates).map(([k, ok]) =>
      `<li class="${ok ? "ok" : "no"}"><span aria-hidden="true">${ok ? "✓" : "✗"}</span>${GATE[k] ?? k}<span class="sr">${ok ? " passed" : " failed"}</span></li>`).join("");
    setupGates();
  }
  const b = d.board;
  if (b && b.videos) {
    const L = b.latest;
    document.getElementById("board-live")!.innerHTML = `
      <dl class="board-figs">
        <div><dt>videos made on the board</dt><dd>${b.videos}</dd></div>
        <div><dt>with one delivery render</dt><dd>${b.one_render}/${b.videos}</dd></div>
        <div><dt>passed on that render</dt><dd>${b.first_render_passed}/${b.videos}</dd></div>
        <div><dt>animatic within 1 point of the final</dt><dd>${b.animatic_within_1}/${b.videos}</dd></div>
      </dl>${L ? `<p class="note">Latest: ${escH(L.title)}: ${L.renders} render, ${L.fix_rounds} fix round${L.fix_rounds === 1 ? "" : "s"} before it,
        screened ${escH(L.animatic ?? "–")}/${escH(L.max)} on the animatic and ${escH(L.final)}/${escH(L.max)} after.</p>
      <ul class="board-desks">${L.desks.map((x) => `<li class="${x.gate === false ? "no" : x.gate ? "ok" : ""}">${escH(x.label)}${x.gate === false ? " ✗" : x.gate ? " ✓" : ""}</li>`).join("")}</ul>` : ""}`;
  }
  houseFrom(d);
}).catch(() => { document.getElementById("wire-text")!.textContent = "Live wire · offline"; houseFrom(null); });

// ---------- Thirdspace House: the board as a building; scrolling the floor stories takes the camera inside each ----------
function houseFrom(d: Live | null) {
  const L = d?.board?.latest;
  const house = mountHouse(document.getElementById("house-stage")!, {
    makes: L?.timeline ? [{ id: "latest", title: L.title, timeline: L.timeline }] : [],
    night: true,
    stats: d ? [`${d.ideas.toLocaleString("en-IN")} ideas collected so far.`, `${d.videos_posted} Shorts posted.`, `${d.lessons} lessons the desks read before each make.`] : undefined,
    label: "Thirdspace House, replaying the latest make. Arrow keys pick a floor, Enter goes inside, Escape returns to the street.",
  });
  const items = [...document.querySelectorAll<HTMLElement>(".floors li")];
  let shown: string | null = null;
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const f = (e.target as HTMLElement).dataset.floor!;
      items.forEach((li) => li.classList.toggle("on", li === e.target));
      if (f !== shown) { shown = f; house.enter(f); }
    }
  }, { rootMargin: matchMedia("(max-width: 900px)").matches ? "-72% 0px -18% 0px" : "-45% 0px -45% 0px" });   // phones: below the sticky stage
  items.forEach((li) => io.observe(li));
  // back on the street when the floor stories are scrolled past in either direction
  new IntersectionObserver(([e]) => { if (!e.isIntersecting && shown) { shown = null; items.forEach((li) => li.classList.remove("on")); house.exit(); } })
    .observe(document.querySelector(".floors")!);
}

// ---------- hero video ----------
const video = document.getElementById("hero-video") as HTMLVideoElement;
const sound = document.getElementById("sound") as HTMLButtonElement;
if (!reduced) video.play().catch(() => {});
else video.controls = true;
sound.addEventListener("click", () => {
  video.muted = !video.muted;
  if (!video.muted) video.play().catch(() => {});
  sound.setAttribute("aria-pressed", String(!video.muted));
  sound.textContent = video.muted ? "Sound off" : "Sound on";
});

// ---------- tour (narrated demo): only one video plays at a time
const tourVideo = document.getElementById("tour-video") as HTMLVideoElement;
tourVideo.addEventListener("play", () => video.pause());
tourVideo.addEventListener("pause", () => { if (!reduced) video.play().catch(() => {}); });

// ---------- scrubbed frames (the wow moment) ----------
const N = 72;
const canvas = document.getElementById("scrub") as HTMLCanvasElement;
const ctx = canvas.getContext("2d")!;
const frames: HTMLImageElement[] = [];
let shown = -1;
function show(i: number) {
  i = Math.max(0, Math.min(N - 1, Math.round(i)));
  const img = frames[i];
  if (i === shown || !img?.complete || !img.naturalWidth) return;
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height); shown = i;
}
function loadFrames() {
  for (let i = 0; i < N; i++) {
    const img = new Image(); img.decoding = "async";
    img.src = `/frames/f${String(i + 1).padStart(2, "0")}.webp`;
    if (i === 0) img.onload = () => show(0);
    frames.push(img);
  }
}
new IntersectionObserver((e, o) => { if (e[0].isIntersecting) { loadFrames(); o.disconnect(); } }, { rootMargin: "800px" }).observe(canvas);

const stages = [...document.querySelectorAll<HTMLElement>(".stages li")];
const setStage = (p: number) => stages.forEach((s, i) => s.classList.toggle("on", i === Math.min(stages.length - 1, Math.floor(p * stages.length))));
let gateItems: HTMLElement[] = [];
function setupGates() { gateItems = [...document.querySelectorAll<HTMLElement>("#gates li")]; if (reduced) gateItems.forEach((g) => g.classList.add("on")); }
const setGates = (p: number) => gateItems.forEach((g, i) => g.classList.toggle("on", p > 0.62 + (i / gateItems.length) * 0.34));

if (reduced) {
  stages.forEach((s) => s.classList.add("on"));
} else {
  const lenis = new Lenis({ lerp: 0.1 });
  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add((t) => lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);

  // staged load
  gsap.from(".hero .line", { yPercent: 110, opacity: 0, duration: 1.2, ease: "power3.out", stagger: 0.09, delay: 0.15 });
  gsap.from(".hero .lede, .hero .ctas, .wire", { y: 18, opacity: 0, duration: 0.8, ease: "power3.out", stagger: 0.08, delay: 0.6 });
  gsap.from(".hero .phone", { y: 80, opacity: 0, rotate: 2, duration: 1.3, ease: "power3.out", delay: 0.35 });
  gsap.from(".counters > div", { y: 20, opacity: 0, duration: 0.7, ease: "power3.out", stagger: 0.07, delay: 0.9 });

  // shader mood per section
  ScrollTrigger.create({ trigger: ".problem", start: "top 70%", end: "bottom 30%", onToggle: (s) => field.setChaos(s.isActive ? 1 : 0) });

  // pinned build sequence
  const mm = gsap.matchMedia();
  mm.add("(min-width: 821px)", () => {
    ScrollTrigger.create({ trigger: ".build", start: "top top", end: "+=260%", pin: ".build-pin", scrub: true,
      onUpdate: (s) => { show(s.progress * (N - 1)); setStage(s.progress); setGates(s.progress); } });
  });
  mm.add("(max-width: 820px)", () => {
    ScrollTrigger.create({ trigger: ".scrub", start: "top 85%", end: "bottom+=900 top", scrub: true,
      onUpdate: (s) => { show(s.progress * (N - 1)); setStage(s.progress); setGates(s.progress); } });
  });

  gsap.utils.toArray<HTMLElement>(".timeline li, .road li, .deploy article, .matrix tbody tr").forEach((el) =>
    gsap.from(el, { y: 24, opacity: 0, duration: 0.6, ease: "power3.out", scrollTrigger: { trigger: el, start: "top 90%", once: true } }));
  gsap.from(".arch-svg .node", { opacity: 0, y: 10, duration: 0.5, stagger: 0.06, ease: "power3.out", scrollTrigger: { trigger: ".arch-panel", start: "top 75%", once: true } });
  gsap.from(".arch-svg .edges path", { opacity: 0, duration: 0.6, stagger: 0.04, delay: 0.4, scrollTrigger: { trigger: ".arch-panel", start: "top 75%", once: true } });
}
