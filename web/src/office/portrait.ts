// Staff ID-card portraits (P17.3.4): the house's own person sprite, drawn big on a riso card. Desk people wear their
// desk look; the new hires, the street and the owner get their looks here. Bade Sahab is only ever a silhouette.
import { PALETTES } from "./palettes";
import { Painter, person } from "./sprites";
import { DESK, CHAIWALA } from "./desks";
import { printFx } from "./fx";

const pal = PALETTES.find((p) => p.id === "riso")!;
const look = (h: string, a: string, b: string, habit?: string) => ({ colors: { h, a, b }, habit });
const EXTRA: Record<string, { colors: Record<string, string>; habit?: string }> = {
  dhwani: look("d", "r", "k", "phones"), kabadi: look("k", "y", "d", "cap"), trendulkar: look("k", "p", "A", "cap"),
  chaiwala: CHAIWALA,
};
const W = 20, H = 24;

export function drawPortrait(canvas: HTMLCanvasElement, id: string) {
  const s = 4;
  canvas.width = W * s; canvas.height = H * s;
  const ctx = canvas.getContext("2d")!;
  ctx.imageSmoothingEnabled = false;
  const off = document.createElement("canvas"); off.width = W; off.height = H;
  const p = new Painter(off.getContext("2d")!, pal);
  p.rect(0, 0, W, H, "p");
  p.rect(0, H - 6, W, 6, "f");
  if (id === "cat") {   // Cache, sitting
    p.rect(6, 12, 8, 6, "k"); p.rect(11, 8, 5, 5, "k"); p.rect(11, 7, 1, 1, "k"); p.rect(15, 7, 1, 1, "k");
    p.rect(12, 10, 1, 1, "y"); p.rect(14, 10, 1, 1, "y"); p.rect(4, 15, 2, 1, "k"); p.rect(3, 14, 1, 1, "k");
  } else {
    const lk = DESK[id]?.look ?? EXTRA[id] ?? CHAIWALA;
    let g = person({ habit: lk.habit, colors: lk.colors });
    if (id === "you") g = g.map((r) => r.replace(/[^.]/g, "k"));   // Bade Sahab: never more than a silhouette
    p.grid(g, 4, H - 19);
  }
  printFx(p.ctx, pal);
  ctx.drawImage(off, 0, 0, W * s, H * s);
}
