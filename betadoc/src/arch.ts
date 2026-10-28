import "./style.css";
import "./arch.css";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";
import Lenis from "lenis";
import { ink } from "./ink";

// Architecture page (Night Edition): every diagram is SVG or DOM, animated with GSAP; reduced motion shows the end state.
gsap.registerPlugin(ScrollTrigger, MotionPathPlugin);
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const field = ink(document.getElementById("ink") as HTMLCanvasElement, reduced);
const NS = "http://www.w3.org/2000/svg";
const $ = <T extends Element = HTMLElement>(s: string) => document.querySelector<T>(s)!;
const $$ = <T extends Element = HTMLElement>(s: string) => [...document.querySelectorAll<T>(s)];
const svgEl = (tag: string, attrs: Record<string, string | number>, parent?: Element) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
  parent?.appendChild(el);
  return el;
};
const escH = (x: unknown) => String(x ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
// The shareable single file (scripts/standalone.mjs) bakes live.json and the frames in; the sites fetch and serve them.
const baked = (window as unknown as { ARCH_BAKED?: { live: unknown; frames: Record<string, string> } }).ARCH_BAKED;
const frameUrl = (n: number) => { const f = `f${String(n).padStart(2, "0")}.webp`; return baked?.frames[f] ?? `/frames/${f}`; };

// ---------- live numbers (betadoc/public/live.json, written by `frameflow web export`) ----------
type Ev = { t: number; d: number; desk: string; label: string; status: string };
(baked ? Promise.resolve(baked.live as any) : fetch("/live.json", { cache: "no-store" }).then((r) => r.json())).then((d) => {
  $$("[data-live]").forEach((el) => {
    const v = Number(d[el.dataset.live!] ?? 0);
    if (reduced) { el.textContent = v.toLocaleString("en-IN"); return; }
    const o = { n: 0 };
    gsap.to(o, { n: v, duration: 1.6, delay: 0.8, ease: "power3.out", onUpdate: () => { el.textContent = Math.round(o.n).toLocaleString("en-IN"); } });
  });
  const L = d.board?.latest;
  if (d.latest?.title) $("#tg-title").textContent = d.latest.title;
  if (L?.timeline?.events?.length) gantt(L.timeline.events as Ev[]);
}).catch(() => {});

function gantt(events: Ev[]) {
  // the make itself, up to the video card; the wait for the owner's tap and the posting are summed after it
  const cut = events.findIndex((e) => e.desk === "you");
  const make = events.slice(0, cut < 0 ? events.length : cut + 1);
  const rest = cut < 0 ? [] : events.slice(cut + 1);
  const end = Math.max(...make.map((e) => e.t + e.d));
  const fmt = (s: number) => (s >= 60 ? `${Math.round(s / 6) / 10} min` : `${Math.round(s)} s`);
  $("#gantt").innerHTML = make.map((e) => `
    <div class="g-row"><span class="g-l">${escH(e.label)}</span>
      <span class="g-track"><i class="g-bar ${e.desk === "render" ? "hot" : ""}" style="left:${(e.t / end) * 100}%;width:${Math.max(0.6, (e.d / end) * 100)}%"></i></span>
      <span class="g-d">${fmt(e.d)}</span></div>`).join("");
  let sum = `made in ${fmt(end)}`;
  if (rest.length) {
    const wait = rest[0].t - (make.at(-1)!.t + make.at(-1)!.d);
    const post = rest.reduce((a, e) => a + e.d, 0);
    sum += ` · then ${Math.round(wait / 360) / 10} h waiting for the owner · posting took ${fmt(post)}`;
  }
  $("#gantt-sum").textContent = sum;
  if (!reduced) gsap.from(".g-bar", { scaleX: 0, transformOrigin: "left", duration: 0.7, ease: "power3.out", stagger: 0.08,
    scrollTrigger: { trigger: "#gantt", start: "top 85%", once: true } });
}

// ---------- chapter rail + reading bar ----------
const links = $$<HTMLAnchorElement>(".chapters a");
const io = new IntersectionObserver((es) => es.forEach((e) => {
  if (e.isIntersecting) links.forEach((a) => a.classList.toggle("on", a.hash === "#" + e.target.id));
}), { rootMargin: "-45% 0px -50% 0px" });
$$("main > section[id]").forEach((s) => io.observe(s));
const bar = $(".read-bar i");
addEventListener("scroll", () => { const h = document.documentElement; bar.style.transform = `scaleX(${h.scrollTop / (h.scrollHeight - innerHeight || 1)})`; }, { passive: true });

// ---------- 00 map: packets ride the wires ----------
const packets = $(".map .packets");
$$<SVGPathElement>(".map .wires path").forEach((p, i) => {
  const back = p.classList.contains("back");
  const len = p.getTotalLength();
  for (let k = 0; k < (p.id === "w16" ? 1 : 2); k++) {
    const c = svgEl("circle", { r: back ? 4 : 5, class: back ? "p-back" : "p-fwd" }, packets);
    if (reduced) { const pt = p.getPointAtLength(len * (0.35 + k * 0.3)); c.setAttribute("cx", String(pt.x)); c.setAttribute("cy", String(pt.y)); continue; }
    gsap.to(c, { motionPath: { path: p, align: p, alignOrigin: [0.5, 0.5] }, duration: p.id === "w16" ? 6 : 1.4 + len / 160,
      ease: "none", repeat: -1, delay: (i * 0.37 + k * 1.1) % 3.2, immediateRender: true });
  }
});

// ---------- 01 clock: a 24 h dial, the hand follows the posting day ----------
const dial = $<SVGSVGElement>(".dial");
const R = 170, C = 200;
const pt = (h: number, r: number) => { const a = (h / 24) * Math.PI * 2 - Math.PI / 2; return [C + r * Math.cos(a), C + r * Math.sin(a)]; };
for (let h = 0; h < 24; h++) {
  const [x1, y1] = pt(h, R - (h % 6 ? 8 : 16)), [x2, y2] = pt(h, R - 2);
  svgEl("line", { x1, y1, x2, y2 }, dial.querySelector(".d-ticks")!);
}
{ // laptop on 10:00-17:00
  const [x1, y1] = pt(10, R + 10), [x2, y2] = pt(17, R + 10);
  dial.querySelector(".d-on")!.setAttribute("d", `M${x1} ${y1} A${R + 10} ${R + 10} 0 0 1 ${x2} ${y2}`);
}
for (const [h, label] of [[0, "00"], [6, "06"], [18, "18"], [14, "14:00 card"], [15, "15:00 pick"], [11.5, "11:30 post"]] as const) {
  const [x, y] = pt(h, typeof label === "string" && label.length > 2 ? R - 40 : R - 30);
  const t = svgEl("text", { x, y: y + 4, class: label.length > 2 ? "ev" : "" }, dial.querySelector(".d-marks")!);
  t.textContent = label;
}
const STEPS = [14, 15, 15.4, 17, 20, 35.5, 35.75, 83.5];   // hours from midnight of the scout day
const hand = dial.querySelector(".d-hand")!;
const states = $$("#states li");
const hourAt = (p: number) => { const f = p * (STEPS.length - 1), i = Math.min(STEPS.length - 2, Math.floor(f)); return STEPS[i] + (STEPS[i + 1] - STEPS[i]) * (f - i); };
function setClock(p: number) {
  const h = hourAt(p);
  gsap.set(hand, { rotation: (h / 24) * 360, svgOrigin: `${C} ${C}` });
  const day = Math.floor(h / 24), hh = Math.floor(h % 24), mm = Math.floor(((h % 1) * 60) / 5) * 5;
  $("#d-day").textContent = day === 0 ? "scout day" : `day +${day}`;
  $("#d-time").textContent = `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
  const on = Math.min(STEPS.length - 1, Math.round(p * (STEPS.length - 1)));
  states.forEach((s, i) => { s.classList.toggle("on", i === on); s.classList.toggle("past", i < on); });
}
setClock(0);

// ---------- 02 intake: dots stream down the source lanes, bars rank ----------
const fdots = $(".funnel .f-dots");
const bars = $(".funnel .f-bars");
for (let i = 0; i < 15; i++) {
  const w = 160 * Math.pow(0.86, i) + 14;
  svgEl("rect", { x: 780, y: 60 + i * 18, width: w, height: 11, rx: 5.5, class: i < 8 ? "top" : "" }, bars);
}
$$<SVGPathElement>(".funnel .f-lanes path").forEach((p, i) => {
  for (let k = 0; k < 4; k++) {
    const c = svgEl("circle", { r: 3.5 }, fdots);
    if (reduced) { const q = p.getPointAtLength(p.getTotalLength() * (0.2 + k * 0.2)); c.setAttribute("cx", String(q.x)); c.setAttribute("cy", String(q.y)); continue; }
    gsap.to(c, { motionPath: { path: p, align: p, alignOrigin: [0.5, 0.5] }, duration: 2.2, ease: "power1.in", repeat: -1, delay: i * 0.3 + k * 0.55, immediateRender: true });
  }
});

// ---------- 06 render: waves for the layers and the ducking panel ----------
const voiceAt = (x: number) => [[0.08, 0.3], [0.36, 0.55], [0.62, 0.9]].some(([a, b]) => x > a && x < b);
$$<SVGSVGElement>(".wave").forEach((w) => {
  const v = w.classList.contains("v");
  let d = "";
  for (let i = 0; i <= 100; i++) {
    const x = i * 2, amp = v ? (voiceAt(i / 100) ? 8 + 18 * Math.abs(Math.sin(i * 1.7) * Math.cos(i * 0.6)) : 1) : 10 + 6 * Math.sin(i * 0.25);
    d += `M${x} ${30 - amp}V${30 + amp}`;
  }
  svgEl("path", { d }, w);
});
{
  const vb = $(".duck .v-bars");
  for (let x = 100; x < 1000; x += 6) {
    const on = voiceAt((x - 100) / 900), a = on ? 6 + 26 * Math.abs(Math.sin(x * 0.11) * Math.cos(x * 0.037)) : 1;
    svgEl("rect", { x, y: 50 - a, width: 3, height: a * 2, rx: 1.5, class: on ? "on" : "" }, vb);
  }
  let d = "";
  for (let x = 100; x <= 1000; x += 5) {
    const duck = voiceAt((x - 100) / 900) ? 22 : 0;   // the bed sits 7 dB lower under the voice
    d += `${x === 100 ? "M" : "L"}${x} ${(150 + duck - 18 * Math.abs(Math.sin(x * 0.05))).toFixed(1)}`;
  }
  $(".duck .bed").setAttribute("d", d);
}

// ---------- 07 gates: twelve real frames of the latest Short under a scanner ----------
const strip = $("#strip");
strip.innerHTML = Array.from({ length: 12 }, (_, i) => `<img src="${frameUrl(1 + i * 6)}" alt="" loading="lazy" />`).join("");
const gateItems = $$("#gate-grid li");
const setGates = (p: number) => gateItems.forEach((g, i) => g.classList.toggle("on", p > (i + 0.5) / gateItems.length * 0.95));

// ---------- 09 orbit: which station the dot is passing ----------
const ring = $<SVGCircleElement>("#orbit-path");
const orbitPath = svgEl("path", { d: "M300 90 A210 210 0 1 1 300 510 A210 210 0 1 1 300 90", fill: "none" }, ring.parentElement!) as SVGPathElement;
const nodes = $$(".o-node");
const NODE_DEG = [-90, -18, 54, 126, 198];
const setOrbit = (p: number) => {
  const deg = -90 + 360 * p;
  nodes.forEach((n, i) => { const diff = Math.abs(((deg - NODE_DEG[i] + 540) % 360) - 180); n.classList.toggle("on", diff < 22); });
};

// ---------- the board's cost meter ----------
const desks = $$("#belt li");
const RENDER = desks.findIndex((d) => d.classList.contains("hot"));
function setDesk(i: number) {
  desks.forEach((d, k) => { d.classList.toggle("on", k === i); d.classList.toggle("past", k < i); });
  const fill = $("#cost-fill"), label = $("#cost-label");
  if (i < RENDER) { fill.style.transform = "scaleX(.08)"; label.textContent = "a text edit, re-voiced locally"; fill.className = ""; }
  else if (i === RENDER) { fill.style.transform = "scaleX(1)"; label.textContent = "a full re-render, so it happens once"; fill.className = "hot"; }
  else { fill.style.transform = "scaleX(1)"; label.textContent = "nothing loops now: the owner's Revise is the fix path"; fill.className = "lamp"; }
}

if (reduced) {
  setClock(1); states.forEach((s) => s.classList.add("past"));
  $$(".fact").forEach((f) => f.classList.add("ruled"));
  desks.forEach((d) => d.classList.add("past")); setDesk(RENDER);
  $$(".rd").forEach((r) => r.classList.add("on"));
  gateItems.forEach((g) => g.classList.add("on"));
  $$(".tg-msg").forEach((m) => m.classList.add("in"));
  $$(".chain li").forEach((l) => l.classList.add("on"));
  nodes.forEach((n) => n.classList.add("on"));
} else {
  const lenis = new Lenis({ lerp: 0.1 });
  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add((t) => lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
  links.forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); lenis.scrollTo(a.hash, { offset: -70 }); }));

  // staged load
  gsap.from(".a-hero .line", { yPercent: 110, opacity: 0, duration: 1.2, ease: "power3.out", stagger: 0.1, delay: 0.15 });
  gsap.from(".a-hero .lede, .a-stats > div", { y: 18, opacity: 0, duration: 0.8, ease: "power3.out", stagger: 0.06, delay: 0.5 });
  gsap.from(".map .zone", { opacity: 0, scale: 0.96, transformOrigin: "50% 50%", duration: 0.9, ease: "expo.out", stagger: 0.08, delay: 0.7 });
  gsap.from(".map .mn", { opacity: 0, y: 10, duration: 0.6, ease: "power3.out", stagger: 0.04, delay: 1.0 });
  gsap.from(".map .wires path", { strokeDashoffset: 400, strokeDasharray: 400, duration: 1.4, ease: "power2.out", stagger: 0.04, delay: 1.3,
    onComplete() { gsap.set(".map .wires path:not(.loop)", { clearProps: "strokeDasharray,strokeDashoffset" }); } });

  // the shader turns chaotic over the wire's noise, calm again once the story is picked
  ScrollTrigger.create({ trigger: ".intake", start: "top 70%", end: "bottom 30%", onToggle: (s) => field.setChaos(s.isActive ? 1 : 0) });
  gsap.from(".funnel .f-bars rect", { scaleX: 0, transformOrigin: "left", duration: 0.7, ease: "power3.out", stagger: 0.05,
    scrollTrigger: { trigger: ".funnel", start: "top 70%", once: true } });

  // facts arrive, then the checker rules on each
  const ft = gsap.timeline({ scrollTrigger: { trigger: ".facts", start: "top 70%", once: true } });
  ft.from(".fact", { y: 24, opacity: 0, duration: 0.6, ease: "power3.out", stagger: 0.12 });
  $$(".fact").forEach((f, i) => ft.add(() => f.classList.add("ruled"), 0.9 + i * 0.35));

  const mm = gsap.matchMedia();
  mm.add("(min-width: 821px)", () => {
    ScrollTrigger.create({ trigger: ".clock-sec", start: "top top", end: "+=180%", pin: ".clock-pin", scrub: 0.4, onUpdate: (s) => setClock(s.progress) });
    // the board: the belt slides under a pinned head; the desk nearest the centre is the one at work
    const belt = $("#belt"), view = $(".belt-view");
    const dist = () => belt.scrollWidth - view.clientWidth + 80;
    gsap.to(belt, { x: () => -dist(), ease: "none", scrollTrigger: { trigger: ".board-sec", start: "top top", end: () => "+=" + dist() * 1.1,
      pin: ".board-pin", scrub: 0.5, invalidateOnRefresh: true, onUpdate: (s) => setDesk(Math.min(desks.length - 1, Math.floor(s.progress * desks.length))) } });
    // render: the exploded layers fall together into one frame
    const st = gsap.timeline({ scrollTrigger: { trigger: ".render", start: "top top", end: "+=160%", pin: ".render-pin", scrub: 0.5,
      onUpdate: (s) => { const k = Math.min(5, Math.floor(s.progress * 6.4)); $$("#layers-key li").forEach((l, i) => l.classList.toggle("on", i <= k)); } } });
    st.to(".ly", { "--z": 0, duration: 1, ease: "power2.inOut", stagger: 0.04 })
      .to(".stack", { "--rx": "0deg", "--rz": "0deg", duration: 0.6, ease: "power2.inOut" }, ">-0.2")
      .to(".ly:not(.l6)", { opacity: 0, duration: 0.2 }, "<0.3")
      .to("#stack-label", { opacity: 1, y: 0, duration: 0.2 });
  });
  mm.add("(max-width: 820px)", () => {
    ScrollTrigger.create({ trigger: ".dial-wrap", start: "top 80%", end: "bottom+=600 top", scrub: 0.4, onUpdate: (s) => setClock(s.progress) });
    const dio = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setDesk(desks.indexOf(e.target as HTMLElement))),
      { rootMargin: "-45% 0px -45% 0px" });
    desks.forEach((d) => dio.observe(d));
    const st = gsap.timeline({ scrollTrigger: { trigger: ".stack-wrap", start: "top 75%", end: "bottom 30%", scrub: 0.5 } });
    st.to(".ly", { "--z": 0, duration: 1, stagger: 0.04 }).to(".stack", { "--rx": "0deg", "--rz": "0deg", duration: 0.6 })
      .to(".ly:not(.l6)", { opacity: 0, duration: 0.2 }, "<0.3").to("#stack-label", { opacity: 1, y: 0, duration: 0.2 });
    $$("#layers-key li").forEach((l) => l.classList.add("on"));
  });

  // show rundown: the playhead runs the episode once on entry
  const rds = $$(".rd");
  gsap.fromTo(".rd-head", { left: "0%" }, { left: "100%", ease: "none", duration: 5, scrollTrigger: { trigger: ".rundown", start: "top 75%", once: true },
    onUpdate() { const p = this.progress(); rds.forEach((r, i) => r.classList.toggle("on", p >= i / rds.length)); } });

  // the ducking playhead loops
  gsap.fromTo(".duck .ph", { attr: { x1: 100, x2: 100 } }, { attr: { x1: 1000, x2: 1000 }, duration: 9, ease: "none", repeat: -1 });

  // gates: the scanner sweeps the strip as the section scrolls by
  ScrollTrigger.create({ trigger: ".scan", start: "top 80%", end: "bottom 25%", scrub: 0.4, onUpdate: (s) => {
    $("#scanner").style.left = `${s.progress * 100}%`; setGates(s.progress); } });

  // publish: the card conversation plays once, then packets fan out to the three feeds
  const pt2 = gsap.timeline({ scrollTrigger: { trigger: ".tg-phone", start: "top 70%", once: true } });
  $$(".tg-msg").forEach((m, i) => pt2.add(() => m.classList.add("in"), i * 0.7));
  pt2.add(() => $(".keys .press").classList.add("hit"), 0.9);
  const fan = $(".fan .fan-dots");
  $$<SVGPathElement>(".fan path").forEach((p, i) => {
    const c = svgEl("circle", { r: 6 }, fan);
    gsap.to(c, { motionPath: { path: p, align: p, alignOrigin: [0.5, 0.5] }, duration: 1.6, ease: "power2.in", repeat: -1, repeatDelay: 0.6, delay: 3.6 + i * 0.15, immediateRender: true });
  });

  // learning loop: the dot keeps orbiting
  gsap.to(".o-dot", { motionPath: { path: orbitPath, align: orbitPath, alignOrigin: [0.5, 0.5] }, duration: 12, ease: "none", repeat: -1,
    onUpdate() { setOrbit(this.progress()); } });

  // routing columns, deploy chain
  gsap.from(".route li", { y: 16, opacity: 0, duration: 0.5, ease: "power3.out", stagger: 0.05, scrollTrigger: { trigger: "#route", start: "top 75%", once: true } });
  const chain = $$(".chain li");
  const ct = gsap.timeline({ repeat: -1, repeatDelay: 1.2, scrollTrigger: { trigger: "#chain", start: "top 80%" } });
  ct.add(() => chain.forEach((l) => l.classList.remove("on")), 0);
  chain.forEach((l, i) => ct.add(() => l.classList.add("on"), 0.2 + i * 0.6));
  ct.to({}, { duration: 1.4 });
  gsap.utils.toArray<HTMLElement>(".procs article, .repo tbody tr, .checks li, .learn-list li").forEach((el) =>
    gsap.from(el, { y: 22, opacity: 0, duration: 0.6, ease: "power3.out", scrollTrigger: { trigger: el, start: "top 90%", once: true } }));
}
