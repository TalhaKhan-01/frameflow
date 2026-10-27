// Replay of one make (P16), from boardview.make_timeline: the clock runs in "show seconds", where long waits
// (the night before posting, Talha's approval) are squeezed so a make plays in about 75 s at 1×.
import { DESK } from "./desks";

export interface TEvent { t: number; d: number; desk: string; label: string; status: string; gate?: boolean; score?: string; say?: string; fix?: boolean }
export interface Timeline { seconds: number; events: TEvent[] }
export interface Show extends TEvent { s: number; e: number }   // start and end on the show clock

const MAX_GAP = 90;     // longest quiet stretch kept, in make seconds
const MIN_SHOW = 1.6;   // every step is on screen for at least this long at 1× (real seconds)
export const REPLAY_SECONDS = 75;

export class Player {
  shows: Show[] = [];
  length = 0;
  t = 0;
  playing = true;
  speed = 1;
  private rate = 1;     // show seconds per real second at 1×

  constructor(public tl: Timeline | null) {
    if (!tl || !tl.events.length) return;
    let shift = 0, prevEnd = 0;
    const raw = tl.events.filter((e) => DESK[e.desk]).map((e) => {
      const gap = e.t - shift - prevEnd;
      if (gap > MAX_GAP) shift += gap - MAX_GAP;
      const s = e.t - shift;
      prevEnd = Math.max(prevEnd, s + e.d);
      return { ...e, s, e: s + e.d };
    });
    const total = Math.max(...raw.map((r) => r.e), 1);
    this.rate = total / REPLAY_SECONDS;
    const min = MIN_SHOW * this.rate;
    // steps of zero length still need screen time: stretch each to the minimum, pushing later steps along
    let push = 0;
    this.shows = raw.map((r) => {
      const s = r.s + push;
      const len = Math.max(r.e - r.s, min);
      push += len - (r.e - r.s);
      return { ...r, s, e: s + len };
    });
    this.length = Math.max(...this.shows.map((s) => s.e)) + 2 * this.rate;
    this.rate = this.length / REPLAY_SECONDS;
  }

  get has() { return this.shows.length > 0; }

  tick(dt: number) {
    if (!this.playing || !this.has) return;
    this.t += dt * this.rate * this.speed;
    if (this.t > this.length) this.t = 0;   // loops: the house never stops working
  }

  seek(frac: number) { this.t = Math.max(0, Math.min(1, frac)) * this.length; }
  get frac() { return this.has ? this.t / this.length : 0; }

  active(): Show[] { return this.shows.filter((s) => s.s <= this.t && this.t < s.e); }
  current(): Show | null {
    let c: Show | null = null;
    for (const s of this.shows) if (s.s <= this.t) c = s;
    return c;
  }
  /** Steps that ended within the last `window` show seconds: their gate stamps are still on screen. */
  justEnded(window: number): Show[] { return this.shows.filter((s) => s.gate !== undefined && s.e <= this.t && this.t - s.e < window); }
  forDesk(desk: string): Show[] { return this.shows.filter((s) => s.desk === desk); }
  /** Make-clock seconds for the label under the scrubber. */
  makeSeconds(): number {
    const c = this.current();
    if (!c) return 0;
    return c.t + Math.min(this.t - c.s, c.d);
  }
  get realRate() { return this.rate; }
}
