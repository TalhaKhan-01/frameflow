// Frameflow Studio: a read-only window on the daily pipeline. Open mode (`frameflow web open`): the snapshot is
// plain data/studio.json and shows at once. Locked mode (`frameflow web lock`): data/studio.enc is AES-GCM
// encrypted by `frameflow web export`; the PIN derives the key (PBKDF2-SHA256) here in the browser.
import "./style.css";

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
      <p class="kicker">Frameflow · Studio edition</p>
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
const TABS: [string, string][] = [["today", "Today"], ["videos", "Videos"], ["cards", "Card posts"],
  ["lessons", "Lessons"], ["library", "Library"], ["build", "Build"]];

function shell(active: string, body: string) {
  const gen = data.generated;
  app.innerHTML = `
  <header class="mast">
    <div class="mast-top">
      <span>Snapshot ${esc(time(gen))}</span>
      <span class="mast-links"><a href="${REPO}" rel="noopener" class="gh" aria-label="Frameflow on GitHub">${GH_ICON}<span>GitHub</span></a>${openMode ? "" : ` · <a href="#" id="lock-btn">Lock</a>`}</span>
    </div>
    <a class="mast-title" href="#/today">The Habit Daily <span>Studio</span></a>
    <nav aria-label="Studio sections">${TABS.map(([k, l]) =>
      `<a href="#/${k}" ${k === active ? 'aria-current="page"' : ""}>${l}</a>`).join("")}</nav>
  </header>
  <main class="page">${body}</main>
  <footer class="foot">Frameflow Studio · read-only · <a href="${REPO}" rel="noopener">source on GitHub</a> · <a href="${esc(data.channels.youtube)}" rel="noopener">YouTube</a> · <a href="${esc(data.channels.instagram)}" rel="noopener">Instagram</a></footer>`;
  document.getElementById("lock-btn")?.addEventListener("click", (e) => {
    e.preventDefault(); store.clear(); data = null; location.hash = ""; lock();
  });
  window.scrollTo(0, 0);
}

const STEPS = ["topic-sent", "picked", "making", "video-sent", "queued", "posting", "posted"];
const STEP_LABEL: Record<string, string> = { "topic-sent": "Topic card", picked: "Picked", making: "Making",
  "video-sent": "Awaiting approval", "awaiting-notes": "Notes asked", queued: "Queued for 11:30", posting: "Posting",
  posted: "Posted", skipped: "Skipped", rejected: "Rejected", failed: "Stopped" };

