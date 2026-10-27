// A desk's workstation (P16): the desk, its props and the seated person at work. (x, y) is the seated person's
// top-left; the desk top sits at y + 11. Shared by the street view (every floor at once) and the inside view.
import { Painter, person } from "./sprites";
import type { Desk } from "./desks";

export const DESK_W = 30;

export function drawDesk(p: Painter, x: number, y: number) {
  p.rect(x - 9, y + 11, DESK_W, 3, "l");
  p.rect(x - 9, y + 14, DESK_W, 1, "k");
  p.rect(x - 9, y + 15, DESK_W, 5, "d");
  p.rect(x - 7, y + 20, 2, 4, "d");
  p.rect(x + 17, y + 20, 2, 4, "d");
}

const blinkAt = (t: number, seed: number) => ((t + seed * 1.7) % 4.3) < 0.13;

/** Props that stand behind or beside the person (drawn before them). */
function behind(p: Painter, d: Desk, x: number, y: number, t: number, on: boolean) {
  switch (d.action) {
    case "paint": {
      p.rect(x + 16, y - 4, 1, 16, "k"); p.rect(x + 23, y - 4, 1, 16, "k");
      p.rect(x + 14, y - 6, 11, 9, "p"); p.rect(x + 14, y - 6, 11, 1, "k");
      const n = on ? Math.floor(t * 2) % 5 : 3;
      for (let i = 0; i < n; i++) p.rect(x + 15 + i * 2, y - 4 + (i % 2) * 3, 2, 2, i % 2 ? "V" : "r");
      break;
    }
    case "chalk": {
      p.rect(x + 14, y - 8, 16, 12, "k"); p.rect(x + 15, y - 7, 14, 10, "V");
      const n = on ? 1 + Math.floor(t * 2) % 6 : 5;
      for (let i = 0; i < n; i++) p.rect(x + 16 + i * 2, y + 1 - Math.round(i * 1.2), 2, 1, "p");
      p.rect(x + 21, y + 4, 1, 8, "k");
      break;
    }
    case "beam": {
      p.rect(x + 15, y + 1, 9, 3, "m"); p.rect(x + 17, y + 4, 5, 2, "m"); p.rect(x + 19, y + 6, 2, 6, "k");
      if (on) for (let i = 0; i < 4; i++) { const yy = y - 4 - ((Math.floor(t * 20) + i * 5) % 22); p.rect(x + 19, yy, 1, 3, "r"); }
      break;
    }
    case "rack": {
      p.rect(x + 22, y - 10, 10, 22, "k");
      for (let i = 0; i < 6; i++) p.rect(x + 24, y - 8 + i * 3, 6, 2, "d");
      for (let i = 0; i < 6; i++) if (!on || (Math.floor(t * 8) + i * 3) % 5 < 3) p.rect(x + 29, y - 8 + i * 3, 1, 1, on ? "r" : "m");
      break;
    }
  }
}

