// The room kit (P17.3.8): every Studio page is a room inside Thirdspace House. A room has a sign (the house sign's
// black plate and pixel letters), a live view of its floor (the HQ's own FloorScene), the crew member who runs that
// stage introducing it in plain technical terms, and a spec panel: the module, what goes in and out, the checks.
import { FloorScene, INT_W, INT_H } from "./interior";
import { PALETTES } from "./palettes";
import { Painter, textWidth } from "./sprites";
import { FLOOR } from "./desks";
import { PERSON } from "./cast";
import { printFx } from "./fx";
import { drawPortrait } from "./portrait";

const pal = PALETTES.find((p) => p.id === "riso")!;
const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

export interface RoomOpts {
  sign: string;            // pixel letters on the plate
  floor: string;           // FLOOR id, for the lift tag and the live view
  title: string;           // the heading; *word* is set in red italics
  resident: string;        // a PERSON id
  intro: string;           // what this stage does, in the resident's words (plain, technical)
  spec?: [string, string][];   // the spec panel: rows of [label, value]; `code` in backticks
}

const md = (s: string) => esc(s).replace(/\*(.+?)\*/g, "<em>$1</em>").replace(/`(.+?)`/g, "<code>$1</code>");

export function roomHead(o: RoomOpts): string {
  const p = PERSON[o.resident];
  const f = FLOOR[o.floor];
  return `<section class="rk-room" aria-labelledby="rk-title">
    <p class="rk-lift">Floor ${esc(o.floor)} · ${esc(f?.name ?? "")}</p>
    <div class="rk-head">
      <div class="rk-left">
        <canvas class="rk-sign" data-sign="${esc(o.sign)}" role="img" aria-label="${esc(o.sign)}"></canvas>
        <h1 id="rk-title">${md(o.title)}</h1>
        <div class="rk-resident">
          <canvas data-portrait="${esc(o.resident)}" width="80" height="96" role="img" aria-label="${esc(p?.name)}, pixel portrait"></canvas>
          <div class="rk-bubble"><span class="rk-who">${esc(p?.name)} · ${esc(p?.title)}</span>${md(o.intro)}</div>
        </div>
      </div>
      <div class="rk-floor"><canvas data-floorview="${esc(o.floor)}" width="${INT_W}" height="${INT_H}" role="img" aria-label="${esc(f?.name)}, live view"></canvas></div>
    </div>
    ${o.spec ? specPanel(o.spec) : ""}
  </section>`;
}

export function specPanel(rows: [string, string][], title = "How this room works") {
  return `<details class="rk-spec" open><summary>${esc(title)}</summary><dl>${rows.map(([k, v]) =>
    `<div><dt>${esc(k)}</dt><dd>${md(v)}</dd></div>`).join("")}</dl></details>`;
}

/** Draw every sign, portrait and floor view in `root`; returns a destroy() that stops the floor views. */
export function mountRoom(root: ParentNode): { destroy(): void } {
  root.querySelectorAll<HTMLCanvasElement>("canvas[data-sign]").forEach((c) => {
    const s = c.dataset.sign!, w = textWidth(s) + 6;
    c.width = w; c.height = 11;
    const p = new Painter(c.getContext("2d")!, pal);
    p.rect(0, 0, w, 11, "k");
    p.text(s, 3, 3, "r");
    c.style.width = `${w * 4}px`;
  });
  root.querySelectorAll<HTMLCanvasElement>("canvas[data-portrait]").forEach((c) => drawPortrait(c, c.dataset.portrait!));
  const views = [...root.querySelectorAll<HTMLCanvasElement>("canvas[data-floorview]")].map((c) => {
    const id = c.dataset.floorview!;
    return { c, sc: new FloorScene(id), on: new Set(FLOOR[id]?.desks ?? []) };
  });
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let raf = 0, last = performance.now(), t = 0;
  const frame = (now: number) => {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (!reduced) t += dt;
    for (const v of views) {
      const ctx = v.c.getContext("2d")!;
      const k = { t, dt: reduced ? 0 : dt, on: v.on, makeHere: null, night: false, reduced };
      v.sc.update(k);
      v.sc.draw(new Painter(ctx, pal), k, []);
      printFx(ctx, pal);
    }
    if (!reduced) raf = requestAnimationFrame(frame);
  };
  if (views.length) raf = requestAnimationFrame(frame);
  return { destroy: () => cancelAnimationFrame(raf) };
}
