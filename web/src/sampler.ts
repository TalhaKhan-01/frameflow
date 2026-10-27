// Style sampler (P16 step 1, dev only): the same office vignette, reel end card and Habit variants in every palette.
import "./sampler.css";
import { PALETTES } from "./office/palettes";
import { HABITS } from "./office/sprites";
import { W, H, EW, EH, drawScene, drawEndcard, drawHabit } from "./office/scene";

const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const root = document.getElementById("app")!;

function canvas(w: number, h: number, cls: string) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h; c.className = cls;
  return c;
}

const loops: ((t: number) => void)[] = [];

for (const pal of PALETTES) {
  const sec = document.createElement("section");
  sec.className = "pal";
  sec.style.setProperty("--bg", pal.bg);
  sec.style.setProperty("--ink", pal.slots.k);
  sec.style.setProperty("--accent", pal.slots.r);
  sec.style.setProperty("--head", `"${pal.type.head}"`);
  sec.style.setProperty("--body", `"${pal.type.body}"`);
  if (pal.id === "night") sec.style.setProperty("--ink", "#E6ECFF");
  sec.innerHTML = `
    <header>
      <h2>${pal.name}</h2>
      <p>${pal.feel}</p>
      <ul class="sw">${pal.swatches.map((c) => `<li style="background:${c}" title="${c}"><span>${c}</span></li>`).join("")}</ul>
      <p class="fonts">Type: ${pal.type.head} + ${pal.type.body}</p>
    </header>
    <div class="row">
      <figure class="vig"><div class="stage"></div><figcaption>The Booth and the Proof Desk</figcaption></figure>
      <figure class="end"><div class="phone"><div class="estage"></div>
        <div class="etext"><b>Make learning a Habit.</b><small>The Daily Habit Studio</small><i>A Thirdspace Production</i></div></div>
        <figcaption>Reel end card</figcaption></figure>
      <figure class="vars"><div class="vrow"></div><figcaption>Habit variants</figcaption></figure>
    </div>`;
  root.appendChild(sec);

  const stage = sec.querySelector(".stage")!;
  const c = canvas(W, H, "px");
  const bubble = document.createElement("div");
  bubble.className = "bubble b1";
  bubble.textContent = "Make learning a Habit.";
  const bubble2 = document.createElement("div");
  bubble2.className = "bubble b2";
  bubble2.textContent = "VERIFIED ✓";
  stage.append(c, bubble, bubble2);
  const ctx = c.getContext("2d")!;
  loops.push((t) => {
    const s = drawScene(ctx, pal, t);
    bubble.classList.toggle("on", s.onAir);
    bubble2.classList.toggle("on", (t % 1.6) / 1.6 > 0.75 || (t % 1.6) < 0.5);
  });

  const ec = canvas(EW, EH, "px");
  sec.querySelector(".estage")!.appendChild(ec);
  const ectx = ec.getContext("2d")!;
  loops.push((t) => drawEndcard(ectx, pal, t));

  const vrow = sec.querySelector(".vrow")!;
  for (const [key, h] of Object.entries(HABITS)) {
    const f = document.createElement("div");
    f.className = "var";
    const hc = canvas(16, 22, "px");
    drawHabit(hc.getContext("2d")!, pal, key);
    f.append(hc);
    f.insertAdjacentHTML("beforeend", `<span>${h.label}</span>`);
    vrow.appendChild(f);
  }
}

if (reduced) loops.forEach((f) => f(1.0));
else {
  const t0 = performance.now();
  const tick = (now: number) => { const t = (now - t0) / 1000; loops.forEach((f) => f(t)); requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}