/** Props on the desk top and in the person's hands (drawn after the desk). */
function front(p: Painter, d: Desk, x: number, y: number, t: number, on: boolean, seated: boolean) {
  const hands = (dy = 0) => { if (seated) { p.rect(x + 1, y + 10 + dy, 2, 2, "s"); p.rect(x + 9, y + 10 - dy, 2, 2, "s"); } };
  switch (d.action) {
    case "type": case "rack": {
      const mx = d.action === "rack" ? x - 8 : x + 13;
      p.rect(mx, y + 3, 9, 7, "k");
      p.rect(mx + 1, y + 4, 7, 5, on ? "X" : "m");
      if (on) for (let i = 0; i < 3; i++) p.rect(mx + 2, y + 5 + i * 1.5, 1 + ((Math.floor(t * 6) + i * 2) % 5), 1, d.action === "rack" ? "r" : "V");
      p.rect(mx + 3, y + 10, 3, 1, "k");
      hands(on && Math.floor(t * 8) % 2 ? 1 : 0);
      break;
    }
    case "stamp": {
      const ph = (t % 1.6) / 1.6, down = on && ph > 0.75;
      p.rect(x - 8, y + 10, 10, 2, "p");
      if (on && Math.floor(t / 1.6) > 0 && !down) p.rect(x - 5, y + 10, 5, 1, "r");
      const sy = down ? y + 4 : y - 2;
      p.rect(x + 13, sy, 2, 4, "k"); p.rect(x + 11, sy + 4, 6, 2, "r"); p.rect(x + 10, sy + 2, 2, 2, "s");
      for (let i = 0; i < 3; i++) p.rect(x + 18, y + 9 - i * 2, 4, 2, i % 2 ? "p" : "l");
      hands();
      break;
    }
    case "talk": {
      p.rect(x + 15, y + 2, 1, 9, "m"); p.rect(x + 13, y - 2, 5, 5, "k"); p.rect(x + 14, y - 1, 3, 3, "m");
      if (on && Math.floor(t * 7) % 2 === 0) { p.rect(x + 20, y - 2, 1, 4, "r"); p.rect(x + 23, y - 3, 1, 6, "r"); }
      p.rect(x - 7, y + 10, 7, 2, "p");
      hands();
      break;
    }
    case "read": {
      if (seated) { p.rect(x + 1, y + 7, 10, 6, "p"); for (let i = 0; i < 3; i++) p.rect(x + 2, y + 8 + i * 2, on ? 4 + ((i + Math.floor(t * 3)) % 4) : 6, 1, "m"); }
      p.rect(x + 14, y + 10, 6, 2, "p");
      break;
    }
    case "watch": {
      p.rect(x + 14, y + 5, 7, 5, "k"); p.rect(x + 13, y + 6, 1, 3, on && Math.floor(t * 12) % 3 ? "g" : "m");
      hands();
      break;
    }
    case "phone": {
      const ring = on && Math.floor(t * 10) % 4 < 2;
      const dx = ring ? (Math.floor(t * 30) % 2 ? 1 : -1) : 0;
      p.rect(x + 14 + dx, y + 8, 7, 3, "k"); p.rect(x + 14 + dx, y + 7, 7, 1, "r");
      if (ring) { p.rect(x + 17, y + 1, 1, 3, "r"); p.rect(x + 17, y + 5, 1, 1, "r"); }
      p.rect(x - 7, y + 10, 6, 1, "A");
      hands();
      break;
    }
    case "wire": {
      p.rect(x + 13, y + 5, 9, 6, "m"); p.rect(x + 14, y + 6, 7, 2, "k");
      const len = on ? 1 + Math.floor(t * 4) % 8 : 3;
      p.rect(x + 22, y + 9, 2, 1, "p"); p.rect(x + 23, y + 9, 1, len, "p");
      hands(on && Math.floor(t * 6) % 2 ? 1 : 0);
      break;
    }
    case "pad": {
      p.rect(x - 7, y + 9, 9, 3, "p");
      const n = on ? 1 + Math.floor(t * 3) % 6 : 4;
      for (let i = 0; i < n; i++) p.rect(x - 6 + i, y + 10 + (i % 2), 1, 1, "r");
      hands();
      break;
    }
    case "book": {
      p.rect(x - 7, y + 9, 12, 3, "p"); p.rect(x - 1, y + 9, 1, 3, "k");
      if (on && Math.floor(t * 2) % 2) { p.rect(x + 1, y + 10, 1, 1, "r"); p.rect(x + 2, y + 11, 1, 1, "r"); p.rect(x + 3, y + 9, 1, 2, "r"); }
      hands();
      break;
    }
    case "clip": {
      if (seated) { p.rect(x + 2, y + 8, 7, 6, "y"); p.rect(x + 4, y + 7, 3, 1, "k"); }
      p.rect(x + 14, y + 9, 5, 3, "p");
      break;
    }
    case "board": {
      for (let i = 0; i < 4; i++) p.rect(x + 13 + (i % 2) * 5, y + 8 + Math.floor(i / 2) * 2, 4, 2, i === Math.floor(t * 2) % 4 && on ? "r" : "p");
      hands();
      break;
    }
    case "beam": case "chalk": case "paint": hands(); break;
  }
}

export interface StationOpts { t: number; on: boolean; seated: boolean; seed: number; talk?: boolean }

/** The desk, props and (when seated) the person. */
export function drawStation(p: Painter, d: Desk, x: number, y: number, o: StationOpts) {
  behind(p, d, x, y, o.t, o.on);
  if (o.seated) {
    const talk = o.talk ?? ((d.action === "talk" || d.action === "read") && o.on && Math.floor(o.t * 7) % 2 === 0);
    p.grid(person({ ...d.look, talk, seated: true, blink: blinkAt(o.t, o.seed) }), x, y + (o.on ? 0 : 1));
  }
  drawDesk(p, x, y);
  front(p, d, x, y, o.t, o.on, o.seated);
}
