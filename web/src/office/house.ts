// Thirdspace House (P16): the street view of every floor, a tap to go inside one, the replay of a make (or a live
// make on the local control panel), desk cards, keyboard and touch. One canvas, drawn in logical pixels and scaled.
import "./house.css";
import { PALETTES } from "./palettes";
import { Painter } from "./sprites";
import { DESK, DESKS, FLOOR, FLOORS } from "./desks";
import { PERSON } from "./cast";
import { Player, type Timeline, type Show } from "./player";
import { EXT_W, EXT_H, BX, BW, FLOOR_RECT, CHAI_RECT, drawExterior, extStation, floorAt, liftYFor } from "./building";
import { INT_W, INT_H, FloorScene, placeAt, seatCols, seatXY } from "./interior";
import { printFx } from "./fx";

export interface MakeRef { id: string; title: string; timeline: Timeline | null; href?: string }
export interface HouseOpts {
  makes: MakeRef[];                    // newest first; the first with a timeline plays
  stats?: string[];                    // the chaiwala's gossip: a few numbers of the day
  live?: string;                       // polled every second: { running, title, timeline }
  links?: Partial<Record<"library" | "lessons" | "videos", string>>;
  night?: boolean;                     // force the lighting; default follows the clock in India
  label?: string;
}

const pal = PALETTES.find((p) => p.id === "riso")!;
const esc = (s: unknown) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
const nameOf = (d: string) => PERSON[d]?.name ?? DESK[d].label;   // the crew's names (P17.3.5)
const ease = (u: number) => (u < 0.5 ? 2 * u * u : 1 - (-2 * u + 2) ** 2 / 2);
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
function istNight(): boolean {
  const h = Number(new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", hour: "numeric", hour12: false }).format(new Date()));
  return h >= 19 || h < 6;
}
const ACTING: Record<string, string> = { type: "typing", stamp: "stamping", talk: "recording", read: "reading", watch: "screening",
  rack: "rendering", phone: "on the phone", beam: "posting", chalk: "charting", paint: "painting", wire: "on the wire", pad: "sketching",
  book: "checking", clip: "running the show", board: "storyboarding" };

type View = "ext" | "int";
interface Fit { s: number; ox: number; oy: number }
interface Trans { kind: "in" | "out" | "slide"; from: string | null; to: string | null; start: number; dur: number; dir?: number }

export function mountHouse(root: HTMLElement, opts: HouseOpts) {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  root.classList.add("house");
  root.innerHTML = `
    <div class="house-stage" tabindex="0" role="application" aria-roledescription="interactive building"
         aria-label="${esc(opts.label ?? "Thirdspace House. Arrow keys pick a floor, Enter goes inside, Escape returns to the street.")}">
      <canvas></canvas>
      <div class="house-where"><b></b><span class="house-live" hidden>LIVE · make running</span><small></small></div>
      <button class="house-street" type="button" hidden>← Street</button>
      <div class="house-tip" hidden></div>
      <div class="house-bubble" hidden></div>
      <div class="house-card" role="dialog" aria-live="polite" hidden></div>
    </div>
    <nav class="house-lift" aria-label="Floors">${FLOORS.map((f) =>
      `<button type="button" data-floor="${f.id}" aria-label="${esc(f.name)}"><span>${f.short}</span></button>`).join("")}</nav>
    <div class="house-replay">
      <button type="button" class="hr-play" aria-label="Pause">❚❚</button>
      <button type="button" class="hr-speed" aria-label="Replay speed">1×</button>
      <input class="hr-scrub" type="range" min="0" max="1000" value="0" aria-label="Replay position" />
      <span class="hr-time"></span>
      <select class="hr-make" aria-label="Which make to replay"></select>
    </div>
    <ul class="house-mirror" aria-label="Desks on view"></ul>`;
  const $ = <T extends Element>(sel: string) => root.querySelector(sel) as T;
  const stage = $<HTMLDivElement>(".house-stage"), canvas = $<HTMLCanvasElement>("canvas");
  const ctx = canvas.getContext("2d")!;
  const bubble = $<HTMLDivElement>(".house-bubble"), tip = $<HTMLDivElement>(".house-tip"), card = $<HTMLDivElement>(".house-card");
  const where = $<HTMLDivElement>(".house-where"), streetBtn = $<HTMLButtonElement>(".house-street");
  const play = $<HTMLButtonElement>(".hr-play"), speedBtn = $<HTMLButtonElement>(".hr-speed");
  const scrub = $<HTMLInputElement>(".hr-scrub"), timeEl = $<HTMLSpanElement>(".hr-time"), makeSel = $<HTMLSelectElement>(".hr-make");
  const mirror = $<HTMLUListElement>(".house-mirror"), liveBadge = $<HTMLSpanElement>(".house-live");

  const buf = (w: number, h: number) => { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; };
  const ext = buf(EXT_W, EXT_H), intA = buf(INT_W, INT_H), intB = buf(INT_W, INT_H);
  const scenes = Object.fromEntries(FLOORS.map((f) => [f.id, new FloorScene(f.id)])) as Record<string, FloorScene>;

  const makes = opts.makes.filter((m) => m.timeline && m.timeline.events.length);
  let make: MakeRef | null = makes[0] ?? null;
  let player = new Player(make?.timeline ?? null);
  let live = false;
  makeSel.innerHTML = makes.map((m) => `<option value="${esc(m.id)}">${esc(m.title)}</option>`).join("");
  makeSel.hidden = makes.length < 2;

  let view: View = "ext", floor: string | null = null, hover: string | null = null, trans: Trans | null = null;
  let t = 0, last = performance.now(), liftY = liftYFor("G"), pan = INT_W / 2, dragging = false;
  let camY = liftYFor("G"), manualAt = -1e9;   // street view: the camera follows the lift unless someone just dragged
  let ambient = new Set<string>(), ambientAt = -10, cardDesk: string | null = null;
  const night = () => opts.night ?? istNight();

  // ---------- replay state ----------
  function onSet(): Set<string> {
    if (player.has) return new Set(player.active().map((s) => s.desk));
    if (t - ambientAt > 3.5) {
      ambientAt = t;
      ambient = new Set(DESKS.filter((_, i) => (i * 7 + Math.floor(t)) % 5 === 0).map((d) => d.id));
    }
    return ambient;
  }
  const current = (): Show | null => (player.has ? player.current() : null);
  const makeFloor = () => { const c = current(); return c ? DESK[c.desk].floor : null; };
  function stampsNow() {
    if (!player.has) return [];
    return player.justEnded(2.2 * player.realRate * player.speed).map((s) => ({ desk: s.desk, pass: !!s.gate }));
  }
  function ticks() {
    if (!player.has) { scrub.style.background = ""; return; }
    const marks = player.shows.filter((s) => s.gate !== undefined).map((s) => {
      const at = (s.e / player.length) * 100;
      return `${s.gate ? "var(--h-blue)" : "var(--h-red)"} ${at}% calc(${at}% + 2px)`;
    });
    scrub.style.setProperty("--ticks", `linear-gradient(90deg, transparent 0 0, ${marks.map((m) => m + ", transparent 0").join(", ")} 100%)`);
  }
  function setMake(m: MakeRef | null) {
    make = m; player = new Player(m?.timeline ?? null); ticks(); renderMirror();
    root.classList.toggle("house--noreplay", !player.has);
    timeEl.textContent = player.has ? "" : "A quiet day at the house: no make to replay yet.";
  }
  setMake(make);

  // ---------- geometry ----------
  function fit(v: View): Fit {
    const W = canvas.width, H = canvas.height;
    const snap = (s: number) => (s >= 2 ? Math.floor(s) : s);
    if (v === "ext") {
      const s = snap(Math.min(W / 330, H / 300));
      const cx = BX + BW / 2 + 9;
      let ox = W >= EXT_W * s ? (W - EXT_W * s) / 2 : W / 2 - cx * s;
      ox = W >= EXT_W * s ? ox : Math.min(0, Math.max(W - EXT_W * s, ox));
      const oy = EXT_H * s <= H ? (H - EXT_H * s) / 2 : Math.min(0, Math.max(H - EXT_H * s, H / 2 - camY * s));
      return { s, ox, oy };
    }
    const s = snap(Math.min(H / INT_H, W / 180));
    let ox: number;
    if (W >= INT_W * s) ox = (W - INT_W * s) / 2;
    else ox = Math.min(0, Math.max(W - INT_W * s, W / 2 - pan * s));
    return { s, ox, oy: (H - INT_H * s) / 2 };
  }
  function floorZoom(id: string): Fit {
    const W = canvas.width, H = canvas.height, r = FLOOR_RECT[id];
    const s = Math.min(W / (BW + 30), H / (r.h + 20));
    return { s, ox: W / 2 - (BX + BW / 2) * s, oy: H / 2 - (r.y + r.h / 2) * s };
  }
  const mix = (a: Fit, b: Fit, u: number): Fit => ({ s: a.s + (b.s - a.s) * u, ox: a.ox + (b.ox - a.ox) * u, oy: a.oy + (b.oy - a.oy) * u });
  function toLogical(e: PointerEvent | MouseEvent): { x: number; y: number } {
    const r = canvas.getBoundingClientRect(), dpr = canvas.width / r.width;
    const f = fit(view);
    return { x: ((e.clientX - r.left) * dpr - f.ox) / f.s, y: ((e.clientY - r.top) * dpr - f.oy) / f.s };
  }
  function toScreen(x: number, y: number, f: Fit) {
    const dpr = canvas.width / canvas.clientWidth;
    return { x: (x * f.s + f.ox) / dpr, y: (y * f.s + f.oy) / dpr };
  }
  function resize() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.round(stage.clientWidth * dpr));
    canvas.height = Math.max(1, Math.round(stage.clientHeight * dpr));
  }
  const ro = new ResizeObserver(resize);
  ro.observe(stage);
  resize();

  // ---------- views ----------
  function enter(id: string) {
    closeCard();
    const from = view === "int" ? floor : null;
    if (view === "int" && floor === id) return;
    const deskHere = current() && DESK[current()!.desk].floor === id ? current()!.desk : FLOOR[id].desks[0];
    if (deskHere) { const i = FLOOR[id].desks.indexOf(deskHere); pan = seatXY(seatCols(FLOOR[id].desks.length)[i]).x + 6; } else pan = INT_W / 2;
    if (reduced) { view = "int"; floor = id; trans = null; }
    else if (view === "ext") { trans = { kind: "in", from: null, to: id, start: performance.now(), dur: 650 }; floor = id; }
    else {
      const order = FLOORS.map((f) => f.id);
      trans = { kind: "slide", from, to: id, start: performance.now(), dur: 420, dir: order.indexOf(id) < order.indexOf(from!) ? -1 : 1 };
      floor = id;
    }
    view = "int";
    afterViewChange();
  }
  function exit() {
    closeCard();
    if (view === "ext") return;
    if (!reduced) trans = { kind: "out", from: floor, to: null, start: performance.now(), dur: 550 };
    view = "ext";
    afterViewChange();
  }
  function afterViewChange() {
    streetBtn.hidden = view === "ext";
    root.dataset.view = view;
    root.querySelectorAll<HTMLButtonElement>(".house-lift button").forEach((b) => {
      if (view === "int" && b.dataset.floor === floor) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
    });
    renderMirror();
  }
  function renderMirror() {
    const desks = view === "int" && floor ? FLOOR[floor].desks : DESKS.map((d) => d.id);
    const on = onSet();
    const text = (d: string) => `${nameOf(d)} (${DESK[d].label}), ${FLOOR[DESK[d].floor].name}: ${on.has(d) ? "working" : "idle"}`;
    const have = [...mirror.querySelectorAll<HTMLButtonElement>("button[data-desk]")];
    const places = view === "int" && floor === "B";
    if (have.length === desks.length && have.every((b, i) => b.dataset.desk === desks[i]) && !!mirror.querySelector("[data-place]") === places) {
      have.forEach((b) => { const s = text(b.dataset.desk!); if (b.textContent !== s) b.textContent = s; });   // keeps keyboard focus
      return;
    }
    mirror.innerHTML = desks.map((d) => `<li><button type="button" data-desk="${d}">${esc(text(d))}</button></li>`).join("")
      + (places ? `<li><button type="button" data-place="library">Library shelves</button></li><li><button type="button" data-place="lessons">Lessons notice board</button></li>` : "");
  }

  // ---------- cards ----------
  function openCard(html: string) { card.innerHTML = `<button type="button" class="hc-close" aria-label="Close">×</button>${html}`; card.hidden = false; }
  function closeCard() { card.hidden = true; cardDesk = null; }
  function deskCard(id: string) {
    const d = DESK[id], steps = player.forDesk(id);
    cardDesk = id;
    const rows = steps.map((s) => `<li class="${s.gate === false ? "no" : s.gate ? "yes" : ""}">
        <span>${esc(s.label)}${s.fix ? ' <em>fix round</em>' : ""}</span>
        <b>${s.gate === true ? "pass" : s.gate === false ? "fix" : s.status === "failed" ? "failed" : "done"}${s.score ? ` · ${esc(s.score)}` : ""} · ${mmss(s.d)}</b>
        ${s.say ? `<q>${esc(s.say)}</q>` : ""}</li>`).join("");
    openCard(`<p class="hc-floor">${esc(FLOOR[d.floor].name)}</p><h3>${esc(nameOf(id))}</h3><p class="hc-role">${esc(d.label)}${PERSON[id] ? ` · “${esc(PERSON[id].catchphrase)}”` : ""}</p><p>${esc(d.about)}</p>
      ${make && steps.length ? `<h4>In “${esc(make.title)}”</h4><ul class="hc-steps">${rows}</ul>` : `<p class="hc-quiet">No steps for this desk in the replay.</p>`}
      ${make?.href ? `<a class="hc-link" href="${esc(make.href)}">See the video's board →</a>` : ""}`);
  }
  function placeCard(place: string) {
    const href = opts.links?.[place as "library" | "lessons"];
    openCard(`<p class="hc-floor">${esc(FLOOR.B.name)}</p><h3>${place === "library" ? "The library shelves" : "The lessons board"}</h3>
      <p>${place === "library" ? "Every drawing, sound and clip the house has made, kept for reuse." : "What each make taught the desks, read back before the next one."}</p>
      ${href ? `<a class="hc-link" href="${esc(href)}">Open the ${place} →</a>` : ""}`);
  }
  function chaiCard() {
    openCard(`<p class="hc-floor">The street</p><h3>${esc(PERSON.chaiwala.name)}</h3><p class="hc-role">Chaiwala · “${esc(PERSON.chaiwala.catchphrase)}”</p>${(opts.stats ?? ["The kettle is always on."]).map((s) => `<p>${esc(s)}</p>`).join("")}`);
  }

  // ---------- input ----------
  let downAt: { x: number; y: number; pan: number; camY: number } | null = null;
  canvas.addEventListener("pointerdown", (e) => { downAt = { x: e.clientX, y: e.clientY, pan, camY }; dragging = false; });
  canvas.addEventListener("pointermove", (e) => {
    if (downAt && (dragging || Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 5)) {
      dragging = true; tip.hidden = true;
      const f = fit(view), dpr = canvas.width / canvas.clientWidth;
      if (view === "int") pan = downAt.pan - ((e.clientX - downAt.x) * dpr) / f.s;
      else { camY = Math.max(0, Math.min(EXT_H, downAt.camY - ((e.clientY - downAt.y) * dpr) / f.s)); manualAt = performance.now(); }
      return;
    }
    const p = toLogical(e);
    if (view === "ext" && !trans) {
      hover = floorAt(p.x, p.y);
      const chai = p.x >= CHAI_RECT.x && p.x < CHAI_RECT.x + CHAI_RECT.w && p.y >= CHAI_RECT.y && p.y < CHAI_RECT.y + CHAI_RECT.h;
      canvas.style.cursor = hover || chai ? "pointer" : "";
      if (hover) {
        const on = onSet(), busy = FLOOR[hover].desks.filter((d) => on.has(d));
        tip.textContent = FLOOR[hover].name + (busy.length ? " · " + busy.map((d) => `${nameOf(d)} ${ACTING[DESK[d].action]}`).join(", ") : "");
        tip.hidden = false;
        const r = canvas.getBoundingClientRect();
        tip.style.left = `${Math.min(e.clientX - r.left + 14, r.width - 240)}px`;
        tip.style.top = `${e.clientY - r.top + 14}px`;
      } else tip.hidden = true;
    } else if (view === "int" && floor) {
      canvas.style.cursor = scenes[floor].deskAt(p.x, p.y) || placeAt(floor, p.x, p.y) ? "pointer" : "";
    }
  });
  canvas.addEventListener("pointerleave", () => { hover = null; tip.hidden = true; downAt = null; });
  canvas.addEventListener("pointerup", (e) => {
    const wasDrag = dragging; downAt = null; dragging = false;
    if (wasDrag || trans) return;
    const p = toLogical(e);
    if (view === "ext") {
      if (p.x >= CHAI_RECT.x && p.x < CHAI_RECT.x + CHAI_RECT.w && p.y >= CHAI_RECT.y && p.y < CHAI_RECT.y + CHAI_RECT.h) { chaiCard(); return; }
      const f = floorAt(p.x, p.y);
      if (f) { tip.hidden = true; enter(f); }
    } else if (floor) {
      const d = scenes[floor].deskAt(p.x, p.y);
      if (d) { deskCard(d); return; }
      const place = placeAt(floor, p.x, p.y);
      if (place) placeCard(place);
    }
  });
  stage.addEventListener("keydown", (e) => {
    const order = FLOORS.map((f) => f.id);
    if (e.key === "Escape") { if (!card.hidden) closeCard(); else exit(); e.preventDefault(); }
    else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      const dir = e.key === "ArrowUp" ? -1 : 1;
      if (view === "int" && floor) enter(order[Math.max(0, Math.min(order.length - 1, order.indexOf(floor) + dir))]);
      else {
        hover = order[Math.max(0, Math.min(order.length - 1, (hover ? order.indexOf(hover) : order.indexOf("G")) + dir))];
        camY = FLOOR_RECT[hover].y + FLOOR_RECT[hover].h / 2; manualAt = performance.now();
      }
      e.preventDefault();
    } else if (e.key === "Enter" && view === "ext" && hover) { enter(hover); e.preventDefault(); }
    else if (e.key === " ") { togglePlay(); e.preventDefault(); }
  });
  root.querySelector(".house-lift")!.addEventListener("click", (e) => {
    const b = (e.target as Element).closest<HTMLButtonElement>("button[data-floor]");
    if (b) enter(b.dataset.floor!);
  });
  streetBtn.addEventListener("click", exit);
  card.addEventListener("click", (e) => { if ((e.target as Element).closest(".hc-close")) { closeCard(); stage.focus(); } });
  mirror.addEventListener("click", (e) => {
    const b = (e.target as Element).closest<HTMLButtonElement>("button");
    if (b?.dataset.desk) deskCard(b.dataset.desk);
    if (b?.dataset.place) placeCard(b.dataset.place);
  });
  function togglePlay() {
    player.playing = !player.playing;
    play.textContent = player.playing ? "❚❚" : "▶";
    play.setAttribute("aria-label", player.playing ? "Pause" : "Play");
  }
  play.addEventListener("click", togglePlay);
  speedBtn.addEventListener("click", () => {
    player.speed = player.speed === 1 ? 2 : player.speed === 2 ? 4 : 1;
    speedBtn.textContent = `${player.speed}×`;
  });
  let scrubbing = false;
  scrub.addEventListener("input", () => { scrubbing = true; player.seek(Number(scrub.value) / 1000); });
  scrub.addEventListener("change", () => { scrubbing = false; });
  makeSel.addEventListener("change", () => setMake(makes.find((m) => m.id === makeSel.value) ?? null));

  // ---------- live (control panel) ----------
  let liveTimer = 0;
  if (opts.live) {
    const poll = async () => {
      try {
        const r = await fetch(opts.live!, { cache: "no-store" });
        const j = await r.json();
        live = !!j.running;
        liveBadge.hidden = !live;
        root.classList.toggle("house--live", live);
        if (j.timeline?.events?.length && (j.timeline.events.length !== make?.timeline?.events.length || live)) {
          const keepPlaying = player.playing;
          setMake({ id: "live", title: j.title ?? "Today's make", timeline: j.timeline, href: j.href });
          if (live) { const lastShow = player.shows[player.shows.length - 1]; player.t = lastShow.s + (lastShow.e - lastShow.s) * 0.5; player.playing = false; }
          else player.playing = keepPlaying;
        }
      } catch { /* the panel may be restarting; try again next second */ }
    };
    poll();
    liveTimer = window.setInterval(poll, 1000);
  }

  // ---------- frame ----------
  let raf = 0, mirrorAt = 0;
  function frame(now: number) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (!reduced) t += dt;
    if (!live) player.tick(dt);
    const on = onSet(), cur = current(), mf = makeFloor(), isNight = night(), stamps = stampsNow();
    const targetLift = liftYFor(mf ?? "G");
    liftY += (targetLift - liftY) * Math.min(1, dt * (reduced ? 60 : 3));
    if (now - manualAt > 6000) camY += (liftY + 10 - camY) * Math.min(1, dt * (reduced ? 60 : 2));

    // street view buffer
    const extOn = view === "ext" || trans?.kind === "in" || trans?.kind === "out";
    if (extOn) {
      const ec = ext.getContext("2d")!;
      drawExterior(new Painter(ec, pal), { t, night: isNight, on, makeFloor: mf, hover, liftY, carrying: player.has, stamps });
      printFx(ec, pal);
    }
    // inside buffers
    const drawFloor = (id: string, target: HTMLCanvasElement) => {
      const sc = scenes[id], c = target.getContext("2d")!;
      const k = { t, dt, on, makeHere: cur && DESK[cur.desk].floor === id ? cur.desk : null, night: isNight, reduced };
      sc.update(k);
      sc.draw(new Painter(c, pal), k, stamps.filter((s) => DESK[s.desk].floor === id));
      printFx(c, pal);
    };
    if (floor && (view === "int" || trans)) drawFloor(floor, intA);
    if (trans?.kind === "slide" && trans.from) drawFloor(trans.from, intB);
    if (trans?.kind === "out" && trans.from) drawFloor(trans.from, intA);

    // compose
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = view === "ext" || trans?.kind === "in" || trans?.kind === "out" ? (isNight ? pal.slots.V : pal.slots.W) : isNight ? pal.slots.d : pal.bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const blit = (src: HTMLCanvasElement, f: Fit, alpha = 1) => {
      ctx.globalAlpha = alpha;
      ctx.drawImage(src, Math.round(f.ox), Math.round(f.oy), Math.round(src.width * f.s), Math.round(src.height * f.s));
      ctx.globalAlpha = 1;
    };
    let shown: Fit = fit(view);
    if (trans) {
      const u = Math.min(1, (now - trans.start) / trans.dur), e = ease(u);
      if (trans.kind === "in" || trans.kind === "out") {
        const id = (trans.to ?? trans.from)!;
        const zoomU = trans.kind === "in" ? Math.min(1, e / 0.75) : Math.min(1, (1 - e) / 0.75);
        blit(ext, mix(fit("ext"), floorZoom(id), ease(zoomU)));
        const fade = trans.kind === "in" ? Math.max(0, (e - 0.6) / 0.4) : Math.max(0, 1 - e / 0.4);
        if (fade > 0) blit(intA, fit("int"), fade);
      } else {
        const H = canvas.height, f = fit("int");
        blit(intB, { ...f, oy: f.oy - trans.dir! * H * e });
        blit(intA, { ...f, oy: f.oy + trans.dir! * H * (1 - e) });
      }
      if (u >= 1) trans = null;
    } else blit(view === "ext" ? ext : intA, shown);

    // labels, bubble, controls
    const whereB = where.querySelector("b")!, whereS = where.querySelector("small")!;
    whereB.textContent = view === "ext" ? "Thirdspace House" : FLOOR[floor!].name;
    whereS.textContent = view === "ext" ? "Tap a floor to go inside" : floor === "B" ? "Tap the shelves or the board" : "Tap someone to see their work";
    if (cur) {
      let at: { x: number; y: number } | null = null;
      if (view === "ext") { const s = extStation(cur.desk); at = toScreen(s.x + 6, s.y - 3, shown); }
      else if (floor && DESK[cur.desk].floor === floor) { const h = scenes[floor].headOf(cur.desk); if (h) at = toScreen(h.x, h.y - 2, shown); }
      const text = cur.say ?? cur.label;
      if (at && !trans) {
        const html = `<b>${esc(nameOf(cur.desk))}</b> ${esc(text)}`;
        if (bubble.innerHTML !== html) bubble.innerHTML = html;
        bubble.hidden = false;
        const w = bubble.offsetWidth, sw = stage.clientWidth;
        bubble.style.left = `${Math.max(6, Math.min(sw - w - 6, at.x - w / 2))}px`;
        bubble.style.top = `${Math.max(48, at.y - bubble.offsetHeight - 8)}px`;
      } else bubble.hidden = true;
    } else bubble.hidden = true;
    if (player.has && !scrubbing) scrub.value = String(Math.round(player.frac * 1000));
    if (player.has) timeEl.textContent = `${mmss(player.makeSeconds())} into the make`;
    if (now - mirrorAt > 1000) { mirrorAt = now; renderMirror(); }
    raf = requestAnimationFrame(frame);
  }
  raf = requestAnimationFrame(frame);
  afterViewChange();

  return {
    enter, exit,
    destroy() { cancelAnimationFrame(raf); ro.disconnect(); clearInterval(liveTimer); root.innerHTML = ""; },
    get state() { return { view, floor, frac: player.frac, card: !card.hidden, playing: player.playing, liftFloor: makeFloor() }; },
  };
}
