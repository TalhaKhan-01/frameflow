// Inside one floor of Thirdspace House (P16): a front-cutaway room on a 16 px tile grid. Desks sit on row 1; people
// get up when their desk is idle (cooler, window, a colleague), walk on the grid (BFS) and come back when work arrives.
// A runner brings the script folder out of the lift to whichever desk on this floor has it.
import { Painter, person, textWidth } from "./sprites";
import { DESK, FLOOR, RUNNER } from "./desks";
import { drawStation } from "./stations";

export const INT_W = 256, INT_H = 160;
const WALL = 56, TILE = 16, COLS = 16, ROWS = 6, SEAT_ROW = 1;
export const LIFT_TILE: [number, number] = [14, 0];
const COOLER: [number, number] = [1, 0], PLANT: [number, number] = [0, 0];
// floor furniture: a chai table people gather at, a sofa, a plant; tiles they block
const TABLE: [number, number] = [7, 4], SOFA: [number, number][] = [[2, 5], [3, 5], [4, 5]], POT: [number, number] = [15, 5];

export function seatCols(n: number): number[] { return Array.from({ length: n }, (_, i) => Math.round(1.5 + (12 / n) * (i + 0.5))); }
export function seatXY(c: number): { x: number; y: number } { return { x: c * TILE + 2, y: WALL + SEAT_ROW * TILE - 4 }; }
const feet = (c: number, r: number) => ({ x: c * TILE + 8, y: WALL + r * TILE + 14 });

interface Actor {
  desk: string | null;            // null: the runner
  home: [number, number];
  x: number; y: number;           // feet, in px
  path: [number, number][];
  mode: "sit" | "walk" | "stand" | "gone";
  wait: number;
  flip: boolean;
  goingHome: boolean;
  say?: string;
}

export interface FloorTick { t: number; dt: number; on: Set<string>; makeHere: string | null; night: boolean; reduced: boolean }

export class FloorScene {
  actors: Actor[] = [];
  blocked = new Set<string>();
  door = 0;   // lift doors, 0 shut .. 1 open
  constructor(public id: string) {
    const f = FLOOR[id];
    const cols = seatCols(f.desks.length);
    if (id !== "R") { this.block(...COOLER); this.block(...PLANT); }
    if (id !== "B") { this.block(...TABLE); this.block(TABLE[0] + 1, TABLE[1]); SOFA.forEach((t) => this.block(...t)); this.block(...POT); }
    f.desks.forEach((desk, i) => {
      const c = cols[i];
      for (const dc of [-1, 0, 1]) this.block(c + dc, SEAT_ROW);
      const at = feet(c, SEAT_ROW);
      this.actors.push({ desk, home: [c, SEAT_ROW], x: at.x, y: at.y, path: [], mode: "sit", wait: 0, flip: false, goingHome: false });
    });
    if (id !== "B") {
      const at = feet(...LIFT_TILE);
      this.actors.push({ desk: null, home: LIFT_TILE, x: at.x, y: at.y, path: [], mode: "gone", wait: 0, flip: false, goingHome: false });
    }
  }
  private block(c: number, r: number) { this.blocked.add(`${c},${r}`); }
  private free(c: number, r: number, from: [number, number], to: [number, number]) {
    if (c < 0 || r < 0 || c >= COLS || r >= ROWS) return false;
    if ((c === from[0] && r === from[1]) || (c === to[0] && r === to[1])) return true;
    return !this.blocked.has(`${c},${r}`);
  }
  path(from: [number, number], to: [number, number]): [number, number][] {
    const key = (c: number, r: number) => `${c},${r}`;
    const prev = new Map<string, string | null>([[key(...from), null]]);
    const q: [number, number][] = [from];
    while (q.length) {
      const [c, r] = q.shift()!;
      if (c === to[0] && r === to[1]) break;
      for (const [dc, dr] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const n: [number, number] = [c + dc, r + dr];
        if (prev.has(key(...n)) || !this.free(n[0], n[1], from, to)) continue;
        prev.set(key(...n), key(c, r));
        q.push(n);
      }
    }
    if (!prev.has(key(...to))) return [];
    const out: [number, number][] = [];
    for (let k: string | null = key(...to); k && k !== key(...from); k = prev.get(k) ?? null) {
      const [c, r] = k.split(",").map(Number);
      out.unshift([c, r]);
    }
    return out;
  }
  private tileOf(a: Actor): [number, number] { return [Math.max(0, Math.min(COLS - 1, Math.floor(a.x / TILE))), Math.max(0, Math.min(ROWS - 1, Math.floor((a.y - WALL) / TILE)))]; }
  private go(a: Actor, to: [number, number]) {
    a.path = this.path(this.tileOf(a), to);
    a.mode = a.path.length ? "walk" : a.mode;
  }
  private pickErrand(a: Actor): [number, number] {
    const others = this.actors.filter((o) => o !== a && o.desk);
    const r = Math.random();
    if (r < 0.25 && this.id !== "R") return [COOLER[0] + 1, COOLER[1]];
    if (r < 0.55) return [TABLE[0] + (Math.random() < 0.5 ? -1 : 2), TABLE[1]];
    if (r < 0.8 && others.length) { const o = others[Math.floor(Math.random() * others.length)]; return [o.home[0], o.home[1] + 1]; }
    return [5 + Math.floor(Math.random() * 8), 3 + Math.floor(Math.random() * 3)];
  }

