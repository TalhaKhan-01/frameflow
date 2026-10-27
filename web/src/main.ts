// Frameflow Studio: a read-only window on the daily pipeline. Open mode (`frameflow web open`): the snapshot is
// plain data/studio.json and shows at once. Locked mode (`frameflow web lock`): data/studio.enc is AES-GCM
// encrypted by `frameflow web export`; the PIN derives the key (PBKDF2-SHA256) here in the browser.
import "./style.css";
import { mountHouse } from "./office/house";
import { CAST, PERSON } from "./office/cast";
import { DESK, FLOOR } from "./office/desks";
import { drawPortrait } from "./office/portrait";
import { roomHead, mountRoom } from "./office/roomkit";

type Any = any; // the snapshot is plain JSON from webexport.py
type Box = { v: number; iter: number; salt: string; iv: string; ct: string };

const app = document.getElementById("app")!;
let data: Any = null;
let openMode = false; // true when the snapshot is published without a PIN
const REPO = "https://github.com/TalhaKhan-01/frameflow";
const GH_ICON = `<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>`;

const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
const b64 = (s: string) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
const day = (s?: string) =>
  s ? new Date(s.length === 10 ? s + "T12:00:00" : s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "";
const time = (s?: string) =>
  s ? new Date(s).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

const store = {
  get: () => { try { return sessionStorage.getItem("ff-pin"); } catch { return null; } },
  set: (v: string) => { try { sessionStorage.setItem("ff-pin", v); } catch { /* private mode */ } },
  clear: () => { try { sessionStorage.removeItem("ff-pin"); } catch { /* private mode */ } },
};

async function openSnapshot(): Promise<Any | null> {
  try {
    const r = await fetch("/data/studio.json", { cache: "no-store" });
    if (!r.ok || !(r.headers.get("content-type") ?? "").includes("json")) return null; // SPA fallbacks answer with HTML
    return await r.json();
  } catch { return null; }
}

async function unlock(pin: string): Promise<Any> {
  const box: Box = await (await fetch("/data/studio.enc", { cache: "no-store" })).json();
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(pin), "PBKDF2", false, ["deriveKey"]);
  const key = await crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt: b64(box.salt), iterations: box.iter },
    base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(box.iv) }, key, b64(box.ct));
  return JSON.parse(new TextDecoder().decode(plain));
}

// ---------- lock screen ----------
function lock(message = "") {
  app.innerHTML = `
  <main class="lock">
    <div class="lock-card">
      <p class="kicker">The Daily Habit Studio · a Thirdspace Production</p>
      <h1>The newsroom<br/>behind <em>Habit</em>.</h1>
      <p class="lede">Every day a story is picked, written, drawn, voiced, checked and posted. This is where it's tracked.</p>
      <form id="pin-form" autocomplete="off">
        <label for="pin">Studio PIN</label>
        <div class="pin-row">
          <input id="pin" name="pin" type="password" inputmode="numeric" autocomplete="current-password" maxlength="12" required aria-describedby="pin-msg" />
          <button type="submit">Open</button>
        </div>
        <p id="pin-msg" class="pin-msg" role="alert">${esc(message)}</p>
      </form>
      <p class="fine">Read-only snapshot. Only videos and posts already public are shown in full.</p>
    </div>
  </main>`;
  const form = document.getElementById("pin-form") as HTMLFormElement;
  const input = document.getElementById("pin") as HTMLInputElement;
  input.focus();
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = form.querySelector("button")!;
    btn.disabled = true; btn.textContent = "Opening…";
    try {
      data = await unlock(input.value.trim());
      store.set(input.value.trim());
      route();
    } catch {
      btn.disabled = false; btn.textContent = "Open";
      (document.getElementById("pin-msg")!).textContent = "That PIN doesn't open it. Try again.";
      input.select();
    }
  });
}

// ---------- shell ----------
// the HQ's rooms (P17.3): every page is a place in the building; the nav is the lift panel
const TABS: [string, string, string][] = [["lobby", "G", "Lobby"], ["cast", "G", "The Crew"], ["videos", "3", "Screening Room"],
  ["board", "5", "Run Sheet"], ["cards", "1", "Print Shop"], ["lessons", "R", "Notice Board"], ["library", "B", "Archive"],
  ["build", "4", "Engine Room"]];
const DESK_ABOUT: Record<string, string> = {
  showrunner: "owns the run; turns a revise request into a change order", researcher: "facts and sources for the story",
  factcheck: "re-reads every source; checks the script's numbers", packaging: "title, cover line and hook promise, before writing",
  writer: "the script in Habit's voice", editor: "an independent table read of the script", director: "storyboard, beats on words, sound plan",
  narrator: "voice and timing checks on the real voice", standards: "labels, licences, on-screen numbers",
  artdirector: "empty, black and off-brand pictures", animatic: "a 12 fps draft render before the real one",
  screening: "the full screening, on the animatic", animator: "the delivery render, once", qc: "loudness, black, motion, captions",
  you: "Bade Sahab (Talha) approves, revises or rejects", publisher: "uploads and checks every post", analyst: "48 h results tied to each decision" };

