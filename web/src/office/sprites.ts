// Our own pixel sprites (P16): grids of palette slots, '.' is transparent. Nothing here comes from another pack.
import type { Palette } from "./palettes";

export type Grid = string[];

// A person, 12 × 19, front view. 'o' is the mouth (skin when closed, ink when open).
const PERSON: Grid = [
  "...hhhhhh...",
  "..hhhhhhhh..",
  ".hhhhhhhhhh.",
  ".hssssssssh.",
  ".ssksssskss.",
  ".ssssssssss.",
  "..sssoosss..",
  "...ssssss...",
  "..aaawwaaa..",
  ".aaaaaaaaaa.",
  "saaaaaaaaaas",
  "saaaaaaaaaas",
  "saaaaaaaaaas",
  ".aaaaaaaaaa.",
  ".bbbbbbbbbb.",
  ".bbbbbbbbbb.",
  ".bbbb..bbbb.",
  ".bbbb..bbbb.",
  ".kkkk..kkkk.",
];
const LEGS_STRIDE: Grid = ["..bbb..bbb..", ".bbb....bbb.", ".kkk....kkk."];
const LEGS_TOGETHER: Grid = ["..bbbbbbbb..", "...bbbbbb...", "...kkkkkk..."];

// Habit variants, laid over the person's top rows ('.' keeps what is under).
export const HABITS: Record<string, { label: string; over: Grid }> = {
  phones: { label: "Headphones", over: [
    "..mmmmmmmm..",
    ".m........m.",
    ".m........m.",
    "mm........mm",
    "mm........mm",
    "mm........mm",
  ] },
  specs: { label: "Round specs + kurta", over: [
    "............",
    "............",
    "............",
    ".GGGG..GGGG.",
    ".GskGGGGksG.",
    ".GGGG..GGGG.",
    "............",
    "............",
    "..aawwwwaa..",
    "....w.......",
    "....w.......",
    "............",
    "............",
    "............",
    ".aaaaaaaaaa.",
  ] },
  cap: { label: "Cap", over: [
    "...cccccc...",
    "..cccccccc..",
    ".cccccccccc.",
    "cccccccccccc",
  ] },
};

function overlay(base: Grid, over: Grid): Grid {
  return base.map((row, y) => {
    const o = over[y];
    if (!o) return row;
    return [...row].map((ch, x) => (o[x] && o[x] !== "." ? o[x] : ch)).join("");
  });
}

export interface PersonOpts { habit?: string; shirt?: "a" | "A"; talk?: boolean; walk?: number; seated?: boolean }

export function person(opts: PersonOpts = {}): Grid {
  let g = PERSON.slice();
  if (opts.walk !== undefined) g = [...g.slice(0, 16), ...(opts.walk % 2 ? LEGS_STRIDE : LEGS_TOGETHER)];
  if (opts.habit && HABITS[opts.habit]) g = overlay(g, HABITS[opts.habit].over);
  g = g.map((r) => r.replace(/o/g, opts.talk ? "k" : "s"));
  if (opts.shirt === "A") g = g.map((r) => r.replace(/a/g, "A"));
  return opts.seated ? g.slice(0, 14) : g;
}

// 3 × 5 pixel letters, enough for signs and stamps.
const FONT: Record<string, string[]> = {
  O: ["###", "#.#", "#.#", "#.#", "###"], N: ["#.#", "###", "###", "###", "#.#"], A: [".#.", "#.#", "###", "#.#", "#.#"],
  I: ["###", ".#.", ".#.", ".#.", "###"], R: ["##.", "#.#", "##.", "#.#", "#.#"], K: ["#.#", "##.", "#..", "##.", "#.#"],
  V: ["#.#", "#.#", "#.#", "#.#", ".#."], E: ["###", "#..", "##.", "#..", "###"], F: ["###", "#..", "##.", "#..", "#.."],
  D: ["##.", "#.#", "#.#", "#.#", "##."], Y: ["#.#", "#.#", ".#.", ".#.", ".#."], T: ["###", ".#.", ".#.", ".#.", ".#."],
  B: ["##.", "#.#", "##.", "#.#", "##."], H: ["#.#", "#.#", "###", "#.#", "#.#"], G: ["###", "#..", "#.#", "#.#", "###"], " ": ["...", "...", "...", "...", "..."],
};

export class Painter {
  constructor(public ctx: CanvasRenderingContext2D, public pal: Palette) {}
  col(slot: string) { return this.pal.slots[slot] ?? slot; }
  rect(x: number, y: number, w: number, h: number, slot: string) {
    this.ctx.fillStyle = this.col(slot);
    this.ctx.fillRect(Math.round(x), Math.round(y), w, h);
  }
  grid(g: Grid, x: number, y: number, flip = false) {
    const w = g[0].length;
    g.forEach((row, j) => {
      for (let i = 0; i < row.length; i++) {
        const ch = row[i];
        if (ch !== ".") this.rect(x + (flip ? w - 1 - i : i), y + j, 1, 1, ch);
      }
    });
  }
  text(s: string, x: number, y: number, slot: string) {
    [...s.toUpperCase()].forEach((ch, n) => {
      const f = FONT[ch] ?? FONT[" "];
      f.forEach((row, j) => [...row].forEach((c, i) => c === "#" && this.rect(x + n * 4 + i, y + j, 1, 1, slot)));
    });
  }
}
