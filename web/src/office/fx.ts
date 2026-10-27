// The riso print look on any buffer (P16): a faint second-ink copy a pixel off, then paper grain.
import type { Palette } from "./palettes";

const grains = new Map<string, HTMLCanvasElement>();
function grain(w: number, h: number): HTMLCanvasElement {
  const key = `${w}x${h}`;
  let g = grains.get(key);
  if (g) return g;
  g = document.createElement("canvas");
  g.width = w; g.height = h;
  const c = g.getContext("2d")!;
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < w * h * 0.18; i++) { c.fillStyle = rnd() > 0.5 ? "#000" : "#fff"; c.fillRect(Math.floor(rnd() * w), Math.floor(rnd() * h), 1, 1); }
  grains.set(key, g);
  return g;
}

export function printFx(ctx: CanvasRenderingContext2D, pal: Palette) {
  const c = ctx.canvas;
  if (pal.fx.riso) {
    ctx.save(); ctx.globalCompositeOperation = "multiply"; ctx.globalAlpha = 0.18; ctx.drawImage(c, 1, 1); ctx.restore();
  }
  if (pal.fx.grain) {
    ctx.save(); ctx.globalAlpha = pal.fx.grain; ctx.globalCompositeOperation = "overlay"; ctx.drawImage(grain(c.width, c.height), 0, 0); ctx.restore();
  }
}