function deskStrip(b: Any) {
  if (!b) return `<p class="meta">Made before the studio board (26 Oct 2026): no desk-by-desk record.</p>`;
  return `<ul class="desks">${b.desks.map((d: Any) => `<li class="desk ${d.gate === false ? "no" : d.gate === true ? "yes" : ""}">
      <b>${esc(d.label)} ${d.gate === true ? "✓" : d.gate === false ? "✗" : ""}</b>
      <span>${d.score ? esc(d.score) + " · " : ""}${d.seconds >= 60 ? Math.round(d.seconds / 60) + " min" : Math.round(d.seconds) + " s"}${d.steps > 1 ? " · ×" + d.steps : ""}</span></li>`).join("")}</ul>
    <p class="meta">${b.renders} delivery render${b.renders === 1 ? "" : "s"} · ${b.fix_rounds} fix round${b.fix_rounds === 1 ? "" : "s"} before it · ${esc(b.minutes ?? "–")} min in all</p>`;
}

let house: { destroy(): void } | null = null;
let room: { destroy(): void } | null = null;   // the room kit's floor views (P17.3.8)

function shell(active: string, body: string) {
  house?.destroy(); house = null;
  room?.destroy(); room = null;
  const gen = data.generated;
  app.innerHTML = `
  <header class="mast">
    <div class="mast-top">
      <span>Snapshot ${esc(time(gen))}</span>
      <span class="mast-links"><a href="${REPO}" rel="noopener" class="gh" aria-label="Frameflow on GitHub">${GH_ICON}<span>GitHub</span></a>${openMode ? "" : ` · <a href="#" id="lock-btn">Lock</a>`}</span>
    </div>
    <a class="mast-title" href="#/lobby">The Daily Habit <span>HQ</span></a>
    <nav class="lift" aria-label="Rooms of the HQ">${TABS.map(([k, f, l]) =>
      `<a href="#/${k}" ${k === active ? 'aria-current="page"' : ""}><i aria-hidden="true">${f}</i>${l}</a>`).join("")}</nav>
  </header>
  <main class="page">${body}</main>
  <footer class="foot">The Daily Habit Studio · Thirdspace Productions · made by Frameflow · read-only · <a href="${REPO}" rel="noopener">source on GitHub</a> · <a href="${esc(data.channels.youtube)}" rel="noopener">YouTube</a> · <a href="${esc(data.channels.instagram)}" rel="noopener">Instagram</a></footer>`;
  document.getElementById("lock-btn")?.addEventListener("click", (e) => {
    e.preventDefault(); store.clear(); data = null; location.hash = ""; lock();
  });
  room = mountRoom(app);
  window.scrollTo(0, 0);
}

const STEPS = ["topic-sent", "picked", "making", "video-sent", "queued", "posting", "posted"];
const STEP_LABEL: Record<string, string> = { "topic-sent": "Topic card", picked: "Picked", making: "Making",
  "video-sent": "Awaiting approval", "awaiting-notes": "Notes asked", queued: "Queued", posting: "Posting",
  posted: "Posted", skipped: "Skipped", rejected: "Rejected", failed: "Stopped", retired: "Retired" };

function pill(state: string) {
  const tone = state === "posted" ? "good" : state === "retired" ? "off"
    : ["failed", "rejected", "needs-work"].includes(state) ? "bad" : "wait";
  return `<span class="pill ${tone}">${esc(STEP_LABEL[state] ?? state.replace(/-/g, " "))}</span>`;
}

function links(l: Record<string, string> = {}) {
  const items = Object.entries(l).filter(([, u]) => typeof u === "string" && u.startsWith("http"));
  return items.length ? `<p class="links">${items.map(([k, u]) => `<a href="${esc(u)}" rel="noopener" target="_blank">${esc(k)} ↗</a>`).join("")}</p>` : "";
}