function pill(state: string) {
  const tone = state === "posted" ? "good" : ["failed", "rejected", "needs-work"].includes(state) ? "bad" : "wait";
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
          <h3>The Short</h3>
          ${video ? `<p class="big"><a href="#/video/${encodeURIComponent(video.id)}">${esc(video.title)}</a></p>
          <p class="meta">Review ${esc(video.review_total)}/20 · QA ${video.qa_pass ? "pass" : "needs work"} · ${esc(r.revisions)} revision${r.revisions === 1 ? "" : "s"}</p>` : `<p class="meta">Not made yet.</p>`}
          <p class="meta">${r.post_at ? `Posts ${esc(time(r.post_at))}` : r.posted_at ? `Posted ${esc(time(r.posted_at))}` : "Posts at 11:30 after approval"}</p>
          ${links(r.links)}
          ${card ? `<h3>Card post</h3><p class="meta">${esc(card.title ?? card.id)} · ${pill(card.state)}</p>` : ""}
        </section>
      </div>
    </article>`;
  }).join("");
  const posted = data.videos.filter((v: Any) => v.status === "posted").length;
  shell("today", `
    <section class="lead">
      <p class="kicker">Today's edition</p>
      <h1>Picked at 15:00, made by 17:00,<br/>posted at <em>11:30</em>.</h1>
      <div class="figures">
        <div><b>${data.ideas}</b><span>ideas collected</span></div>
        <div><b>${data.videos.length}</b><span>Shorts made</span></div>
        <div><b>${posted}</b><span>posted</span></div>
        <div><b>${data.lessons.filter((x: Any) => x.status === "active").length}</b><span>active lessons</span></div>
      </div>
    </section>
    ${body || '<p class="meta">No daily runs yet.</p>'}`);
}

function videos() {
  shell("videos", `
    <section class="lead"><p class="kicker">Every Short so far</p><h1>Videos</h1></section>
    <div class="grid">${data.videos.map((v: Any) => `
      <a class="vcard" href="#/video/${encodeURIComponent(v.id)}">
        ${v.media?.cover ? `<img src="/${esc(v.media.cover)}" alt="" loading="lazy" width="360" height="640" />`
          : `<div class="ph"><span class="hand">${v.status === "posted" ? "" : "not public yet"}</span></div>`}
        <div class="vbody">
          <p class="meta">${esc(v.lane)} · ${esc(day(v.created))}</p>
          <h3>${esc(v.title)}</h3>
          <p>${pill(v.status)} <span class="meta">review ${esc(v.review_total ?? "–")}/20</span></p>
        </div>
      </a>`).join("")}</div>`);
}

const ROWS: Record<string, string> = { hook: "Hook", story: "Story", persona_humour: "Habit's humour",
  visual_storytelling: "Visual storytelling", pacing: "Pacing", sound_plan: "Sound plan", captions: "Captions",
  sources: "Sources", honesty: "Honesty", ending: "Ending", flow: "Flow" };

function video(id: string) {
  const v = data.videos.find((x: Any) => x.id === id);
  if (!v) return videos();
  const gates = Object.entries(v.gates ?? {}) as [string, Any][];
  const scores = Object.entries(v.scores ?? {}) as [string, number][];
  shell("videos", `
    <p class="back"><a href="#/videos">← All videos</a></p>
    <article class="vpage">
      <div class="vmedia">
        ${v.media?.video ? `<video controls playsinline preload="metadata" poster="/${esc(v.media.cover)}" src="/${esc(v.media.video)}"></video>`
          : `<div class="ph tall"><span class="hand">Shown here once it's posted</span></div>`}
        ${links(v.links)}
      </div>
      <div class="vinfo">
        <p class="kicker">${esc(v.lane)} · ${esc(day(v.created))}</p>
        <h1>${esc(v.yt_title ?? v.title)}</h1>
        <p>${pill(v.status)}</p>
        <div class="figures small">
          <div><b>${v.seconds ? Math.round(v.seconds) + " s" : "–"}</b><span>length</span></div>
          <div><b>${esc(v.lufs ?? "–")}</b><span>LUFS</span></div>
          <div><b>${esc(v.wpm ?? "–")}</b><span>words/min</span></div>
          <div><b>${esc(v.review_total ?? "–")}<small>/20</small></b><span>review</span></div>
        </div>
        <h2>Automatic checks</h2>
        <table class="gates"><tbody>${gates.map(([k, g]) =>
          `<tr><td>${g.pass ? '<span class="tick" aria-label="pass">✓</span>' : '<span class="cross" aria-label="fail">✗</span>'}</td><th>${esc(k)}</th><td>${esc(g.detail)}</td></tr>`).join("")}</tbody></table>
        ${v.warnings?.length ? `<p class="meta">Warnings: ${v.warnings.map(esc).join("; ")}</p>` : ""}
        <h2>Model review</h2>
        <ul class="scores">${scores.map(([k, s]) =>
          `<li><span>${esc(ROWS[k] ?? k)}</span><i class="bar"><i style="width:${(s / 2) * 100}%"></i></i><b>${s}/2</b></li>`).join("")}</ul>
        ${v.fixes?.length ? `<details><summary>${v.fixes.length} fix${v.fixes.length === 1 ? "" : "es"} the reviewer asked for</summary>${v.fixes.map((f: Any) =>
          `<p><b>${esc(ROWS[f.row] ?? f.row)}:</b> ${esc(f.fix)}</p>`).join("")}</details>` : ""}
      </div>
    </article>
    ${v.media?.keyframes ? `<section><h2>Keyframes</h2><img class="strip" src="/${esc(v.media.keyframes)}" alt="Keyframes from the Short" loading="lazy" /></section>` : ""}
    ${v.script?.length ? `<section class="script"><h2>What Habit says</h2>${v.script.map((l: string) => `<p>${esc(l)}</p>`).join("")}</section>` : ""}`);
}

function cards() {
  shell("cards", `
    <section class="lead"><p class="kicker">Carousel posts from the same brief</p><h1>Card posts</h1></section>
    ${data.cards.map((c: Any) => `
    <article class="cardpost">
      <div class="run-head"><h2>${esc(c.title ?? c.id)}</h2>${pill(c.state)}</div>
      <p class="meta">${c.day ? esc(day(c.day)) : esc(day(c.created))}${c.post_at ? " · posts " + esc(time(c.post_at)) : ""}</p>
      ${c.slides?.length ? `<div class="slides" tabindex="0" aria-label="Slides">${c.slides.map((s: string, i: number) =>
        `<img src="/${esc(s)}" alt="Slide ${i + 1}" loading="lazy" width="360" height="450" />`).join("")}</div>`
        : `<ol class="slide-text">${c.slides_text.map((s: Any) =>
          `<li><b>${esc(s.stat ?? "")}</b> ${esc(s.heading)}</li>`).join("")}</ol>`}
      ${c.caption ? `<details><summary>Caption</summary><p class="pre">${esc(c.caption)}</p></details>` : ""}
      ${links(c.links)}
    </article>`).join("")}`);
}

function lessons() {
  const all: Any[] = data.lessons;
  const areas = [...new Set(all.map((l) => l.area))];
  const render = (area: string) => all.filter((l) => !area || l.area === area).map((l) => `
    <li class="${esc(l.status)}">
      <p><span class="tag">${esc(l.area)}</span> <span class="tag ${l.status === "active" ? "on" : ""}">${esc(l.status)}</span>
      <span class="meta">from ${esc(l.source)} · seen ${esc(l.seen)} · helped ${esc(l.helped)} · hurt ${esc(l.hurt)}</span></p>
      <p>${esc(l.text)}</p>
    </li>`).join("");
  shell("lessons", `
    <section class="lead"><p class="kicker">What each video taught the next one</p><h1>Lessons</h1>
      <p class="lede">Reviews, failed checks and Talha's notes become lessons. The best 8 per area go into the writer's and director's prompts.</p></section>
    <div class="filters" role="group" aria-label="Filter by area"><button data-a="" aria-pressed="true">All</button>${areas.map((a) =>
      `<button data-a="${esc(a)}" aria-pressed="false">${esc(a)}</button>`).join("")}</div>
    <ul class="lessons" id="lessons">${render("")}</ul>`);
  document.querySelectorAll<HTMLButtonElement>(".filters button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".filters button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    document.getElementById("lessons")!.innerHTML = render(b.dataset.a!);
  }));
}

function library() {
  const lib = data.library;
  const tabs: [string, string, (x: Any) => string][] = [
    ["hooks", "Unused hooks", (h) => `<li><span class="score">${esc(h.score)}</span><span>${esc(h.text)} <span class="tag">${esc(h.family)}</span></span></li>`],
    ["knowledge", "Knowledge cards", (k) => `<li><span>${esc(k.text)} <a class="meta" href="${esc(k.source)}" rel="noopener" target="_blank">source ↗</a></span></li>`],
    ["analogies", "Analogies", (a) => `<li><span>${esc(a.text)}</span></li>`],
    ["scenes", "Scene recipes", (s) => `<li><span><span class="tag">${esc(s.template)}</span> ${esc(s.text)}</span></li>`],
  ];
  shell("library", `
    <section class="lead"><p class="kicker">Reused, never imposed</p><h1>Asset library</h1>
      <p class="lede">Passing videos leave behind facts, spare hooks, analogies and scene ideas. New videos are offered matching ones, with freshness and variety rules.</p>
      <div class="figures">${tabs.map(([k, l]) => `<div><b>${lib.counts[k]}</b><span>${l.toLowerCase()}</span></div>`).join("")}</div></section>
    ${tabs.map(([k, l, f]) => `<section><h2>${l}</h2><ol class="options plain">${(lib[k] as Any[]).slice(0, 40).map(f).join("")}</ol></section>`).join("")}`);
}

function build() {
  const pd: Any[] = data.phasedoc;
  const u: Any[] = data.usage;
  const max = Math.max(1, ...u.map((x) => x.tokens));
  shell("build", `
    <section class="lead"><p class="kicker">How far the build has come</p><h1>Build progress</h1>
      <p class="lede">Every task has an acceptance test and is ticked only after it ran.</p></section>
    <ul class="phases">${pd.map((p) => `
      <li><span class="pid">${esc(p.id)}</span><span class="ptitle">${esc(p.title)}</span>
        <i class="bar wide"><i style="width:${p.total ? (p.done / p.total) * 100 : 0}%"></i><i class="part" style="width:${p.total ? (p.partial / p.total) * 100 : 0}%"></i></i>
        <b>${p.done}/${p.total}</b></li>`).join("")}</ul>
    <section><h2>Model tokens per day</h2>
      <ul class="usage">${u.map((d) => `<li><span>${esc(day(d.day))}</span><i class="bar wide"><i style="width:${(d.tokens / max) * 100}%"></i></i><b>${(d.tokens / 1000).toFixed(0)}k · ${d.calls} calls</b></li>`).join("")}</ul>
    </section>`);
}

function route() {
  if (!data) return lock();
  const [, view, arg] = location.hash.split("/");
  const views: Record<string, () => void> = { videos, cards, lessons, library, build };
  if (views[view]) views[view]();
  else if (view === "video") video(decodeURIComponent(arg ?? ""));
  else today();
}

window.addEventListener("hashchange", route);
openSnapshot().then((d) => {
  if (d) { openMode = true; data = d; route(); return; }
  const saved = store.get();
  if (saved) unlock(saved).then((x) => { data = x; route(); }).catch(() => { store.clear(); lock(); });
  else lock();
});
