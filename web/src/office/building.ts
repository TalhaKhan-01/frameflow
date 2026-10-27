// Thirdspace House from the street (P16): every floor cut open at once, the lift on the side, the street below.
import { Painter, person, textWidth } from "./sprites";
import { DESK, FLOORS, CHAIWALA } from "./desks";
import { drawStation } from "./stations";

export const EXT_W = 480, EXT_H = 480;
export const BX = 128, BW = 224, LIFT_X = BX + BW + 2;
const ROOF_Y = 64, FH = 48, G_H = 52;
export const STREET_Y = ROOF_Y + 6 * FH + G_H;            // 404
export const FLOOR_RECT: Record<string, { y: number; h: number }> = {};
FLOORS.forEach((f, i) => {
  if (f.id === "G") FLOOR_RECT.G = { y: ROOF_Y + 6 * FH, h: G_H };
  else if (f.id === "B") FLOOR_RECT.B = { y: STREET_Y + 26, h: 46 };
  else FLOOR_RECT[f.id] = { y: ROOF_Y + i * FH, h: FH };
});

export interface ExtState {
  t: number; night: boolean; on: Set<string>; makeFloor: string | null; hover: string | null; liftY: number; carrying: boolean;
  stamps: { desk: string; pass: boolean }[];
}

/** Where a desk's seated person is drawn in the street view (top-left). */
export function extStation(desk: string): { x: number; y: number } {
  const f = FLOORS.find((fl) => fl.desks.includes(desk))!;
  const i = f.desks.indexOf(desk), n = f.desks.length;
  const r = FLOOR_RECT[f.id];
  const lead = f.id === "R" ? 40 : 0;   // the roof's water tank takes the left end
  const span = BW - lead;
  return { x: Math.round(BX + lead + (span / n) * (i + 0.5) - 6), y: r.y + (f.id === "G" ? 20 : 16) };
}

export function liftYFor(floor: string): number { const r = FLOOR_RECT[floor]; return r.y + r.h - 24; }

function sky(p: Painter, s: ExtState) {
  p.rect(0, 0, EXT_W, STREET_Y, s.night ? "V" : "W");
  if (s.night) {
    for (let i = 0; i < 40; i++) p.rect((i * 97) % EXT_W, (i * 53) % 150, 1, 1, i % 7 ? "X" : "p");
    p.rect(52, 22, 10, 10, "p"); p.rect(55, 22, 7, 7, "V");
  } else {
    for (let dy = -7; dy <= 7; dy++) { const w = Math.round(Math.sqrt(49 - dy * dy)); p.rect(60 - w, 36 + dy, w * 2, 1, "r"); }
    [[300, 30, 40], [400, 52, 30], [20, 80, 34]].forEach(([x, y, w]) => { p.rect(x, y, w, 4, "X"); p.rect(x + 6, y - 3, w - 14, 3, "X"); });
  }
}

function neighbours(p: Painter, s: ExtState) {
  const block = (x: number, y: number, w: number, seed: number) => {
    p.rect(x, y, w, STREET_Y - y, s.night ? "d" : "X");
    for (let yy = y + 8; yy < STREET_Y - 10; yy += 14)
      for (let xx = x + 6; xx < x + w - 8; xx += 12) {
        const lit = s.night ? (xx * 7 + yy * 3 + seed) % 5 < 2 : false;
        p.rect(xx, yy, 6, 8, lit ? "g" : s.night ? "b" : "W");
      }
  };
  block(4, 170, 104, 1);
  block(380, 210, 96, 2);
  block(108, 260, 18, 3);
}

function wallProps(p: Painter, id: string, y: number, s: ExtState) {
  const on = (desk: string) => s.on.has(desk);
  switch (id) {
    case "5": p.rect(BX + 96, y + 6, 32, 14, "X"); p.rect(BX + 111, y + 6, 1, 14, "k"); p.rect(BX + 96, y + 13, 32, 1, "k"); break;
    case "3": {
      p.rect(BX + 92, y + 4, 40, 18, "k"); p.rect(BX + 93, y + 5, 38, 16, on("animatic") || on("screening") ? (Math.floor(s.t * 6) % 2 ? "p" : "X") : "m");
      break;
    }
    case "2": {
      const air = on("narrator");
      p.rect(BX + 30, y + 5, 27, 9, "k"); p.rect(BX + 31, y + 6, 25, 7, air ? "r" : "d"); p.text("ON AIR", BX + 32, y + 7, air ? "p" : "m");
      for (let xx = BX + 120; xx < BX + 210; xx += 8) for (let yy = y + 5; yy < y + 22; yy += 8) p.rect(xx, yy, 5, 5, "X");
      break;
    }
    case "1": for (let i = 0; i < 12; i++) p.rect(BX + 70 + (i % 6) * 9, y + 5 + Math.floor(i / 6) * 8, 7, 6, i % 4 === 1 ? "y" : "p"); break;
    case "G": { p.rect(BX + 96, y + 4, 34, 12, "l"); [[100, 6], [110, 8], [120, 5]].forEach(([x, yy]) => p.rect(BX + x, y + yy, 7, 6, "p")); break; }
    case "4": p.text("RENDER", BX + 90, y + 8, "V"); break;
  }
}