// ---------- views ----------
function today() {
  const runs: Any[] = data.runs;
  const cards: Any[] = data.cards;
  const body = runs.map((r) => {
    const at = Math.max(0, STEPS.indexOf(r.state === "awaiting-notes" ? "video-sent" : r.state));
    const card = cards.find((c) => c.day === r.day);
    const video = data.videos.find((v: Any) => v.id === r.video_id);
    return `
    <article class="run">
      <div class="run-head">
        <h2>${esc(day(r.day))} <small>${esc(r.lane)} lane</small></h2>
        ${pill(r.state)}
      </div>
      <ol class="steps" aria-label="Run progress">${STEPS.map((s, i) =>
        `<li class="${i < at ? "done" : i === at ? "now" : ""}">${esc(STEP_LABEL[s])}</li>`).join("")}</ol>
      <div class="cols">
        <section>
          <h3>Topic card</h3>
          <ol class="options">${r.options.map((o: Any, i: number) =>
            `<li class="${r.pick === i + 1 ? "picked" : ""}"><span class="score">${esc(o.score)}</span><span>${esc(o.title)}${r.pick === i + 1 ? ' <b class="hand">picked</b>' : ""}</span></li>`).join("")}</ol>
        </section>
        <section>
          <h3>The video</h3>
          ${video ? `<p class="big"><a href="#/video/${encodeURIComponent(video.id)}">${esc(video.title)}</a></p>
          <p class="meta">Review ${esc(video.review_total)}/20 · QA ${video.qa_pass ? "pass" : "needs work"} · ${esc(r.revisions)} revision${r.revisions === 1 ? "" : "s"}</p>` : `<p class="meta">Not made yet.</p>`}
          <p class="meta">${r.post_at ? `Posts ${esc(time(r.post_at))}` : r.posted_at ? `Posted ${esc(time(r.posted_at))}` : "Posts after approval"}</p>
          ${links(r.links)}
          ${card ? `<h3>Card post</h3><p class="meta">${esc(card.title ?? card.id)} · ${pill(card.state)}</p>` : ""}
        </section>
      </div>
    </article>`;
  }).join("");
  const posted = data.videos.filter((v: Any) => v.status === "posted").length;
  const active = data.lessons.filter((x: Any) => x.status === "active").length;
  shell("lobby", `
    <section class="lead">
      <p class="kicker">The Lobby · Thirdspace House, home of The Daily Habit Studio</p>
      <h1>Every desk, <em>at work</em>.</h1>
      <p class="lede">Each floor is a desk of the board, and every desk is a person. Watch the last make climb the house from the newsroom to the roof, or tap a floor to go inside.</p>
    </section>
    ${reception()}
    <div id="house" class="house-wrap"></div>
    <section class="lead">
      <p class="kicker">Content automation</p>
      <h2 class="h1ish">One sourced brief, <em>every format</em>.</h2>
      <p class="lede">Each story becomes a video and a carousel, checked by code and by models, and approved by the owner before anything is posted.</p>
      <div class="figures">
        <div><b>${data.ideas}</b><span>ideas collected</span></div>
        <div><b>${data.videos.length}</b><span>videos made</span></div>
        <div><b>${data.cards.length}</b><span>carousels made</span></div>
        <div><b>${posted}</b><span>posted</span></div>
        <div><b>${active}</b><span>active lessons</span></div>
      </div>
    </section>
    ${body || '<p class="meta">No daily runs yet.</p>'}`);
  const makes = data.videos.filter((v: Any) => v.timeline?.events?.length)
    .map((v: Any) => ({ id: v.id, title: v.yt_title || v.title, timeline: v.timeline, href: `#/video/${encodeURIComponent(v.id)}` }));
  house = mountHouse(document.getElementById("house")!, {
    makes,
    stats: [`${data.ideas} ideas collected so far.`, `${data.videos.length} videos made, ${posted} posted.`, `${active} lessons the desks read before each make.`],
    links: { library: "#/library", lessons: "#/lessons", videos: "#/videos" },
  });
}

// ---------- the HQ (P17.3) ----------
const who = (desk: string) => PERSON[desk]?.name ?? DESK[desk]?.label ?? desk;

function reception() {   // the lobby's letter board: today's make, where it is, who came in, who is on leave
  const v = data.videos.find((x: Any) => x.board?.desks?.length && x.timeline?.events?.length);
  if (!v) return "";
  const ev: Any[] = v.timeline.events, lastDesk = ev[ev.length - 1].desk;
  const inToday = new Set<string>([...v.board.desks.filter((d: Any) => d.steps > 0).map((d: Any) => d.desk),
    ...ev.map((e: Any) => e.desk)].filter((d) => DESK[d]));
  const leave = Object.keys(DESK).filter((d) => !inToday.has(d));
  const score = v.review_total != null ? `${v.review_total}/${v.review_max ?? 22}` : "–";
  return `<section class="reception" aria-label="Reception board">
    <p class="rb-head">RECEPTION · ${esc(day(v.created))}</p>
    <dl>
      <div><dt>Today's make</dt><dd>${esc(v.yt_title || v.title)}</dd></div>
      <div><dt>Last seen</dt><dd>${esc(FLOOR[DESK[lastDesk]?.floor]?.name ?? "")} · ${esc(who(lastDesk))}</dd></div>
      <div><dt>Score</dt><dd>${esc(score)} · ${v.board.renders ?? 1} render · ${v.board.fix_rounds ?? 0} fix rounds</dd></div>
      <div><dt>In today</dt><dd>${[...inToday].map((d) => esc(who(d))).join(", ")}</dd></div>
      ${leave.length ? `<div><dt>On leave</dt><dd>${leave.map((d) => esc(who(d))).join(", ")}</dd></div>` : ""}
    </dl>
    <p class="rb-foot">${esc(PERSON.chaiwala.name)}: "${esc(PERSON.chaiwala.catchphrase)}" · <a href="#/cast">Meet the crew →</a></p>
  </section>`;
}

