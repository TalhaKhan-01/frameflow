// The sampler's vignette (P16 step 1): the Booth (Habit on air) and the Proof Desk (stamping), a runner carrying the
// script folder between them. 208 × 120 logical pixels; the same Painter and slots the full office will use.
import type { Palette } from "./palettes";
import { Painter, person } from "./sprites";

export const W = 208, H = 120;

function desk(p: Painter, x: number, y: number, w: number) {
  p.rect(x, y, w, 3, "l");
  p.rect(x, y + 3, w, 1, "k");
  p.rect(x, y + 4, w, 8, "d");
  p.rect(x + 2, y + 6, w - 4, 1, "k");
  p.rect(x + 2, y + 12, 3, 6, "d");
  p.rect(x + w - 5, y + 12, 3, 6, "d");
}

function room(p: Painter) {
  p.rect(0, 0, W, 44, "W");
  for (let y = 6; y < 36; y += 6) for (let x = 6; x < 96; x += 6) if (((x + y) / 6) % 2) p.rect(x, y, 4, 4, "X");
  p.rect(0, 40, W, 4, "V");
  for (let y = 44; y < H; y += 8) for (let x = 0; x < W; x += 8) p.rect(x, y, 8, 8, ((x + y) / 8) % 2 ? "f" : "F");
  p.rect(102, 0, 4, 66, "d");
  p.rect(102, 0, 1, 66, "k");
  p.rect(105, 0, 1, 66, "k");
  // Proof room pinboard with notes
  p.rect(148, 10, 34, 20, "l");
  p.rect(148, 10, 34, 1, "k");
  p.rect(148, 29, 34, 1, "k");
  [[151, 13], [160, 15], [170, 12], [153, 21], [165, 22], [174, 20]].forEach(([x, y]) => { p.rect(x, y, 6, 5, "p"); p.rect(x + 2, y, 1, 1, "r"); });
  // plant in the booth corner
  p.rect(8, 58, 8, 7, "d");
  [[9, 50], [12, 47], [7, 53], [14, 52], [11, 54]].forEach(([x, y]) => p.rect(x, y, 2, 5, "V"));
}

export interface SceneState { talk: boolean; onAir: boolean; stamped: number; runnerX: number; runnerFlip: boolean }

export function sceneState(t: number): SceneState {
  const talkCycle = t % 4;
  const onAir = talkCycle < 2.6;
  const talk = onAir && Math.floor(t * 7) % 2 === 0;
  const stamped = Math.floor(t / 1.6);
  const leg = 7, pos = t % (2 * leg);
  const u = pos < leg ? pos / leg : 2 - pos / leg;
  const ease = u < 0.08 ? 0 : u > 0.92 ? 1 : (u - 0.08) / 0.84;
  return { talk, onAir, stamped, runnerX: 18 + ease * 160, runnerFlip: pos >= leg };
}

export function drawScene(ctx: CanvasRenderingContext2D, pal: Palette, t: number): SceneState {
  const p = new Painter(ctx, pal);
  const s = sceneState(t);
  ctx.fillStyle = pal.bg;
  ctx.fillRect(0, 0, W, H);
  room(p);

  // The Booth: ON AIR sign, Habit, mic
  p.rect(32, 9, 29, 11, "k");
  p.rect(33, 10, 27, 9, s.onAir ? "r" : "d");
  p.text("ON AIR", 35, 12, s.onAir ? "p" : "m");
  p.grid(person({ habit: "phones", talk: s.talk, seated: true }), 34, 49);
  p.rect(56, 51, 1, 11, "m");
  p.rect(54, 47, 5, 5, "k");
  p.rect(55, 48, 3, 3, "m");
  if (s.talk) { p.rect(61, 47, 1, 4, "r"); p.rect(64, 46, 1, 6, "r"); }
  desk(p, 20, 62, 52);
  p.rect(26, 60, 8, 2, "p");
  p.rect(36, 60, 2, 2, "s");
  p.rect(43, 60, 2, 2, "s");

  // The Proof Desk: fact-checker with a stamp, paper, lamp, chai
  p.grid(person({ shirt: "A", seated: true }), 150, 49);
  const phase = (t % 1.6) / 1.6;
  const down = phase > 0.75;
  desk(p, 128, 62, 58);
  p.rect(136, 61, 12, 3, "p");
  p.rect(152, 60, 2, 2, "s");
  if (s.stamped > 0 && !down) { p.rect(139, 61, 6, 2, "r"); }
  const sy = down ? 56 : 49 + Math.round(Math.sin(phase * Math.PI) * -2);
  p.rect(140, sy, 2, 4, "k");
  p.rect(138, sy + 4, 6, 2, "r");
  p.rect(146, sy + 2, 3, 3, "s");
  for (let i = 0; i < 3 + (s.stamped % 4); i++) p.rect(170, 60 - i * 2, 10, 2, i % 2 ? "p" : "l");
  p.rect(183, 54, 1, 8, "k");
  p.rect(180, 52, 5, 3, "k");
  p.rect(181, 55, 3, 1, "g");
  p.rect(132, 58, 3, 4, "p");
  p.rect(132, 59, 3, 2, "y");

  // The runner with the script folder
  const rx = Math.round(s.runnerX), ry = 90;
  p.rect(rx + 1, ry + 19, 10, 2, "F");
  p.grid(person({ walk: Math.floor(t * 8), shirt: "A" }), rx, ry, s.runnerFlip);
  p.rect(rx + (s.runnerFlip ? 0 : 5), ry + 9, 7, 5, "y");
  p.rect(rx + (s.runnerFlip ? 0 : 5), ry + 9, 7, 1, "k");

  fx(ctx, pal, t, s);
  return s;
}

