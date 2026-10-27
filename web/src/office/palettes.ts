// The office's palettes: every sprite pixel is a slot letter, each palette maps slots to colours (P16 style sampler).
// Slots: k ink · s skin · h hair · a/A shirt (two desks) · b trousers · w collar · o mouth · G glasses · c cap · m metal
// d dark wood · l light wood · p paper · y folder · r signal red · g lamp glow · f/F floor · W/V wall and wainscot · I inside wall · X foam.
export type Slot = string;
export interface Palette {
  id: string;
  name: string;
  feel: string;
  bg: string;
  slots: Record<Slot, string>;
  fx: { riso?: string; grain?: number; glow?: boolean };
  type: { head: string; body: string };
  swatches: string[];
}

export const PALETTES: Palette[] = [
  {
    id: "riso", name: "A · Riso Press", feel: "Pixel art printed in two inks on cream paper: editorial red, ink blue, a 1 px misregistration and grain. Grows out of Paper Press.",
    bg: "#F3EBDD",
    slots: { k: "#1B1B1B", s: "#F0B8A8", h: "#1F3A93", a: "#D2392B", A: "#1F3A93", b: "#5B2A6E", w: "#F3EBDD", o: "#1B1B1B", G: "#1B1B1B",
      c: "#D2392B", m: "#7F8CC0", d: "#5B2A6E", l: "#E7A598", p: "#FBF6EC", y: "#F2C6BC", r: "#D2392B", g: "#FF6B5B",
      f: "#ECE1CC", F: "#E3D5BC", W: "#EADCC4", I: "#F2DDD2", V: "#1F3A93", X: "#C9D0EA" },
    fx: { riso: "#1F3A93", grain: 0.11 },
    type: { head: "Fraunces", body: "JetBrains Mono" },
    swatches: ["#F3EBDD", "#D2392B", "#1F3A93", "#5B2A6E", "#1B1B1B"],
  },
  {
    id: "chai", name: "B · Chai Stall Warm", feel: "A desi street-studio: terracotta, turmeric, teal-green and old wood, like a Mumbai production office above a chai stall.",
    bg: "#F6E9D2",
    slots: { k: "#3A2418", s: "#C68B59", h: "#2B1B12", a: "#C8553D", A: "#2A7F62", b: "#6B4226", w: "#F6E9D2", o: "#3A2418", G: "#3A2418",
      c: "#E9B44C", m: "#8A9A8B", d: "#6B4226", l: "#A86B3C", p: "#FBF4E6", y: "#E9B44C", r: "#C8553D", g: "#FFD166",
      f: "#E8D3B0", F: "#DCC29A", W: "#F0DDBA", I: "#F3E1C4", V: "#2A7F62", X: "#D9B98A" },
    fx: { grain: 0.06 },
    type: { head: "Kalam", body: "Inter" },
    swatches: ["#F6E9D2", "#C8553D", "#E9B44C", "#2A7F62", "#6B4226"],
  },
  {
    id: "night", name: "C · Night Shift", feel: "The studio after dark, lit by monitors and the ON AIR lamp: navy, monitor teal, signal red and lamp amber.",
    bg: "#0E1530",
    slots: { k: "#05081A", s: "#D9A07A", h: "#0B0F24", a: "#35D0BA", A: "#FFB547", b: "#2A3466", w: "#C9F5EE", o: "#05081A", G: "#05081A",
      c: "#FF4D4D", m: "#4A5690", d: "#2A2F55", l: "#3B4380", p: "#B9C6E8", y: "#FFB547", r: "#FF4D4D", g: "#FF4D4D",
      f: "#18224A", F: "#141C3E", W: "#1B2550", I: "#1F2A5A", V: "#24306A", X: "#222D5E" },
    fx: { glow: true },
    type: { head: "JetBrains Mono", body: "Inter" },
    swatches: ["#0E1530", "#35D0BA", "#FF4D4D", "#FFB547", "#4A5690"],
  },
  {
    id: "lofi", name: "D · Lofi Pastel", feel: "A cosy, soft studio: cream, sage, dusty pink and lavender. Calm and friendly, like a study-with-me stream.",
    bg: "#F6E7D7",
    slots: { k: "#2E2A2A", s: "#F1C9B0", h: "#6B4E3D", a: "#E8A9A0", A: "#B6A6D9", b: "#8FAE8A", w: "#FFF8EF", o: "#2E2A2A", G: "#2E2A2A",
      c: "#B6A6D9", m: "#B6A6D9", d: "#B89A80", l: "#D9BFA3", p: "#FFFDF8", y: "#F2D492", r: "#E07A6E", g: "#F7B267",
      f: "#EBD9C6", F: "#E3CDB8", W: "#EFDDCB", I: "#F4E3D6", V: "#A8C3A0", X: "#DCCDE9" },
    fx: { grain: 0.04 },
    type: { head: "Fraunces", body: "Inter" },
    swatches: ["#F6E7D7", "#A8C3A0", "#E8A9A0", "#B6A6D9", "#2E2A2A"],
  },
];