function street() {   // the landing: the building at the door, "Enter the Daily Habit HQ"
  house?.destroy(); house = null;
  const posted = data.videos.filter((v: Any) => v.status === "posted").length;
  app.innerHTML = `
  <main class="street">
    <section class="street-copy">
      <p class="kicker">Thirdspace Productions presents</p>
      <h1>The Daily Habit <em>HQ</em></h1>
      <p class="lede">A production house where every desk is a person: ${CAST.length} characters, from ${esc(PERSON.researcher.name)} chasing rumours to ${esc(PERSON.factcheck.name)} stamping NOPE, all making videos and carousels every day with ${esc(PERSON.narrator.name)}, ${esc(PERSON.narrator.title)}.</p>
      <a class="door" href="#/lobby">Enter the Daily Habit HQ <span aria-hidden="true">→</span></a>
      <p class="meta">${data.videos.length} videos and ${data.cards.length} carousels made · ${posted} videos posted · <a href="#/cast">meet the crew</a> · <a href="${REPO}" rel="noopener">source on GitHub</a></p>
    </section>
    <div id="house" class="house-wrap street-house"></div>
  </main>`;
  const makes = data.videos.filter((v: Any) => v.timeline?.events?.length)
    .map((v: Any) => ({ id: v.id, title: v.yt_title || v.title, timeline: v.timeline, href: `#/video/${encodeURIComponent(v.id)}` }));
  house = mountHouse(document.getElementById("house")!, {
    makes, stats: [`${data.ideas} ideas collected so far.`, `${data.videos.length} videos made, ${posted} posted.`],
    links: { library: "#/library", lessons: "#/lessons", videos: "#/videos" },
  });
  window.scrollTo(0, 0);
}

function cast() {   // staff ID cards
  const week = Date.now() - 7 * 864e5;
  const recent = data.videos.filter((v: Any) => v.board?.desks && new Date(v.created).getTime() >= week);
  const work = (id: string) => {
    const rows = recent.flatMap((v: Any) => v.board.desks.filter((d: Any) => d.desk === id && d.steps > 0));
    if (!rows.length) return "";
    const steps = rows.reduce((n: number, d: Any) => n + d.steps, 0), secs = rows.reduce((n: number, d: Any) => n + d.seconds, 0);
    const line = recent.flatMap((v: Any) => (v.timeline?.events ?? []).filter((e: Any) => e.desk === id && e.say)).map((e: Any) => e.say)[0];
    return `<p class="id-work">This week: ${steps} job${steps === 1 ? "" : "s"} on ${rows.length} video${rows.length === 1 ? "" : "s"}, ${secs >= 60 ? Math.round(secs / 60) + " min" : Math.round(secs) + " s"}${line ? `<br/><q>${esc(String(line).slice(0, 110))}</q>` : ""}</p>`;
  };
  const rival = (r: string) => PERSON[r]?.name ?? r;
  const place = (p: Any) => FLOOR[DESK[p.id]?.floor ?? p.floor]?.name ?? ({ street: "The street", awning: "The awning" } as Any)[p.floor] ?? "";
  shell("cast", `
    <section class="lead"><p class="kicker">The Crew · staff of Thirdspace House</p><h1>Every desk is <em>a person</em>.</h1>
      <p class="lede">${CAST.length - 1} people and a cat make The Daily Habit. Each desk of the board has a name, a temper and a rival, and the rivals argue on every make.</p></section>
    <ul class="idcards">${CAST.map((p) => `
      <li class="idcard${p.id === "you" ? " owner" : ""}" id="crew-${esc(p.id)}">
        <canvas data-portrait="${esc(p.id)}" width="80" height="96" role="img" aria-label="${esc(p.name)}, pixel portrait"></canvas>
        <div>
          <p class="id-title">${esc(p.title)}</p>
          <h2>${esc(p.name)}</h2>
          <p class="id-place">${esc(place(p))}${p.id === "you" ? " · the green phone" : DESK[p.id] ? ` · ${esc(DESK[p.id].label)} desk` : p.floor && !DESK[p.id] && ["2", "B", "G"].includes(p.floor) ? " · joining soon" : ""}</p>
          <p class="id-line">“${esc(p.catchphrase)}”</p>
          <p class="id-rival">Rival: ${esc(rival(p.rival))}</p>
          ${work(p.id)}
        </div>
      </li>`).join("")}</ul>`);
  document.querySelectorAll<HTMLCanvasElement>("canvas[data-portrait]").forEach((c) => drawPortrait(c, c.dataset.portrait!));
}