  update(k: FloorTick) {
    const speed = 34;
    const target = k.makeHere && this.actors.find((a) => a.desk === k.makeHere);
    for (const a of this.actors) {
      const working = a.desk ? k.on.has(a.desk) : false;
      if (a.desk) {
        if (working && a.mode !== "sit" && !a.goingHome) { this.go(a, a.home); a.goingHome = true; }
        if (a.mode === "sit" && !working && !k.reduced && Math.random() < k.dt * 0.035) { a.mode = "stand"; this.go(a, this.pickErrand(a)); a.goingHome = false; }
        if (a.mode === "stand" && !a.goingHome) { a.wait -= k.dt; if (a.wait <= 0) { this.go(a, a.home); a.goingHome = true; } }
      } else {
        // the runner: out of the lift to the desk with the folder, back into the lift when the make moves on
        const want: [number, number] = target ? [target.home[0], target.home[1] + 1] : LIFT_TILE;
        const last = a.path.length ? a.path[a.path.length - 1] : this.tileOf(a);
        if (a.mode === "gone" && target) { a.mode = "stand"; this.go(a, want); }
        else if (a.mode !== "gone" && (last[0] !== want[0] || last[1] !== want[1])) this.go(a, want);
      }
      if (a.mode === "walk" && a.path.length) {
        const [c, r] = a.path[0];
        const to = feet(c, r);
        const dx = to.x - a.x, dy = to.y - a.y, dist = Math.hypot(dx, dy), step = speed * k.dt;
        if (dx) a.flip = dx < 0;
        if (dist <= step) { a.x = to.x; a.y = to.y; a.path.shift(); } else { a.x += (dx / dist) * step; a.y += (dy / dist) * step; }
        if (!a.path.length) {
          const t = this.tileOf(a);
          if (a.desk && t[0] === a.home[0] && t[1] === a.home[1]) { a.mode = "sit"; a.goingHome = false; }
          else if (!a.desk && t[0] === LIFT_TILE[0] && t[1] === LIFT_TILE[1] && !target) a.mode = "gone";
          else { a.mode = "stand"; a.wait = 2 + Math.random() * 4; }
        }
      }
    }
    const runner = this.actors.find((a) => !a.desk);
    const near = runner && runner.mode !== "gone" && Math.hypot(runner.x - feet(...LIFT_TILE).x, runner.y - feet(...LIFT_TILE).y) < 28;
    const want = near || (runner?.mode === "gone" && target) ? 1 : 0;
    this.door += Math.sign(want - this.door) * Math.min(Math.abs(want - this.door), k.dt * 3);
  }

  deskAt(x: number, y: number): string | null {
    for (const a of this.actors) {
      if (!a.desk) continue;
      const box = a.mode === "sit" ? { x: seatXY(a.home[0]).x - 9, y: seatXY(a.home[0]).y - 2, w: 30, h: 26 } : { x: a.x - 7, y: a.y - 20, w: 14, h: 21 };
      if (x >= box.x && x < box.x + box.w && y >= box.y && y < box.y + box.h) return a.desk;
    }
    return null;
  }
  /** Where a desk's person is now (for speech bubbles): head position in px. */
  headOf(desk: string): { x: number; y: number } | null {
    const a = this.actors.find((o) => o.desk === desk);
    if (!a) return null;
    if (a.mode === "sit") { const s = seatXY(a.home[0]); return { x: s.x + 6, y: s.y - 2 }; }
    return { x: a.x, y: a.y - 20 };
  }

