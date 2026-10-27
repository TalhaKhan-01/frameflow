// The board's desks as people in Thirdspace House (P16): who they are, which floor, how they work and look.
// Order and labels follow frameflow/boardview.py DESKS.
export type Action = "type" | "stamp" | "talk" | "read" | "watch" | "rack" | "phone" | "beam" | "chalk" | "paint" | "wire"
  | "pad" | "book" | "clip" | "board";

export interface Desk {
  id: string;
  label: string;
  about: string;
  floor: string;
  action: Action;
  look: { colors: Record<string, string>; habit?: string };
}

const look = (h: string, a: string, b: string, habit?: string) => ({ colors: { h, a, b }, habit });

export const DESKS: Desk[] = [
  { id: "showrunner", label: "Showrunner", about: "Owns the run; turns a revise request into a change order.", floor: "5", action: "clip", look: look("k", "b", "k") },
  { id: "researcher", label: "Researcher", about: "Facts and sources for the story.", floor: "G", action: "wire", look: look("d", "y", "A") },
  { id: "factcheck", label: "Fact-checker", about: "Re-reads every source and checks every number the script says.", floor: "G", action: "stamp", look: look("k", "A", "b") },
  { id: "packaging", label: "Packaging", about: "Title, cover line and hook promise, before a word is written.", floor: "1", action: "pad", look: look("r", "p", "A") },
  { id: "writer", label: "Writer", about: "The script, in Habit's voice.", floor: "1", action: "type", look: look("A", "b", "k") },
  { id: "director", label: "Director", about: "Storyboard, beats on words, sound plan.", floor: "1", action: "board", look: look("d", "k", "b", "cap") },
  { id: "narrator", label: "Narrator · Habit", about: "Habit voices the script; timing checks run on the real voice.", floor: "2", action: "talk", look: look("h", "a", "b", "phones") },
  { id: "editor", label: "Script editor", about: "An independent table read of the script.", floor: "1", action: "read", look: look("k", "y", "b") },
  { id: "standards", label: "Standards", about: "Labels, licences and on-screen numbers.", floor: "2", action: "book", look: look("k", "m", "A") },
  { id: "animatic", label: "Animatic", about: "A 12 fps draft render, made before the real one.", floor: "3", action: "watch", look: look("A", "p", "k") },
  { id: "artdirector", label: "Art director", about: "Catches empty, black and off-brand pictures in the draft.", floor: "3", action: "paint", look: look("r", "y", "k") },
  { id: "screening", label: "Screening", about: "The full screening on the animatic, scored like a strict first viewer.", floor: "3", action: "read", look: look("d", "A", "b") },
  { id: "animator", label: "Render", about: "The delivery render, once.", floor: "4", action: "rack", look: look("k", "b", "A") },
  { id: "qc", label: "QC", about: "Loudness, black frames, motion and captions.", floor: "4", action: "type", look: look("A", "m", "b") },
  { id: "you", label: "Bade Sahab", about: "The owner: approves, revises or rejects on the hotline (Telegram). Only ever a silhouette.", floor: "5", action: "phone", look: { colors: { h: "k", s: "k", a: "k", b: "k", w: "k" } } },
  { id: "publisher", label: "Publisher", about: "Uploads to YouTube, Instagram and Facebook, then checks every post.", floor: "R", action: "beam", look: look("k", "a", "A") },
  { id: "analyst", label: "Analyst", about: "48 h results, tied back to each decision.", floor: "R", action: "chalk", look: look("d", "p", "b", "specs") },
];
export const DESK = Object.fromEntries(DESKS.map((d) => [d.id, d])) as Record<string, Desk>;

export interface Floor { id: string; name: string; short: string; desks: string[] }
export const FLOORS: Floor[] = [
  { id: "R", name: "The Roof · Dispatch & Ledger", short: "R", desks: ["publisher", "analyst"] },
  { id: "5", name: "The Cabin", short: "5", desks: ["showrunner", "you"] },
  { id: "4", name: "Post · The Engine Room", short: "4", desks: ["animator", "qc"] },
  { id: "3", name: "The Screening Room", short: "3", desks: ["animatic", "artdirector", "screening"] },
  { id: "2", name: "The Booth", short: "2", desks: ["narrator", "standards"] },
  { id: "1", name: "The Writers' Room", short: "1", desks: ["packaging", "writer", "editor", "director"] },
  { id: "G", name: "The Newsroom", short: "G", desks: ["researcher", "factcheck"] },
  { id: "B", name: "The Archive", short: "B", desks: [] },
];
export const FLOOR = Object.fromEntries(FLOORS.map((f) => [f.id, f])) as Record<string, Floor>;

export const RUNNER = look("k", "y", "A");
export const CHAIWALA = look("k", "p", "d");