let grainCanvas: HTMLCanvasElement | null = null;
function grain(): HTMLCanvasElement {
  if (grainCanvas) return grainCanvas;
  grainCanvas = document.createElement("canvas");
  grainCanvas.width = W; grainCanvas.height = H;
  const g = grainCanvas.getContext("2d")!;
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < W * H * 0.18; i++) { g.fillStyle = rnd() > 0.5 ? "#000" : "#fff"; g.fillRect(Math.floor(rnd() * W), Math.floor(rnd() * H), 1, 1); }
  return grainCanvas;
}

function fx(ctx: CanvasRenderingContext2D, pal: Palette, t: number, s: SceneState) {
  const c = ctx.canvas;
  if (pal.fx.riso) {
    // The second ink drum, a pixel off: a faint blue copy under the red.
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.globalAlpha = 0.18;
    ctx.drawImage(c, 1, 1);
    ctx.restore();
  }
  if (pal.fx.grain) {
    ctx.save();
    ctx.globalAlpha = pal.fx.grain;
    ctx.globalCompositeOperation = "overlay";
    ctx.drawImage(grain(), 0, 0);
    ctx.restore();
  }
  if (pal.fx.glow) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    const glow = (x: number, y: number, r: number, col: string, a: number) => {
      const gr = ctx.createRadialGradient(x, y, 0, x, y, r);
      gr.addColorStop(0, col); gr.addColorStop(1, "transparent");
      ctx.globalAlpha = a; ctx.fillStyle = gr; ctx.fillRect(x - r, y - r, r * 2, r * 2);
    };
    if (s.onAir) glow(46, 14, 26, pal.slots.r, 0.35 + 0.1 * Math.sin(t * 6));
    glow(182, 56, 22, pal.slots.y, 0.3);
    glow(56, 50, 10, pal.slots.a, 0.15);
    ctx.restore();
  }
}

// The reel end card mock: a standing Habit on a floor line, 54 × 96.
export const EW = 54, EH = 96;
export function drawEndcard(ctx: CanvasRenderingContext2D, pal: Palette, t: number, habit = "phones") {
  const p = new Painter(ctx, pal);
  ctx.fillStyle = pal.bg;
  ctx.fillRect(0, 0, EW, EH);
  p.rect(0, 52, EW, 1, "V");
  p.rect(14, 6, 26, 9, "k");
  p.rect(15, 7, 24, 7, Math.floor(t * 1.5) % 2 ? "r" : "d");
  p.text("HABIT", 17, 8, "p");
  const bob = Math.floor(t * 3) % 2;
  p.grid(person({ habit, talk: Math.floor(t * 6) % 3 === 0 }), 21, 33 + bob);
}

export function drawHabit(ctx: CanvasRenderingContext2D, pal: Palette, habit: string) {
  const p = new Painter(ctx, pal);
  ctx.fillStyle = pal.bg;
  ctx.fillRect(0, 0, 16, 22);
  p.grid(person({ habit }), 2, 2);
}