function floorBox(p: Painter, id: string, s: ExtState) {
  const r = FLOOR_RECT[id];
  const top = id === "G" ? r.y + 7 : r.y;
  if (id === "R") {
    p.rect(BX, r.y + 38, BW, 7, "F");
    p.rect(BX + 6, r.y + 6, 26, 22, "m"); p.rect(BX + 6, r.y + 12, 26, 1, "k"); p.rect(BX + 6, r.y + 20, 26, 1, "k");
    p.rect(BX + 9, r.y + 28, 2, 10, "k"); p.rect(BX + 27, r.y + 28, 2, 10, "k");
    p.rect(BX + 200, r.y + 2, 1, 14, "k"); p.rect(BX + 198, r.y + 2, 5, 1, "r");
  } else {
    p.rect(BX, top, BW, r.y + r.h - top - 3, "I");
    p.rect(BX, r.y + r.h - 20, BW, 17, "f");
    for (let x = BX; x < BX + BW; x += 8) p.rect(x, r.y + r.h - 20 + ((x / 8) % 2) * 8, 8, 8, "F");
    p.rect(BX, r.y + r.h - 24, BW, 4, "V");
    wallProps(p, id, top, s);
  }
  for (const desk of FLOORS.find((f) => f.id === id)!.desks) {
    const at = extStation(desk);
    drawStation(p, DESK[desk], at.x, at.y, { t: s.t, on: s.on.has(desk), seated: true, seed: at.x });
  }
  if (id === "G") {
    p.rect(BX - 6, r.y, BW + 12, 7, "r");
    for (let x = BX - 6; x < BX + BW + 6; x += 6) p.rect(x, r.y + 7, 3, 2, "r");
    const label = "THE DAILY HABIT STUDIO";
    p.text(label, BX + BW / 2 - textWidth(label) / 2, r.y + 1, "p");
    // the cat on the awning
    const cx = BX + 170, tail = Math.floor(s.t * 2) % 2;
    p.rect(cx, r.y - 4, 7, 4, "k"); p.rect(cx + 6, r.y - 6, 3, 3, "k"); p.rect(cx + 6, r.y - 7, 1, 1, "k"); p.rect(cx + 8, r.y - 7, 1, 1, "k");
    p.rect(cx - 2 - tail, r.y - 6 + tail, 2, 1, "k");
  }
  // slab, pillars
  p.rect(BX - 6, r.y + r.h - 3, BW + 12, 3, "d");
  p.rect(BX - 6, r.y + r.h - 3, BW + 12, 1, "k");
  p.rect(BX - 6, r.y, 6, r.h, "d");
  p.rect(BX + BW, r.y, 2, r.h, "d");
  // lighting: at night a floor glows only while its desks work or the make is here
  const lit = id === s.makeFloor || FLOORS.find((f) => f.id === id)!.desks.some((d) => s.on.has(d));
  if (s.night && !lit && id !== "R") {
    const c = p.ctx; c.save(); c.globalAlpha = 0.38; c.fillStyle = p.col("V"); c.fillRect(BX, r.y, BW, r.h - 3); c.restore();
  }
  if (id === s.makeFloor) {
    const blink = Math.floor(s.t * 3) % 2;
    p.rect(BX - 12, r.y + 18, 4, 9, blink ? "r" : "k"); p.rect(BX - 14, r.y + 21, 2, 3, blink ? "r" : "k");
  }
  if (id === s.hover) {
    p.rect(BX - 1, r.y, BW + 2, 1, "r"); p.rect(BX - 1, r.y + r.h - 4, BW + 2, 1, "r");
    p.rect(BX - 1, r.y, 1, r.h - 3, "r"); p.rect(BX + BW, r.y, 1, r.h - 3, "r");
  }
}

function basement(p: Painter, s: ExtState) {
  const r = FLOOR_RECT.B;
  p.rect(0, STREET_Y + 24, EXT_W, EXT_H - STREET_Y - 24, "d");
  for (let i = 0; i < 70; i++) p.rect((i * 71) % EXT_W, STREET_Y + 26 + (i * 37) % 50, 2, 1, "b");
  p.rect(BX, r.y, BW, r.h - 2, "I");
  p.rect(BX, r.y + r.h - 14, BW, 12, "F");
  for (let shelf = 0; shelf < 3; shelf++) {
    const sy = r.y + 6 + shelf * 10;
    p.rect(BX + 8, sy + 7, 90, 2, "d");
    for (let i = 0; i < 12; i++) p.rect(BX + 10 + i * 7, sy + 1, 5, 6, (i + shelf) % 3 ? "y" : "r");
  }
  p.rect(BX + 130, r.y + 6, 50, 22, "l"); p.rect(BX + 130, r.y + 6, 50, 1, "k");
  for (let i = 0; i < 8; i++) p.rect(BX + 133 + (i % 4) * 12, r.y + 9 + Math.floor(i / 4) * 9, 9, 7, "p");
  p.text("ARCHIVE", BX + 188, r.y + 10, "V");
  if (s.hover === "B") { p.rect(BX - 1, r.y, BW + 2, 1, "r"); p.rect(BX - 1, r.y + r.h - 2, BW + 2, 1, "r"); }
}