const SCREENING_SPEC: [string, string][] = [
  ["Modules", "`frameflow/animatic.py` (12 fps draft), `frameflow/review.py` (screening), `frameflow/qa.py` (automatic checks)"],
  ["Screening", "Opus reads a contact sheet of stills plus the script and scores 11 rows from 0 to 2; pass is 16 or more with no row at 0"],
  ["Pacing", "at least 4 visual events per 10 s, no gap over 2.5 s, a re-hook at least every 10.5 s (measured on the real voice timing)"],
  ["Audio", "integrated loudness −15 to −13 LUFS, true peak at most −1 dBTP; first word within 0.3 s"],
  ["Captions", "word error rate of the spoken words against the script under 10%"],
  ["Licences", "every asset has a source, licence, URL and author in the ledger, or the video fails"],
];

function videos() {
  shell("videos", `
    ${roomHead({ sign: "SCREENING ROOM", floor: "3", resident: "screening", title: "Every video, *screened twice*.",
      intro: "Each video is screened on the 12 fps animatic, while a fix is still a text edit, and again after the single delivery render. Code measures what can be measured; a model judges what can't.",
      spec: SCREENING_SPEC })}
    <div class="rk-cinema"><div class="grid">${data.videos.map((v: Any) => `
      <a class="vcard" href="#/video/${encodeURIComponent(v.id)}">
        ${v.media?.cover ? `<img src="/${esc(v.media.cover)}" alt="" loading="lazy" width="360" height="640" />`
          : `<div class="ph"><span class="hand">${v.status === "posted" ? "" : "not public yet"}</span></div>`}
        <div class="vbody">
          <p class="meta">${esc(v.lane)} · ${esc(day(v.created))}</p>
          <h3>${esc(v.title)}</h3>
          <p>${pill(v.status)} <span class="meta">review ${esc(v.review_total ?? "–")}/${esc(v.review_max ?? 22)}</span></p>
        </div>
      </a>`).join("")}</div></div>`);
}

const ROWS: Record<string, string> = { hook: "Hook", story: "Story", persona_humour: "Habit's humour",
  visual_storytelling: "Visual storytelling", pacing: "Pacing", sound_plan: "Sound plan", captions: "Captions",
  sources: "Sources", honesty: "Honesty", ending: "Ending", flow: "Flow" };

const stamp = (pass: boolean | null | undefined, ok = "OK", no = "FIX") =>
  pass == null ? "" : `<span class="rk-stamp ${pass ? "ok" : "fix"}">${pass ? ok : no}</span>`;