  draw(p: Painter, k: FloorTick, stamps: { desk: string; pass: boolean }[]) {
    room(p, this.id, k);
    this.liftDoor(p);
    const items: { z: number; draw: () => void }[] = [];
    for (const a of this.actors) {
      if (a.desk) {
        const d = DESK[a.desk], s = seatXY(a.home[0]);
        items.push({ z: s.y + 24, draw: () => drawStation(p, d, s.x, s.y, { t: k.t, on: k.on.has(a.desk!), seated: a.mode === "sit", seed: s.x }) });
      }
      if (a.mode === "walk" || a.mode === "stand") {
        const look = a.desk ? DESK[a.desk].look : RUNNER;
        items.push({ z: a.y, draw: () => {
          p.rect(a.x - 5, a.y, 10, 2, "F");
          p.grid(person({ ...look, walk: a.mode === "walk" ? Math.floor(k.t * 8) : undefined }), Math.round(a.x - 6), Math.round(a.y - 18), a.flip);
          if (!a.desk && k.makeHere) { p.rect(a.x + (a.flip ? -7 : -1), a.y - 9, 8, 6, "r"); p.rect(a.x + (a.flip ? -7 : -1), a.y - 9, 8, 1, "k"); }
        } });
      }
    }
    items.sort((a, b) => a.z - b.z).forEach((i) => i.draw());
    for (const st of stamps) {
      const h = this.headOf(st.desk);
      if (!h) continue;
      const word = st.pass ? "OK" : "FIX", w = textWidth(word) + 4;
      p.rect(h.x - w / 2, h.y - 12, w, 9, st.pass ? "V" : "r");
      p.text(word, h.x - w / 2 + 2, h.y - 10, "p");
    }
    if (k.night && this.id !== "R") { const c = p.ctx; c.save(); c.globalAlpha = 0.12; c.fillStyle = p.col("V"); c.fillRect(0, 0, INT_W, INT_H); c.restore(); }
  }

  private liftDoor(p: Painter) {
    if (this.id === "B") return;
    const x = LIFT_TILE[0] * TILE + 2, y = WALL - 34, w = 26, h = 34;
    p.rect(x - 2, y - 2, w + 4, h + 2, "k");
    p.rect(x, y, w, h, "X");
    const open = Math.round((w / 2) * this.door);
    p.rect(x, y, w / 2 - open, h, "m");
    p.rect(x + w / 2 + open, y, w / 2 - open, h, "m");
    p.rect(x + w / 2 - open - 1, y, 1, h, "k");
    p.rect(x + w / 2 + open, y, 1, h, "k");
    p.rect(x + 8, y - 10, 12, 7, "k");
    p.text(this.id, x + 12, y - 9, "g");
  }
}