function street(p: Painter, s: ExtState) {
  p.rect(0, STREET_Y, EXT_W, 9, "F");
  p.rect(0, STREET_Y + 9, EXT_W, 1, "k");
  p.rect(0, STREET_Y + 10, EXT_W, 14, "b");
  for (let x = (Math.floor(s.t * 20) % 24) - 24; x < EXT_W; x += 24) p.rect(x, STREET_Y + 16, 10, 1, "p");
  // the chaiwala's cart, steam rising
  const cx = 70, cy = STREET_Y - 6;
  p.grid(person({ ...CHAIWALA, talk: Math.floor(s.t * 2) % 5 === 0 }), cx + 8, cy - 15);
  p.rect(cx, cy + 1, 32, 8, "r"); p.rect(cx, cy, 32, 1, "k"); p.rect(cx + 2, cy + 9, 4, 4, "k"); p.rect(cx + 26, cy + 9, 4, 4, "k");
  p.rect(cx + 22, cy - 6, 6, 6, "m"); p.rect(cx + 28, cy - 4, 2, 1, "m");
  for (let i = 0; i < 3; i++) { const yy = cy - 9 - ((Math.floor(s.t * 6) + i * 3) % 9); p.rect(cx + 24 + (i % 2), yy, 1, 1, "p"); }
  p.rect(cx + 4, cy - 2, 2, 2, "p"); p.rect(cx + 8, cy - 2, 2, 2, "p");
  // two passers-by
  [[0.031, 0, "A"], [0.022, 0.5, "y"]].forEach(([sp, off, shirt], i) => {
    const u = ((s.t * (sp as number) + (off as number)) % 1);
    const x = Math.round(-20 + u * (EXT_W + 40));
    p.grid(person({ walk: Math.floor(s.t * 6) + i, colors: { h: i ? "d" : "k", a: shirt as string, b: "k" } }), i ? EXT_W - x : x, STREET_Y - 11, i === 1);
  });
}

function sign(p: Painter, s: ExtState) {
  const name = "THIRDSPACE PRODUCTIONS";
  const w = textWidth(name) + 8, x = Math.round(BX + BW / 2 - w / 2), y = ROOF_Y - 22;
  p.rect(x + 8, y + 10, 2, 12, "k"); p.rect(x + w - 10, y + 10, 2, 12, "k");
  p.rect(x, y, w, 11, "k");
  const flick = s.night && Math.floor(s.t * 9) % 37 === 0;
  p.text(name, x + 4, y + 3, flick ? "d" : s.night ? "g" : "r");
}

function lift(p: Painter, s: ExtState) {
  const top = ROOF_Y - 8, bottom = FLOOR_RECT.B.y + FLOOR_RECT.B.h;
  p.rect(LIFT_X, top, 18, bottom - top, "k");
  p.rect(LIFT_X + 2, top + 2, 14, bottom - top - 4, "X");
  for (let y = top + 6; y < bottom; y += 12) p.rect(LIFT_X + 8, y, 2, 6, "m");
  const y = Math.round(s.liftY);
  p.rect(LIFT_X + 2, y, 14, 21, "k"); p.rect(LIFT_X + 3, y + 1, 12, 19, "y"); p.rect(LIFT_X + 8, y + 1, 1, 19, "k");
  if (s.carrying) { p.rect(LIFT_X + 4, y + 10, 8, 6, "r"); p.rect(LIFT_X + 4, y + 10, 8, 1, "k"); }
}

function stamps(p: Painter, s: ExtState) {
  for (const st of s.stamps) {
    const at = extStation(st.desk);
    const word = st.pass ? "OK" : "FIX";
    const w = textWidth(word) + 4;
    p.rect(at.x + 6 - w / 2, at.y - 10, w, 9, st.pass ? "V" : "r");
    p.text(word, at.x + 8 - w / 2, at.y - 8, "p");
  }
}

export function drawExterior(p: Painter, s: ExtState) {
  sky(p, s);
  neighbours(p, s);
  sign(p, s);
  for (const f of FLOORS) if (f.id !== "B") floorBox(p, f.id, s);
  basement(p, s);
  street(p, s);
  lift(p, s);
  stamps(p, s);
}

export function floorAt(x: number, y: number): string | null {
  if (x < BX - 14 || x > LIFT_X + 18) return null;
  for (const f of FLOORS) { const r = FLOOR_RECT[f.id]; if (y >= r.y && y < r.y + r.h) return f.id; }
  return null;
}
export const CHAI_RECT = { x: 70, y: STREET_Y - 22, w: 34, h: 26 };