function video(id: string) {
  const v = data.videos.find((x: Any) => x.id === id);
  if (!v) return videos();
  const gates = Object.entries(v.gates ?? {}) as [string, Any][];
  const scores = Object.entries(v.scores ?? {}) as [string, number][];
  shell("videos", `
    <p class="back"><a href="#/videos">← Screening Room</a></p>
    <article class="rk-screening">
      <div class="rk-screen">
        ${v.media?.video ? `<video controls playsinline preload="metadata" poster="/${esc(v.media.cover)}" src="/${esc(v.media.video)}"></video>`
          : `<div class="ph tall"><span class="hand">Shown here once it's posted</span></div>`}
      </div>
      <div class="rk-qc">
        <p class="kicker">${esc(v.lane)} · ${esc(day(v.created))}</p>
        <h1>${esc(v.yt_title ?? v.title)}</h1>
        <p>${pill(v.status)}</p>${links(v.links)}
        <div class="rk-seats">
          <div><b>${v.seconds ? Math.round(v.seconds) + " s" : "–"}</b><span>length</span></div>
          <div><b>${esc(v.lufs ?? "–")}</b><span>LUFS</span></div>
          <div><b>${esc(v.wpm ?? "–")}</b><span>words/min</span></div>
          <div><b>${esc(v.review_total ?? "–")}<small>/${esc(v.review_max ?? 22)}</small></b><span>review</span></div>
        </div>
        <h2>Automatic checks</h2>
        <ul class="rk-checks">${gates.map(([k, g]) => `<li>${stamp(!!g.pass)}<b>${esc(k)}</b><span>${esc(g.detail)}</span></li>`).join("")}</ul>
        ${v.warnings?.length ? `<p class="meta">Warnings: ${v.warnings.map(esc).join("; ")}</p>` : ""}
      </div>
    </article>
    <div class="rk-two">
      <section class="rk-plate"><h2>Model review</h2>
        <ul class="scores">${scores.map(([k, sc]) =>
          `<li><span>${esc(ROWS[k] ?? k)}</span><i class="bar"><i style="width:${(sc / 2) * 100}%"></i></i><b>${sc}/2</b></li>`).join("")}</ul>
        ${v.fixes?.length ? `<details><summary>${v.fixes.length} fix${v.fixes.length === 1 ? "" : "es"} the reviewer asked for</summary>${v.fixes.map((f: Any) =>
          `<p><b>${esc(ROWS[f.row] ?? f.row)}:</b> ${esc(f.fix)}</p>`).join("")}</details>` : ""}
      </section>
      <section class="rk-plate"><h2>How it was made</h2>
        ${deskStrip(v.board)}${v.animatic_total != null ? `<p class="meta">Screened on the animatic before the render: ${esc(v.animatic_total)}; after: ${esc(v.review_total)}.</p>` : ""}
      </section>
    </div>
    ${v.media?.keyframes ? `<section><h2>Keyframes</h2><img class="strip" src="/${esc(v.media.keyframes)}" alt="Keyframes from the video" loading="lazy" /></section>` : ""}
    ${v.script?.length ? `<section class="script"><h2>What Habit says</h2>${v.script.map((l: string) => `<p>${esc(l)}</p>`).join("")}</section>` : ""}`);
}

function cards() {
  shell("cards", `
    ${roomHead({ sign: "PRINT SHOP", floor: "1", resident: "packaging", title: "Carousels from the *same brief*.",
      intro: "The research brief behind a video is also set as a carousel: slide 1 states the claim, every fact slide names its source, the last slide asks for the follow. It is approved on Telegram like a video.",
      spec: [
        ["Module", "`frameflow/cards.py` (topics → make → revise → post)"],
        ["Input", "a sourced brief, reused from a video, so a carousel needs no new research"],
        ["Output", "1080 × 1350 PNG slides rendered from HTML, a caption and hashtags"],
        ["Models", "Sonnet writes the slide text; code checks lengths and that every fact has a source"],
        ["Posting", "Instagram and Facebook carousels through the Graph API, with a browser fallback (The Pilot)"],
      ] })}
    ${data.cards.map((c: Any) => `
    <article class="rk-press">
      <div class="run-head"><h2>${esc(c.title ?? c.id)}</h2>${c.state === "posted" ? '<span class="rk-stamp posted">POSTED</span>' : pill(c.state)}</div>
      <p class="meta">${c.day ? esc(day(c.day)) : esc(day(c.created))}${c.post_at ? " · posts " + esc(time(c.post_at)) : ""}</p>
      ${c.slides?.length ? `<div class="rk-line" tabindex="0" aria-label="Slides">${c.slides.map((sl: string, i: number) =>
        `<img src="/${esc(sl)}" alt="Slide ${i + 1}" loading="lazy" width="360" height="450" />`).join("")}</div>`
        : `<ol class="rk-line text">${c.slides_text.map((sl: Any) =>
          `<li><b>${esc(sl.stat ?? "")}</b> ${esc(sl.heading)}</li>`).join("")}</ol>`}
      ${c.caption ? `<details><summary>Caption</summary><p class="pre">${esc(c.caption)}</p></details>` : ""}
      ${links(c.links)}
    </article>`).join("")}`);
}

function lessons() {
  const all: Any[] = data.lessons;
  const areas = [...new Set(all.map((l) => l.area))];
  const render = (area: string) => all.filter((l) => !area || l.area === area).map((l) => `
    <li class="rk-pin ${esc(l.status)}">
      <p class="rk-tags">${esc(l.area)} · ${esc(l.status)} · from ${esc(l.source)}</p>
      <p>${esc(l.text)}</p>
      <p class="meta">seen ${esc(l.seen)} · helped ${esc(l.helped)} · hurt ${esc(l.hurt)}</p>
      ${l.status === "retired" ? '<span class="rk-stamp fix">RETIRED</span>' : ""}
    </li>`).join("");
  shell("lessons", `
    ${roomHead({ sign: "NOTICE BOARD", floor: "R", resident: "analyst", title: "What each video *taught* the next.",
      intro: "After every video, its review, its failed checks and the owner's notes are distilled into general lessons. The 48-hour results then score each lesson by the videos it shaped.",
      spec: [
        ["Module", "`frameflow/lessons.py` (distil, rank, write the prompt files)"],
        ["Ledger", "`research/lessons.jsonl`: area, text, evidence, source, status, seen / helped / hurt"],
        ["Output", "the top 8 active lessons per area in `research/lessons-writer.txt` and `lessons-director.txt`, read by the writer and director as house rules"],
        ["Scoring", "`frameflow/stats48.py` ties 48 h views and engagement back to the lessons a video used"],
        ["Lifecycle", "active → promoted into a skill's rules, or retired when it stops helping"],
      ] })}
    <div class="rk-tabs" role="group" aria-label="Filter by area"><button data-a="" aria-pressed="true">All ${all.length}</button>${areas.map((a) =>
      `<button data-a="${esc(a)}" aria-pressed="false">${esc(a)}</button>`).join("")}</div>
    <ul class="rk-cork" id="lessons">${render("")}</ul>`);
  document.querySelectorAll<HTMLButtonElement>(".rk-tabs button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".rk-tabs button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    document.getElementById("lessons")!.innerHTML = render(b.dataset.a!);
  }));
}

function library() {
  const lib = data.library;
  const tabs: [string, string, (x: Any) => string][] = [
    ["hooks", "Unused hooks", (h) => `<li><span>${esc(h.text)}</span><span class="rk-k">${esc(h.family)} · ${esc(h.score)}</span></li>`],
    ["knowledge", "Knowledge cards", (k) => `<li><span>${esc(k.text)}</span><a class="rk-k" href="${esc(k.source)}" rel="noopener" target="_blank">source ↗</a></li>`],
    ["analogies", "Analogies", (a) => `<li><span>${esc(a.text)}</span></li>`],
    ["scenes", "Scene recipes", (sc) => `<li><span>${esc(sc.text)}</span><span class="rk-k">${esc(sc.template)}</span></li>`],
  ];
  const drawer = (k: string) => {
    const [, l, f] = tabs.find((t) => t[0] === k)!;
    return `<h2>${esc(l)}</h2><ol class="rk-icards">${(lib[k] as Any[]).slice(0, 40).map(f).join("")}</ol>`;
  };
  shell("library", `
    ${roomHead({ sign: "ARCHIVE", floor: "B", resident: "researcher", title: "Reused, *never imposed*.",
      intro: "Videos that pass review leave their reusable parts here: sourced facts, unused hooks, analogies and storyboard recipes. A new brief is offered matching items as optional material, never as rules.",
      spec: [
        ["Module", "`frameflow/library.py` (extract, suggest, stats)"],
        ["Store", "`research/assets/*.jsonl`, small JSON lines kept in git, each with its source video and scores"],
        ["Intake", "only videos that passed review or were posted"],
        ["Matching", "keyword overlap: serving a suggestion costs no model tokens"],
        ["Freshness", "hooks rest 30 days after use, analogies 21, scene recipes 10; facts are re-checked by the fact-checker every time"],
      ] })}
    <div class="rk-cabinet" role="group" aria-label="Drawers">${tabs.map(([k, l], i) =>
      `<button class="rk-drawer" data-k="${k}" aria-pressed="${i === 0}"><span class="rk-label">${esc(l)}</span><b>${lib.counts[k]}</b><i aria-hidden="true"></i></button>`).join("")}</div>
    <section id="drawer">${drawer("hooks")}</section>`);
  document.querySelectorAll<HTMLButtonElement>(".rk-drawer").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".rk-drawer").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    document.getElementById("drawer")!.innerHTML = drawer(b.dataset.k!);
  }));
}

function board() {
  const b: Any = data.board ?? { desks: [], videos: 0 };
  const last = data.videos.find((x: Any) => x.board?.desks?.length);
  const res = (desk: string) => last?.board.desks.find((d: Any) => d.desk === desk);
  const dur = (s: number) => (s >= 60 ? Math.round(s / 60) + " min" : Math.round(s) + " s");
  shell("board", `
    ${roomHead({ sign: "RUN SHEET", floor: "5", resident: "showrunner", title: "How a piece *is made*.",
      intro: "Each make runs as a pipeline of 17 stages. Every stage logs its result and its gate; a failed gate goes back for a bounded fix round before the delivery render, never after it. Nothing reaches the owner until the checks have run.",
      spec: [
        ["Modules", "`frameflow/board.py` runs the stages; `frameflow/progress.py` logs each step; `frameflow/daily.py` schedules the day"],
        ["Input", "a research brief: verified facts with sources, the angle and the lane"],
        ["Output", "`final.mp4` (1080 × 1920), `qa.json`, `review.json`, and an approval card on Telegram"],
        ["Fix rounds", "1 timing round (voice, captions, re-hooks) and 1 animatic round (screening, art direction, standards), from the active profile"],
        ["Renders", "one 12 fps animatic to screen, then exactly one delivery render"],
        ["Approval", "the owner approves, revises in plain words, or rejects; nothing is posted without approval"],
      ] })}
    <div class="figures small">
      <div><b>${esc(b.videos)}</b><span>videos made on the board</span></div>
      <div><b>${esc(b.one_render ?? 0)}<small>/${esc(b.videos)}</small></b><span>with one delivery render</span></div>
      <div><b>${esc(b.first_render_passed ?? 0)}<small>/${esc(b.videos)}</small></b><span>passed on that render</span></div>
      <div><b>${esc(b.animatic_within_1 ?? 0)}<small>/${esc(b.videos)}</small></b><span>animatic within 1 point of the final</span></div>
    </div>
    <div class="rk-clip">
      <h2>${last ? `Run sheet · ${esc(day(last.created))}` : "Run sheet"}</h2>
      ${last ? `<p class="meta"><a href="#/video/${encodeURIComponent(last.id)}">${esc(last.yt_title || last.title)}</a> · ${last.board.renders} render · ${last.board.fix_rounds} fix rounds · ${esc(last.board.minutes ?? "–")} min in all</p>` : ""}
      <ol class="rk-rows">${b.desks.map((d: Any, i: number) => {
        const r = res(d.desk);
        return `<li><span class="n">${String(i + 1).padStart(2, "0")}</span>
          <canvas data-portrait="${esc(d.desk)}" width="80" height="96" aria-hidden="true"></canvas>
          <span class="who"><b>${esc(who(d.desk))}</b><span>${esc(d.label)} · ${esc(DESK_ABOUT[d.desk] ?? "")}</span></span>
          <span class="st">${r?.gate != null ? stamp(r.gate, "✓ OK", "✗ FIX") : r?.steps ? '<span class="meta">done</span>' : '<span class="meta">–</span>'}</span>
          <span class="t">${r?.steps ? dur(r.seconds) + (r.steps > 1 ? " · ×" + r.steps : "") : ""}</span></li>`;
      }).join("")}</ol>
    </div>`);
}

function build() {
  const pd: Any[] = data.phasedoc;
  const u: Any[] = data.usage;
  const max = Math.max(1, ...u.map((x) => x.tokens));
  shell("build", `
    ${roomHead({ sign: "ENGINE ROOM", floor: "4", resident: "animator", title: "The engine and *the build*.",
      intro: "Everything runs on one laptop: Python services kept alive by PM2, a Telegram bot for approvals, local voice and rendering. Every model call's tokens are logged, so the cost of each piece is measured, not guessed.",
      spec: [
        ["Pipeline", "Python 3 managed with uv; this site is TypeScript + Vite, deployed to Vercel from git"],
        ["Models", "Claude Code CLI (`claude -p`) inside a Pro plan: Opus where quality is decided, Sonnet for fixes, Haiku for small jobs (`research/profiles/lean.json`)"],
        ["Voice", "Chatterbox on the GPU, Kokoro as the fallback; both local and free"],
        ["Video", "HyperFrames compositions (HTML + GSAP, seek-safe) rendered at 1080 × 1920; FFmpeg mixes and measures loudness"],
        ["Services", "PM2: the Telegram bot, the control panel, the browser for posting, this build's cockpit"],
        ["Tracking", "phasedoc: every task has an acceptance test and is ticked only after it ran"],
      ] })}
    <section class="rk-plate"><h2>Build progress</h2>
    <ul class="phases">${pd.map((p) => `
      <li><span class="pid">${esc(p.id)}</span><span class="ptitle">${esc(p.title)}</span>
        <i class="bar wide"><i style="width:${p.total ? (p.done / p.total) * 100 : 0}%"></i><i class="part" style="width:${p.total ? (p.partial / p.total) * 100 : 0}%"></i></i>
        <b>${p.done}/${p.total}</b></li>`).join("")}</ul></section>
    <section class="rk-plate"><h2>Model tokens per day</h2>
      <ul class="usage">${u.map((d) => `<li><span>${esc(day(d.day))}</span><i class="bar wide"><i style="width:${(d.tokens / max) * 100}%"></i></i><b>${(d.tokens / 1000).toFixed(0)}k · ${d.calls} calls</b></li>`).join("")}</ul>
    </section>`);
}

function route() {
  if (!data) return lock();
  const [, view, arg] = location.hash.split("/");
  const views: Record<string, () => void> = { lobby: today, today, cast, videos, board, cards, lessons, library, build };
  if (views[view]) views[view]();
  else if (view === "video") video(decodeURIComponent(arg ?? ""));
  else street();
}

window.addEventListener("hashchange", route);
openSnapshot().then((d) => {
  if (d) { openMode = true; data = d; route(); return; }
  const saved = store.get();
  if (saved) unlock(saved).then((x) => { data = x; route(); }).catch(() => { store.clear(); lock(); });
  else lock();
});