function room(p: Painter, id: string, k: FloorTick) {
  const on = (d: string) => k.on.has(d);
  if (id === "R") {
    p.rect(0, 0, INT_W, WALL, k.night ? "V" : "W");
    for (let i = 0; i < 8; i++) { const h = 10 + ((i * 37) % 24); p.rect(i * 34, WALL - 8 - h, 28, h, k.night ? "d" : "X"); }
    if (k.night) for (let i = 0; i < 20; i++) p.rect((i * 53) % INT_W, (i * 29) % 26, 1, 1, "p");
    p.rect(0, WALL - 8, INT_W, 8, "F"); p.rect(0, WALL - 8, INT_W, 1, "k");
    p.rect(6, 10, 32, 30, "m"); p.rect(6, 18, 32, 1, "k"); p.rect(6, 30, 32, 1, "k"); p.rect(9, 40, 2, 8, "k"); p.rect(33, 40, 2, 8, "k");
    p.rect(196, 4, 1, 28, "k"); p.rect(193, 4, 7, 2, "r");
  } else {
    p.rect(0, 0, INT_W, WALL, "I");
    if (id === "B") {
      for (let shelf = 0; shelf < 3; shelf++) {
        const sy = 4 + shelf * 15;
        p.rect(6, sy + 11, 120, 2, "d");
        for (let i = 0; i < 17; i++) p.rect(8 + i * 7, sy + 2, 5, 9, (i + shelf) % 3 ? "y" : "r");
      }
      p.rect(150, 6, 96, 40, "l"); p.rect(150, 6, 96, 2, "k");
      for (let i = 0; i < 8; i++) { p.rect(156 + (i % 4) * 22, 12 + Math.floor(i / 4) * 16, 16, 11, "p"); p.rect(163 + (i % 4) * 22, 12 + Math.floor(i / 4) * 16, 2, 2, "r"); }
      p.text("LIBRARY", 40, WALL - 8, "V"); p.text("LESSONS", 184, WALL - 8, "V");
    } else {
      // a window on the city
      p.rect(96, 6, 64, 28, "k"); p.rect(98, 8, 60, 24, k.night ? "V" : "X");
      for (let i = 0; i < 5; i++) p.rect(100 + i * 12, 18 + ((i * 7) % 10), 9, 14 - ((i * 7) % 10), k.night ? "d" : "m");
      if (k.night) for (let i = 0; i < 5; i++) p.rect(103 + i * 12, 22, 2, 2, "g");
      p.rect(127, 8, 2, 24, "k");
      p.rect(0, WALL - 4, INT_W, 4, "V");
    }
    switch (id) {
      case "2": {
        for (let y = 6; y < 46; y += 8) for (let x = 6; x < 88; x += 8) if (((x + y) / 8) % 2 > 0.5) p.rect(x, y, 5, 5, "X");
        const air = on("narrator");
        p.rect(170, 10, 42, 14, "k"); p.rect(172, 12, 38, 10, air ? "r" : "d"); p.text("ON AIR", 180, 15, air ? "p" : "m");
        break;
      }
      case "1": {
        for (let i = 0; i < 15; i++) { p.rect(6 + (i % 5) * 17, 6 + Math.floor(i / 5) * 14, 14, 11, i % 5 === 2 ? "y" : "p"); p.rect(12 + (i % 5) * 17, 6 + Math.floor(i / 5) * 14, 2, 2, "r"); }
        p.rect(168, 8, 46, 30, "p"); p.rect(168, 8, 46, 1, "k"); p.text("HOOK?", 180, 14, "r");
        for (let i = 0; i < 3; i++) p.rect(174, 24 + i * 4, 32 - i * 8, 1, "m");
        break;
      }
      case "3": {
        const live = on("animatic") || on("screening");
        p.rect(6, 4, 82, 44, "k"); p.rect(8, 6, 78, 40, live ? (Math.floor(k.t * 6) % 3 ? "p" : "X") : "m");
        if (live) { p.rect(20 + (Math.floor(k.t * 20) % 40), 18, 12, 12, "r"); p.text("ANIMATIC", 30, 38, "V"); }
        p.rect(170, 10, 40, 26, "l"); p.text("SCORE", 180, 14, "V"); p.text("14/22", 180, 24, "r");
        break;
      }
      case "4": {
        p.text("ENGINE ROOM", 6, 6, "V");
        for (let i = 0; i < 4; i++) { p.rect(6 + i * 20, 14, 16, 34, "k"); for (let j = 0; j < 5; j++) p.rect(9 + i * 20, 17 + j * 6, 10, 3, on("animator") && (Math.floor(k.t * 6) + j + i) % 4 ? "r" : "d"); }
        p.rect(170, 10, 40, 24, "k"); p.rect(172, 12, 36, 20, "X");
        for (let i = 0; i < 9; i++) p.rect(174 + i * 4, 22 - ((i * 5 + Math.floor(k.t * (on("qc") ? 6 : 0))) % 8), 2, 2 + ((i * 5 + Math.floor(k.t * (on("qc") ? 6 : 0))) % 8), "V");
        break;
      }
      case "5": {
        p.rect(10, 8, 56, 34, "l"); p.rect(12, 10, 52, 30, "p"); p.text("THIRDSPACE", 18, 16, "r"); p.text("PRODUCTIONS", 16, 26, "V");
        p.rect(176, 10, 20, 20, "k"); p.rect(178, 12, 16, 16, "p"); p.rect(186, 14, 1, 7, "k"); p.rect(186, 20, 5, 1, "r");
        break;
      }
      case "G": {
        p.text("THE NEWSROOM", 6, 6, "V");
        for (let i = 0; i < 8; i++) p.rect(6 + (i % 4) * 20 + (i > 3 ? 8 : 0), 14 + Math.floor(i / 4) * 16, 15, 13, i % 3 ? "p" : "y");
        p.rect(166, 10, 50, 10, "k");
        const msg = "WIRE: NEW STORY IN  ";
        const off = Math.floor(k.t * 10) % (msg.length * 4);
        p.ctx.save(); p.ctx.beginPath(); p.ctx.rect(167, 11, 48, 8); p.ctx.clip();
        p.text(msg + msg, 168 - off, 13, "g"); p.ctx.restore();
        break;
      }
    }
  }
  // floor tiles and baseboard
  for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) p.rect(c * TILE, WALL + r * TILE, TILE, TILE, (c + r) % 2 ? "f" : "F");
  p.rect(0, INT_H - 8, INT_W, 8, "d"); p.rect(0, INT_H - 8, INT_W, 1, "k");
  if (id === "B") {
    for (let i = 0; i < 6; i++) { p.rect(40 + i * 30, WALL + 50, 20, 14, "l"); p.rect(40 + i * 30, WALL + 50, 20, 1, "k"); p.rect(46 + i * 30, WALL + 55, 8, 2, "d"); }
    // the archive cat, asleep
    const cx = 200, cy = WALL + 80, z = Math.floor(k.t) % 3;
    p.rect(cx, cy, 10, 4, "k"); p.rect(cx + 8, cy - 2, 4, 3, "k"); p.rect(cx - 3, cy + 2, 4, 1, "k");
    p.text("Z".repeat(z + 1), cx + 12, cy - 9 - z, "m");
    return;
  }
  if (id !== "R") {
    // cooler and plant
    const cx = COOLER[0] * TILE, py = WALL + 14;
    p.rect(cx + 3, py - 22, 10, 10, "X"); p.rect(cx + 3, py - 22, 10, 1, "k"); p.rect(cx + 2, py - 12, 12, 12, "m"); p.rect(cx + 5, py - 9, 2, 2, "r");
    p.rect(PLANT[0] * TILE + 4, py - 8, 8, 8, "d");
    [[5, -18], [8, -21], [3, -14], [10, -15]].forEach(([dx, dy]) => p.rect(PLANT[0] * TILE + dx, py + dy, 2, 8, "V"));
  }
  // rug, chai table, sofa, a big plant
  for (let x = 72; x < 168; x += 4) for (let y = WALL + 40; y < WALL + 76; y += 4) if (((x + y) / 4) % 3 === 0) p.rect(x, y, 2, 2, "y");
  p.rect(68, WALL + 38, 104, 1, "r"); p.rect(68, WALL + 77, 104, 1, "r");
  const tx = TABLE[0] * TILE, ty = WALL + TABLE[1] * TILE;
  p.rect(tx, ty + 4, 32, 4, "l"); p.rect(tx, ty + 8, 32, 1, "k"); p.rect(tx + 2, ty + 9, 2, 6, "d"); p.rect(tx + 28, ty + 9, 2, 6, "d");
  [[8, 0], [14, 1], [22, 0]].forEach(([dx, dy]) => { p.rect(tx + dx, ty + dy, 3, 4, "p"); p.rect(tx + dx, ty + dy + 1, 3, 2, "y"); });
  if (Math.floor(k.t * 3) % 2) p.rect(tx + 15, ty - 3, 1, 2, "p");
  const sx = SOFA[0][0] * TILE, sy = WALL + SOFA[0][1] * TILE;
  p.rect(sx, sy - 4, 48, 6, "b"); p.rect(sx, sy + 2, 48, 8, "a"); p.rect(sx - 2, sy - 2, 4, 12, "b"); p.rect(sx + 46, sy - 2, 4, 12, "b");
  p.rect(sx + 4, sy + 2, 1, 8, "k"); p.rect(sx + 24, sy + 2, 1, 8, "k");
  const px = POT[0] * TILE, py2 = WALL + POT[1] * TILE;
  p.rect(px + 3, py2 + 6, 10, 9, "r");
  [[4, -10], [7, -14], [10, -9], [2, -6], [12, -5]].forEach(([dx, dy]) => p.rect(px + dx, py2 + dy, 2, 14, "V"));
  if (id === "R") { p.text("DISPATCH: YT IG FB", 60, INT_H - 6, "p"); }
}

/** Places on a floor that open a page (the Archive's shelves and notice board). */
export function placeAt(id: string, x: number, y: number): string | null {
  if (id !== "B") return null;
  if (x < 130 && y < WALL) return "library";
  if (x >= 150 && x < 246 && y < WALL) return "lessons";
  return null;
}
