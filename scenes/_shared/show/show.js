/* The Daily Habit show (P24.4, ported from spikes/studio-show): The Daily Habit as a show. One composition draws a set (riso | paper | night),
   a Habit look (pixel | puppet) and the four framings (wide | split | pip | full), plus the show package
   (sting, lane bug, lower-third, source chip, PiP frame, ticker, captions, end card).

   Determinism: the camera, the framing, Habit's pose, captions and the ticker are pure functions of time,
   computed in one clock tween's onUpdate (seek-safe in any order). Graphics enter with one fromTo each and are
   shown or hidden by frame(t). Nothing reads the clock or calls Math.random. */
(() => {
  const W = 1080, H = 1920;
  const FACE = { x: 540, y: 1090 };   // Habit's face in set space (the desk shot)

  // ---------- sets: tokens, fonts, filters ----------
  const SETS = {
    riso: { bg: "#F3EBDD", panel: "#ECE1CC", panel2: "#E3D5BC", ink: "#1B1B1B", red: "#D2392B", blue: "#1F3A93", purple: "#5B2A6E",
      soft: "#7F8CC0", dark: "#1B1B1B", text: "#1B1B1B", textOnRed: "#F3EBDD", head: '"FF Serif", Georgia, serif', body: '"FF Mono", monospace',
      hand: '"FF Hand", cursive', grain: 0.11, filter: "riso", seam: "#F3EBDD", wallBg: "#1F3A93", wallInk: "#F3EBDD" },
    paper: { bg: "#f3eee4", panel: "#e6dece", panel2: "#d9cdb6", ink: "#1d1a22", red: "#c8372a", blue: "#1f5fd1", purple: "#7a4fd6",
      soft: "#9fb3d9", dark: "#1d1a22", text: "#1d1a22", textOnRed: "#fbf8f1", head: '"FF Serif", Georgia, serif', body: '"FF Body", sans-serif',
      hand: '"FF Hand", cursive', grain: 0.07, filter: "paper", seam: "#f3eee4", wallBg: "#fbf8f1", wallInk: "#1d1a22" },
    night: { bg: "#0b0e1c", panel: "#151a30", panel2: "#1d2442", ink: "#EDEBF5", red: "#FF5A4E", blue: "#4F7BFF", purple: "#9B6BFF",
      soft: "#3a4470", dark: "#050714", text: "#EDEBF5", textOnRed: "#0b0e1c", head: '"FF Display", sans-serif', body: '"FF Body", sans-serif',
      hand: '"FF Display", sans-serif', grain: 0.05, filter: "night", seam: "#0b0e1c", wallBg: "#060814", wallInk: "#7FA0FF" },
  };

  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}, parent = null) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };
  const div = (parent, css, cls) => { const d = document.createElement("div"); d.style.cssText = css; if (cls) d.className = cls; parent.appendChild(d); return d; };
  const svgBox = (parent, w = W, h = H, css = "position:absolute;left:0;top:0") => {
    const s = el("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h }); s.style.cssText = css; parent.appendChild(s); return s;
  };
  const txt = (parent, x, y, str, o = {}) => {
    const t = el("text", { x, y, "text-anchor": o.anchor ?? "middle", "dominant-baseline": o.baseline ?? "middle", fill: o.fill,
      "font-family": o.font, "font-weight": o.weight ?? 700, "font-size": o.size ?? 44, "letter-spacing": o.spacing ?? 0 }, parent);
    t.textContent = str;
    return t;
  };
  const fit = (t, maxW, size) => { let fs = size; t.setAttribute("font-size", fs); while (t.getComputedTextLength() > maxW && fs > 14) { fs -= 2; t.setAttribute("font-size", fs); } };
  const lerp = (a, b, k) => a + (b - a) * k;
  const ease = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);   // cubic in-out
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));

  function defs(svg, S) {
    const d = el("defs", {}, svg);
    // riso: a second ink plate 1.5 px off register, multiplied under the first
    const r = el("filter", { id: "f-riso", x: "-5%", y: "-5%", width: "110%", height: "110%" }, d);
    el("feFlood", { "flood-color": S.blue, "flood-opacity": 0.45, result: "c" }, r);
    el("feComposite", { in: "c", in2: "SourceAlpha", operator: "in", result: "m" }, r);
    el("feOffset", { in: "m", dx: 2, dy: 1.5, result: "o" }, r);
    const mr = el("feMerge", {}, r); el("feMergeNode", { in: "o" }, mr); el("feMergeNode", { in: "SourceGraphic" }, mr);
    // paper: cut edges wobble a little and every piece casts a soft shadow
    const p = el("filter", { id: "f-paper", x: "-5%", y: "-5%", width: "110%", height: "115%" }, d);
    el("feTurbulence", { type: "fractalNoise", baseFrequency: 0.035, numOctaves: 2, seed: 4, result: "n" }, p);
    el("feDisplacementMap", { in: "SourceGraphic", in2: "n", scale: 4, result: "w" }, p);
    el("feDropShadow", { in: "w", dx: 0, dy: 7, stdDeviation: 5, "flood-color": "#3b2f1e", "flood-opacity": 0.28 }, p);
    // night: neon glow
    const g = el("filter", { id: "f-night", x: "-10%", y: "-10%", width: "120%", height: "120%" }, d);
    el("feGaussianBlur", { in: "SourceGraphic", stdDeviation: 7, result: "b" }, g);
    const gm = el("feMerge", {}, g); el("feMergeNode", { in: "b" }, gm); el("feMergeNode", { in: "SourceGraphic" }, gm);
    // seam gradient for the split (the set's paper colour)
    return d;
  }
  const look = (S) => `url(#f-${S.filter})`;

  // ---------- the sets ----------
  function drawSetBack(svg, S, cfg) {
    defs(svg, S);
    const g = el("g", { filter: look(S) }, svg);
    el("rect", { x: 0, y: 0, width: W, height: H, fill: S.bg }, svg).parentNode.insertBefore(svg.lastChild, g);
    if (cfg.set === "riso") {
      // back wall: printed pixel bricks in two inks, a pixel window strip, the video wall
      for (let y = 120; y < 1330; y += 40) for (let x = (y / 40) % 2 ? 0 : -40; x < W; x += 80)
        el("rect", { x: x + 2, y: y + 2, width: 76, height: 36, fill: (x + y) % 240 === 0 ? S.panel2 : S.panel }, g);
      el("rect", { x: 0, y: 0, width: W, height: 120, fill: S.blue }, g);
      el("rect", { x: 0, y: 120, width: W, height: 10, fill: S.red }, g);
      FF.pixelText(g, 540, 250, "FLOOR 2 THE STUDIO", 6, "a");
      el("rect", { x: 120, y: 330, width: 840, height: 540, fill: S.ink }, g);
      el("rect", { x: 140, y: 350, width: 800, height: 500, fill: S.wallBg }, g);
      for (let i = 0; i < 4; i++) el("rect", { x: 70 + i * 260, y: 1210, width: 160, height: 30, fill: S.red }, g);   // studio lights strip
      // lamp + plant, pixel style
      FF.pixel(g, ["..kkkk..", ".kyyyyk.", "kyyyyyyk", "...kk...", "...kk...", "...kk...", "..kkkk.."], 60, 900, 14, { y: "#F2C6BC" });
      FF.pixel(g, ["..g.g.g.", ".ggggggg", "gg.ggg.g", ".ggggggg", "..aaaaa.", "..aaaaa.", "...aaa.."], 900, 1180, 16, { g: "#2A7F62", a: S.red });
    } else if (cfg.set === "paper") {
      // newspaper wall made of cut-paper sheets, a paper-craft screen, bunting
      el("rect", { x: 0, y: 0, width: W, height: 1330, fill: "#e9e1d0" }, g);
      const sheets = [[30, 880, 290, 380, -3], [760, 890, 290, 380, 4], [960, 330, 280, 360, 2], [-160, 340, 280, 380, -2]];
      sheets.forEach(([x, y, w, h, r], i) => {
        const sg = el("g", { transform: `rotate(${r} ${x + w / 2} ${y + h / 2})` }, g);
        el("rect", { x, y, width: w, height: h, fill: "#fbf8f1" }, sg);
        txt(sg, x + w / 2, y + 44, ["THE DAILY", "HABIT", "TECH", "TIMES"][i], { size: 34, font: S.head, fill: S.ink, weight: 800 });
        for (let l = 0; l < 9; l++) el("rect", { x: x + 22, y: y + 90 + l * 30, width: w - 44 - (l % 3) * 30, height: 9, fill: "#cfc4b0" }, sg);
      });
      el("rect", { x: 150, y: 330, width: 780, height: 520, rx: 18, fill: S.ink }, g);
      el("rect", { x: 170, y: 350, width: 740, height: 480, rx: 10, fill: S.wallBg }, g);
      for (let i = 0; i < 9; i++) el("path", { d: `M ${60 + i * 110} 130 l 55 0 l -27 60 z`, fill: i % 2 ? S.red : S.blue }, g);
      el("path", { d: "M 40 128 Q 540 170 1040 128", stroke: S.ink, "stroke-width": 4, fill: "none" }, g);
    } else {
      // night: LED video wall of tiles, light-sweep rails, glowing floor line
      el("rect", { x: 0, y: 0, width: W, height: 1330, fill: "#0e1226" }, g);
      for (let r = 0; r < 12; r++) for (let c = 0; c < 9; c++)
        el("rect", { x: 30 + c * 115, y: 140 + r * 95, width: 105, height: 85, rx: 6, fill: (r * 7 + c * 3) % 11 === 0 ? "#1a2350" : "#121833" }, g);
      el("rect", { x: 130, y: 330, width: 820, height: 520, rx: 14, fill: "none", stroke: S.blue, "stroke-width": 6 }, g);
      el("rect", { x: 140, y: 340, width: 800, height: 500, rx: 10, fill: S.wallBg }, g);
      el("rect", { x: 0, y: 1300, width: W, height: 6, fill: S.red }, g);
      for (let i = 0; i < 3; i++) el("rect", { class: "sweep", x: -300, y: 120, width: 220, height: 1200, fill: "url(#sweep)", opacity: 0.0 }, svg);
      const lg = el("linearGradient", { id: "sweep", x1: 0, x2: 1 }, svg.querySelector("defs"));
      el("stop", { offset: 0, "stop-color": S.blue, "stop-opacity": 0 }, lg);
      el("stop", { offset: 0.5, "stop-color": S.blue, "stop-opacity": 0.35 }, lg);
      el("stop", { offset: 1, "stop-color": S.blue, "stop-opacity": 0 }, lg);
    }
    // floor
    el("rect", { x: 0, y: 1330, width: W, height: 590, fill: cfg.set === "night" ? "#080a16" : S.panel2 }, g);
    return g;
  }

  function drawWall(svg, S, cfg) {   // what the video wall behind Habit says; changes per beat (set by frame)
    const g = el("g", {}, svg);
    const label = txt(g, 540, 600, "", { size: 150, font: S.head, fill: S.wallInk, weight: 800 });
    const sub = txt(g, 540, 760, "", { size: 40, font: S.body, fill: S.wallInk, weight: 600, spacing: 4 });
    return { set(main, small) { if (label.textContent !== main) { label.textContent = main; fit(label, 720, 150); } sub.textContent = small || ""; } };
  }

  function drawDesk(svg, S, cfg) {
    const g = el("g", { filter: look(S) }, svg);
    if (cfg.set === "riso") {
      el("rect", { x: 60, y: 1320, width: 960, height: 30, fill: S.ink }, g);
      el("rect", { x: 90, y: 1350, width: 900, height: 380, fill: S.red }, g);
      FF.pixelText(g, 540, 1470, "THE DAILY HABIT", 12, "p");
      for (let i = 0; i < 9; i++) el("rect", { x: 110 + i * 100, y: 1600, width: 60, height: 12, fill: S.bg }, g);
      FF.pixel(g, ["kkkkk", "kpppk.", "kpppkk", "kpppk.", ".kkk."], 760, 1250, 12, { p: S.bg });   // chai cup
    } else if (cfg.set === "paper") {
      el("path", { d: "M 70 1325 L 1010 1318 L 990 1360 L 90 1365 Z", fill: "#3b3743" }, g);
      el("path", { d: "M 95 1362 L 985 1356 L 975 1730 L 105 1735 Z", fill: S.red }, g);
      txt(g, 540, 1470, "The Daily Habit", { size: 92, font: S.head, fill: "#fbf8f1", weight: 800 });
      txt(g, 540, 1560, "A THIRDSPACE PRODUCTION", { size: 30, font: S.body, fill: "#fbf8f1", weight: 600, spacing: 6 });
      el("rect", { x: 740, y: 1240, width: 70, height: 84, rx: 8, fill: "#fbf8f1", stroke: S.ink, "stroke-width": 4 }, g);
    } else {
      el("rect", { x: 70, y: 1318, width: 940, height: 26, rx: 6, fill: "#1d2442" }, g);
      el("rect", { x: 70, y: 1318, width: 940, height: 4, fill: S.blue }, g);
      el("rect", { x: 100, y: 1344, width: 880, height: 390, rx: 10, fill: "#10142a", stroke: S.red, "stroke-width": 4 }, g);
      txt(g, 540, 1470, "THE DAILY HABIT", { size: 84, font: S.head, fill: S.ink, weight: 700, spacing: 6 });
      el("rect", { x: 300, y: 1530, width: 480, height: 5, fill: S.red }, g);
    }
    return g;
  }

  // ---------- Habit, two looks: one pose API (mouth 0-1, blink 0-1, lookX/lookY -1..1, bob px, brow 0-1) ----------
  const SKIN = "#F0B8A8", HAIR = "#1F3A93", PHONES = "#7F8CC0", SHIRT = "#D2392B", INK = "#1B1B1B", CREAM = "#F3EBDD";

  function rigPixel(parent) {
    const C = 28, left = FACE.x - 6 * C, top = FACE.y - 4.5 * C;
    const box = div(parent, `position:absolute;left:${left}px;top:${top}px;width:${12 * C}px;height:${19 * C}px`);
    const s = svgBox(box, 12 * C, 19 * C, "position:absolute;left:0;top:0");
    const grid = FF.HABIT_PX.map((r, i) => (i === 6 ? r.replace(/o/g, "s") : i === 4 ? r.replace(/k/g, "s") : r));
    const body = FF.pixel(s, grid, 0, 0, C);
    const eyes = [3, 8].map((c) => el("rect", { x: c * C, y: 4 * C, width: C, height: C, fill: INK }, s));
    const mouth = el("rect", { x: 5 * C, y: 6 * C, width: 2 * C, height: C, fill: INK }, s);
    const tongue = el("rect", { x: 5 * C, y: 7 * C, width: 2 * C, height: C * 0.6, fill: SHIRT }, s);
    return { el: box, pose(p) {
      const h = p.blink > 0.5 ? C * 0.25 : C;
      eyes.forEach((e, i) => { e.setAttribute("y", 4 * C + (C - h) + Math.round(p.lookY) * -C * 0.0); e.setAttribute("height", h);
        e.setAttribute("x", ([3, 8][i] + (p.lookX > 0.35 ? 0.34 : p.lookX < -0.35 ? -0.34 : 0)) * C); });
      const m = p.mouth;   // pixel mouths step: closed line, half, open with tongue
      mouth.setAttribute("height", m < 0.15 ? C * 0.3 : m < 0.5 ? C * 0.65 : C);
      mouth.setAttribute("y", 6 * C + (m < 0.15 ? C * 0.35 : 0));
      tongue.setAttribute("opacity", m >= 0.5 ? 1 : 0);
      box.style.transform = `translateY(${Math.round(p.bob / 4) * 4}px)`;   // pixel steps
    } };
  }

  function rigPuppet(parent) {
    const box = div(parent, `position:absolute;left:${FACE.x - 180}px;top:${FACE.y - 230}px;width:360px;height:560px`);
    const s = svgBox(box, 360, 560, "position:absolute;left:0;top:0;overflow:visible");
    const st = { stroke: INK, "stroke-width": 5, "stroke-linejoin": "round" };
    const misreg = el("g", { transform: "translate(3 2)", opacity: 0.35 }, s);   // riso second plate
    const body = el("g", {}, s);
    el("path", { d: "M 40 560 Q 40 400 180 392 Q 320 400 320 560 Z", fill: SHIRT, ...st }, body);
    el("path", { d: "M 150 392 L 180 440 L 210 392 Z", fill: CREAM, ...st }, body);
    el("rect", { x: 155, y: 330, width: 50, height: 70, fill: SKIN, ...st }, body);
    const head = el("g", {}, s);
    el("ellipse", { cx: 180, cy: 228, rx: 108, ry: 122, fill: SKIN, ...st }, head);
    el("path", { d: "M 76 214 Q 70 98 180 96 Q 292 98 286 214 Q 250 150 180 156 Q 112 150 76 214 Z", fill: HAIR, ...st }, head);
    el("path", { d: "M 64 236 Q 64 70 180 66 Q 296 70 296 236", fill: "none", stroke: PHONES, "stroke-width": 20, "stroke-linecap": "round" }, head);
    el("rect", { x: 44, y: 196, width: 44, height: 92, rx: 18, fill: HAIR, ...st }, head);
    el("rect", { x: 272, y: 196, width: 44, height: 92, rx: 18, fill: HAIR, ...st }, head);
    el("circle", { cx: 116, cy: 282, r: 16, fill: "#FF6B5B", opacity: 0.45 }, head);
    el("circle", { cx: 244, cy: 282, r: 16, fill: "#FF6B5B", opacity: 0.45 }, head);
    const brows = el("g", {}, head);
    const bL = el("path", { d: "M 120 196 Q 140 186 160 194", fill: "none", stroke: INK, "stroke-width": 7, "stroke-linecap": "round" }, brows);
    const bR = el("path", { d: "M 200 194 Q 220 186 240 196", fill: "none", stroke: INK, "stroke-width": 7, "stroke-linecap": "round" }, brows);
    const eyes = el("g", {}, head);
    const eL = el("ellipse", { cx: 140, cy: 230, rx: 12, ry: 16, fill: INK }, eyes);
    const eR = el("ellipse", { cx: 220, cy: 230, rx: 12, ry: 16, fill: INK }, eyes);
    const gL = el("circle", { cx: 144, cy: 224, r: 4, fill: "#fff" }, eyes), gR = el("circle", { cx: 224, cy: 224, r: 4, fill: "#fff" }, eyes);
    const mouthO = el("ellipse", { cx: 180, cy: 300, rx: 24, ry: 4, fill: "#5B1D1D", ...st, "stroke-width": 4 }, head);
    const tongue = el("ellipse", { cx: 180, cy: 312, rx: 14, ry: 6, fill: "#FF6B5B" }, head);
    const smile = el("path", { d: "M 152 296 Q 180 318 208 296", fill: "none", stroke: INK, "stroke-width": 6, "stroke-linecap": "round" }, head);
    misreg.innerHTML = `<ellipse cx="180" cy="228" rx="108" ry="122" fill="#1F3A93"/><path d="M 40 560 Q 40 400 180 392 Q 320 400 320 560 Z" fill="#1F3A93"/>`;
    return { el: box, pose(p) {
      const e = p.emo || EMO.neutral;   // emotion: brows (tilt: + = inner ends up, worried), eyes (open), smile (-1 frown .. 1 grin)
      const ry = 16 * e.eye * (1 - 0.9 * p.blink);
      eL.setAttribute("ry", ry); eR.setAttribute("ry", ry * (e.eyeR ?? 1));
      gL.setAttribute("opacity", e.eye < 0.45 ? 0 : 1); gR.setAttribute("opacity", e.eye < 0.45 ? 0 : 1);
      eyes.setAttribute("transform", `translate(${p.lookX * 9} ${p.lookY * -7})`);
      brows.setAttribute("transform", `translate(0 ${-(p.brow * 0.5 + e.up) * 12})`);
      bL.setAttribute("transform", `rotate(${-e.tilt} 140 192) translate(0 ${-(e.upL ?? 0) * 12})`);
      bR.setAttribute("transform", `rotate(${e.tilt} 220 192) translate(0 ${-(e.upR ?? 0) * 12})`);
      smile.setAttribute("d", `M 152 ${298 - 4 * e.smile} Q 180 ${298 + 24 * e.smile} 208 ${298 - 4 * e.smile}`);
      const m = Math.max(p.mouth, p.mouth > 0.08 ? e.open ?? 0 : 0);
      mouthO.setAttribute("ry", 3 + 22 * m); mouthO.setAttribute("rx", 22 + 6 * (1 - m)); mouthO.setAttribute("cy", 300 + 8 * m);
      mouthO.setAttribute("opacity", m > 0.08 ? 1 : 0); tongue.setAttribute("opacity", m > 0.45 ? 1 : 0); tongue.setAttribute("cy", 300 + 20 * m);
      smile.setAttribute("opacity", m > 0.08 ? 0 : 1);
      head.setAttribute("transform", `rotate(${p.lookX * 4 + p.tilt} 180 330) translate(0 ${p.bob * 0.6})`);
      box.style.transform = `translateY(${p.bob * 0.4}px)`;
    } };
  }

  const RIGS = { pixel: rigPixel, puppet: rigPuppet };

  // ---------- Habit's emotions (P24.4.2): one per line, from the script ----------
  const EMO = {
    neutral:   { tilt: 0,   up: 0.1,  smile: 0.35, eye: 1 },
    excited:   { tilt: -6,  up: 0.7,  smile: 0.9,  eye: 1.2, open: 0.25 },
    surprised: { tilt: 4,   up: 1.1,  smile: 0,    eye: 1.4, open: 0.4 },
    doubtful:  { tilt: 0,   up: 0,    smile: -0.2, eye: 0.85, upL: 0.9, upR: -0.3, eyeR: 0.7 },
    smug:      { tilt: -4,  up: -0.1, smile: 0.7,  eye: 0.6, upL: 0.4 },
    worried:   { tilt: 14,  up: 0.35, smile: -0.6, eye: 1.05 },
    laughing:  { tilt: -4,  up: 0.6,  smile: 1,    eye: 0.3, open: 0.35 },
    serious:   { tilt: -10, up: -0.25, smile: 0,   eye: 0.9 },
  };
  const mixEmo = (a, b, k) => Object.fromEntries([...new Set([...Object.keys(a), ...Object.keys(b)])].map((key) =>
    [key, lerp(a[key] ?? (key === "eyeR" ? 1 : 0), b[key] ?? (key === "eyeR" ? 1 : 0), k)]));

  // ---------- framings: where the studio window is, and where the camera looks ----------
  const PIP = { x: 48, y: 1120, s: 320 };
  function framing(shot) {
    const cam = (s, tx, ty) => ({ s, tx: tx - FACE.x * s, ty: ty - FACE.y * s });
    switch (shot) {
      case "split": return { ...cam(1.6, 540, 1320), ct: 0, cr: 0, cb: 0, cl: 0, rad: 0, ma: 960, mb: 1150, op: 1 };
      case "pip": return { ...cam(1.12, PIP.x + PIP.s / 2, PIP.y + PIP.s / 2 + 30), ct: PIP.y, cr: W - PIP.x - PIP.s, cb: H - PIP.y - PIP.s, cl: PIP.x, rad: 30, ma: -2, mb: -1, op: 1 };
      case "full": return { ...cam(1.12, PIP.x + PIP.s / 2, PIP.y + PIP.s / 2 + 30), ct: PIP.y + PIP.s / 2, cr: W - PIP.x - PIP.s / 2, cb: H - PIP.y - PIP.s / 2, cl: PIP.x + PIP.s / 2, rad: 30, ma: -2, mb: -1, op: 0 };
      case "end": return { ...cam(1, 540, 1090), ct: 0, cr: 0, cb: 0, cl: 0, rad: 0, ma: -2, mb: -1, op: 0 };
      default: return { ...cam(1, 540, 1090), ct: 0, cr: 0, cb: 0, cl: 0, rad: 0, ma: -2, mb: -1, op: 1 };   // wide
    }
  }
  const mixF = (a, b, k) => Object.fromEntries(Object.keys(a).map((key) => [key, lerp(a[key], b[key], k)]));

  // ---------- graphics: data-driven builders (seg.g = {type, ...} from the director); content inside y 300-980 ----------
  function graphics(S, cfg) {
    const H1 = (g, x, y, s, size, o = {}) => txt(g, x, y, s, { size, font: S.head, fill: o.fill ?? S.text, weight: o.weight ?? 800, anchor: o.anchor });
    const B = (g, x, y, s, size, o = {}) => txt(g, x, y, s, { size, font: S.body, fill: o.fill ?? S.text, weight: o.weight ?? 600, anchor: o.anchor, spacing: o.spacing });
    const card = (g, x, y, w, h, fill, o = {}) => el("rect", { x, y, width: w, height: h, rx: o.rx ?? (cfg.set === "riso" ? 0 : 18), fill, stroke: o.stroke ?? S.ink, "stroke-width": o.sw ?? 5 }, g);
    const piv = (n, x, y) => gsap.set(n, { svgOrigin: `${x} ${y}` });
    const paper = cfg.set === "night" ? "#10142a" : "#fbf8f1";
    // "₹16.3B", "90%", "60,000", "10x": prefix, number, suffix, decimals (count-ups keep the source's format)
    const parseNum = (v) => { const m = String(v ?? "").match(/^([^\d-]*)(-?[\d,]*\.?\d+)(.*)$/); if (!m) return null;
      const raw = m[2]; return { pre: m[1], n: parseFloat(raw.replace(/,/g, "")), dec: (raw.split(".")[1] || "").length, comma: raw.includes(","), suf: m[3] }; };
    const fmt = (p, v) => { let s = v.toFixed(p.dec); if (p.comma) s = Number(s).toLocaleString("en-IN", { minimumFractionDigits: p.dec, maximumFractionDigits: p.dec }); return p.pre + s + p.suf; };
    const countUp = (tl, node, value, t0, dur = 1.1, maxW = 0) => {   // sized once on the final value (seek-safe)
      node.textContent = String(value ?? ""); if (maxW) fit(node, maxW, +node.getAttribute("font-size"));
      const p = parseNum(value); if (!p) return;
      const o = { v: 0 }; node.textContent = fmt(p, 0);
      tl.fromTo(o, { v: 0 }, { v: p.n, duration: dur, ease: "power3.out", onUpdate: () => (node.textContent = fmt(p, o.v)) }, t0);
    };
    const wrap = (str, max) => { const out = []; let cur = ""; String(str || "").split(/\s+/).forEach((w) => { if ((cur + " " + w).trim().length > max && cur) { out.push(cur); cur = w; } else cur = (cur + " " + w).trim(); }); if (cur) out.push(cur); return out; };
    const kicker = (g, tl, t0, s, y = 930) => { if (!s) return; const k = B(g, 540, y, String(s).toUpperCase(), 38, { spacing: 2, weight: 800 }); fit(k, 960, 38);
      tl.fromTo(k, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.35 }, t0); };
    return {
      headline(g, tl, t0, d) {
        const a = H1(g, 540, 470, d.top || "", 120), b = H1(g, 540, 640, d.bottom || "", 150, { fill: S.red });
        fit(a, 960, 120); fit(b, 960, 150);
        const bar = el("rect", { x: 140, y: 730, width: 800, height: 16, fill: S.blue }, g); piv(bar, 140, 738);
        [a, b].forEach((n, i) => { piv(n, 540, 470 + i * 170); tl.fromTo(n, { scale: 2.2, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.24, ease: "power4.in" }, t0 + 0.05 + i * 0.22); });
        tl.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: 0.4, ease: "power3.out" }, t0 + 0.6);
        kicker(g, tl, t0 + 1.2, d.kicker, 840);
      },
      stat(g, tl, t0, d) {
        const num = H1(g, 540, 520, "", 300, { fill: S.red });
        countUp(tl, num, d.value, t0 + 0.1, 1.2, 980);
        const l1 = B(g, 540, 720, String(d.label || "").toUpperCase(), 46, { weight: 800, spacing: 1 }); fit(l1, 960, 46);
        tl.fromTo(l1, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.35 }, t0 + 0.8);
        if (d.sub) { const l2 = H1(g, 540, 810, d.sub, 60, { fill: S.blue }); fit(l2, 960, 60); tl.fromTo(l2, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.35 }, t0 + 1.15); }
        const p = parseNum(d.value);
        if (p && String(d.value).includes("%") && p.n <= 100) {   // a 100-dot grid for a share
          const dots = el("g", {}, g);
          for (let i = 0; i < 100; i++) el("rect", { x: 240 + (i % 25) * 24, y: 880 + Math.floor(i / 25) * 24, width: 18, height: 18, rx: 3, fill: i < Math.round(p.n) ? S.red : S.soft }, dots);
          tl.fromTo(dots.children, { opacity: 0 }, { opacity: 1, duration: 0.05, stagger: 0.01 }, t0 + 1.4);
        }
      },
      versus(g, tl, t0, d) {
        const side = (x, item, fill, i) => {
          const c = el("g", {}, g);
          card(c, x - 185, 330, 370, 470, i ? S.panel : paper);
          const lab = wrap(item?.label, 16).slice(0, 3);
          lab.forEach((l, k) => { const n = B(c, x, 400 + k * 46, l.toUpperCase(), 36, { weight: 800 }); fit(n, 330, 36); });
          const v = H1(c, x, 640, "", 120, { fill });
          countUp(tl, v, item?.value, t0 + 0.5 + i * 0.5, 1.0, 330);
          tl.fromTo(c, { opacity: 0, x: i ? 120 : -120 }, { opacity: 1, x: 0, duration: 0.45, ease: "power3.out" }, t0 + i * 0.35);
        };
        side(290, d.left, S.blue, 0); side(790, d.right, S.red, 1);
        const vs = H1(g, 540, 565, "VS", 54, { fill: S.ink }); piv(vs, 540, 565);
        tl.fromTo(vs, { scale: 0 }, { scale: 1, duration: 0.35, ease: "back.out(2.5)" }, t0 + 0.7);
        kicker(g, tl, t0 + 1.8, d.caption, 880);
      },
      bars(g, tl, t0, d) {
        const items = (d.items || []).slice(0, 4);
        const max = Math.max(...items.map((x) => Math.abs(parseNum(x.value)?.n ?? 0)), 1e-9);
        const top = 360, gap = items.length > 3 ? 130 : 160;
        items.forEach((it, i) => {
          const y = top + i * gap;
          const lab = B(g, 110, y, String(it.label || "").toUpperCase(), 34, { anchor: "start", weight: 800 }); fit(lab, 860, 34);
          const w = 40 + 700 * Math.abs(parseNum(it.value)?.n ?? 0) / max;
          const bar = el("rect", { x: 110, y: y + 26, width: w, height: 64, rx: cfg.set === "riso" ? 0 : 10, fill: i === (d.highlight ?? 0) ? S.red : S.blue }, g); piv(bar, 110, y + 58);
          const v = B(g, 110 + w + 18, y + 60, "", 46, { anchor: "start", weight: 800 });
          tl.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: "power3.out" }, t0 + 0.2 + i * 0.3);
          countUp(tl, v, it.value, t0 + 0.2 + i * 0.3, 0.6);
          if (w > 760) { v.setAttribute("x", 110 + w - 18); v.setAttribute("text-anchor", "end"); v.setAttribute("fill", "#fbf8f1"); }
        });
        kicker(g, tl, t0 + 0.4 + items.length * 0.3, d.caption, 920);
      },
      quote(g, tl, t0, d) {
        card(g, 90, 300, 900, 620, paper);
        H1(g, 170, 420, "“", 200, { fill: S.red, anchor: "start" });
        const lines = wrap(d.text, 26).slice(0, 5);
        const ns = lines.map((l, i) => { const n = H1(g, 540, 470 + i * 78, l, 62); fit(n, 820, 62); return n; });
        tl.fromTo(ns, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.3, stagger: 0.18 }, t0 + 0.2);
        if (d.who) { const w = B(g, 540, 470 + lines.length * 78 + 40, "— " + String(d.who).toUpperCase(), 34, { spacing: 2, fill: S.red, weight: 800 }); fit(w, 820, 34);
          tl.fromTo(w, { opacity: 0 }, { opacity: 1, duration: 0.3 }, t0 + 0.4 + lines.length * 0.18); }
      },
      list(g, tl, t0, d) {
        const title = H1(g, 540, 380, d.title || "", 80, { fill: S.red }); fit(title, 960, 80);
        tl.fromTo(title, { opacity: 0, y: -20 }, { opacity: 1, y: 0, duration: 0.3 }, t0);
        (d.items || []).slice(0, 4).forEach((it, i) => {
          const r = el("g", {}, g);
          card(r, 110, 450 + i * 125, 860, 100, i % 2 ? S.panel : paper, { rx: cfg.set === "riso" ? 0 : 14 });
          const n = H1(r, 170, 502 + i * 125, String(i + 1), 56, { fill: S.red });
          const t = B(r, 220, 502 + i * 125, it, 40, { anchor: "start", weight: 700 }); fit(t, 720, 40);
          tl.fromTo(r, { opacity: 0, x: -80 }, { opacity: 1, x: 0, duration: 0.35, ease: "power3.out" }, t0 + 0.4 + i * 0.45);
        });
      },
    };
  }

  // ---------- media (P25.2.2): what the story is about, on screen while it is said; inside the graphics box ----------
  // m = {dur, photo: {src, w, h, credit}, shot: {src, w, h, head: [x,y,w,h], credit}, logo: {src, name}}
  // order: the photo (Ken Burns) or the headline screenshot, then the screenshot zooming to its headline with a
  // highlighter; the logo badge pops in on top; the whole layer lifts away to the data graphic at t0 + dur.
  function mediaBuilder(S) {
    const BX = 60, BY = 300, BW = 960, BH = 680;
    let n = 0;
    return function media(g, tl, t0, m, si) {
      const id = `mclip${si}-${n++}`;
      const cp = el("clipPath", { id }, el("defs", {}, g));
      el("rect", { x: BX, y: BY, width: BW, height: BH, rx: 22 }, cp);
      const frame = el("g", {}, g);
      el("rect", { x: BX - 6, y: BY - 6, width: BW + 12, height: BH + 12, rx: 26, fill: S.ink }, frame);
      el("rect", { x: BX, y: BY, width: BW, height: BH, rx: 22, fill: "#ffffff" }, frame);
      const inner = el("g", { "clip-path": `url(#${id})` }, frame);
      const credit = (layer, text) => {
        if (!text) return;
        const bar = el("g", {}, layer);
        el("rect", { x: BX, y: BY + BH - 44, width: BW, height: 44, fill: "rgba(20,18,26,0.72)" }, bar);
        const c = txt(bar, BX + BW - 18, BY + BH - 21, text, { size: 20, font: S.body, fill: "#f3eee4", weight: 600, anchor: "end" });
        fit(c, BW - 36, 20);
      };
      const layers = [];
      const ph = m.photo, sh = m.shot;
      if (ph) {   // photo: cover the box, slow push in
        const L = el("g", {}, inner);
        const im = el("image", { href: ph.src, x: BX, y: BY, width: BW, height: BH, preserveAspectRatio: "xMidYMid slice" }, L);
        gsap.set(im, { svgOrigin: `${BX + BW / 2} ${BY + BH / 2}` });
        credit(L, ph.credit);
        layers.push({ L, run: (a, b) => tl.fromTo(im, { scale: 1.0 }, { scale: 1.12, duration: b - a, ease: "none" }, a) });
      }
      if (sh) {   // screenshot: fit the width, then zoom to the headline and sweep a highlighter over it
        const L = el("g", {}, inner);
        el("rect", { x: BX, y: BY, width: BW, height: BH, fill: "#ffffff" }, L);
        const f = Math.min(BW / sh.w, BH / sh.h), w = sh.w * f, h = sh.h * f, x = BX + (BW - w) / 2, y = BY + (BH - h) / 2;
        const zoom = el("g", {}, L);
        el("image", { href: sh.src, x, y, width: w, height: h, preserveAspectRatio: "xMidYMid meet" }, zoom);
        let hl = null, cx = BX + BW / 2, cy = BY + BH / 2, k = 1.0;
        if (sh.head) {
          const [hx, hy, hw, hh] = sh.head.map((v) => v * f);
          cx = x + hx + hw / 2; cy = y + hy + hh / 2;
          k = clamp(Math.min((BW - 40) / Math.max(hw, 1), 130 / Math.max(hh, 1)), 1, 2.6);   // as big as fits the box, never cut
          hl = el("rect", { x: x + hx - 8, y: y + hy - 4, width: hw + 16, height: hh + 8, fill: "#ffe14d", opacity: 0.5,
                            style: "mix-blend-mode:multiply" }, zoom);   // over the headline, multiplied so the text stays black
          gsap.set(hl, { svgOrigin: `${x + hx - 8} ${cy}` });
        }
        gsap.set(zoom, { svgOrigin: `${cx} ${cy}` });
        credit(L, sh.credit);
        layers.push({ L, run: (a, b) => {
          tl.fromTo(zoom, { scale: 1, x: 0, y: 0 }, { scale: k, x: BX + BW / 2 - cx, y: BY + BH / 2 - cy, duration: Math.min(1.2, (b - a) * 0.6), ease: "power2.inOut" }, a + 0.1);
          if (hl) tl.fromTo(hl, { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power2.out" }, a + 0.5);
        } });
      }
      // timing: one layer = the whole window; two = split it; each layer fades in over the one before
      const span = m.dur - 0.25;
      layers.forEach(({ L, run }, i) => {
        const a = t0 + (span * i) / layers.length, b = t0 + (span * (i + 1)) / layers.length;
        if (i) tl.fromTo(L, { opacity: 0 }, { opacity: 1, duration: 0.25 }, a); else gsap.set(L, { opacity: 1 });
        run(a, b);
      });
      if (m.logo) {   // logo badge, top left of the box, pops in after the first beat
        const lg = el("g", {}, frame);
        el("rect", { x: BX + 24, y: BY + 24, width: 250, height: 150, rx: 18, fill: "#ffffff", stroke: S.ink, "stroke-width": 5 }, lg);
        el("image", { href: m.logo.src, x: BX + 44, y: BY + 44, width: 210, height: 110, preserveAspectRatio: "xMidYMid meet" }, lg);
        gsap.set(lg, { svgOrigin: `${BX + 149} ${BY + 99}` });
        tl.fromTo(lg, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.4, ease: "back.out(2.2)" }, t0 + 0.35);
      }
      gsap.set(frame, { svgOrigin: `${BX + BW / 2} ${BY + BH / 2}` });
      tl.fromTo(frame, { scale: 0.9, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.35, ease: "power3.out" }, t0);
      tl.to(frame, { opacity: 0, y: -40, duration: 0.3, ease: "power2.in" }, t0 + m.dur - 0.25);
    };
  }

  // ---------- analogy gags (P25.2.4): four fixed recipes, picked by the writer from research/analogies.json ----------
  // a = {treatment, at, dur, image|left|right: {src, credit}, left_label, right_label, joiner, big, label, caption, word}
  function gagBuilder(S) {
    const BX = 60, BY = 300, BW = 960, BH = 680;
    let n = 0;
    const pic = (g, p, x, y, w, h, r = 20) => {
      const id = `gclip${n++}`;
      el("rect", { x, y, width: w, height: h, rx: r }, el("clipPath", { id }, el("defs", {}, g)));
      el("rect", { x: x - 5, y: y - 5, width: w + 10, height: h + 10, rx: r + 4, fill: S.ink }, g);
      return el("image", { href: p.src, x, y, width: w, height: h, preserveAspectRatio: "xMidYMid slice", "clip-path": `url(#${id})` }, g);
    };
    const label = (g, x, y, s, size, fill = S.text, maxW = 420) => { const t = txt(g, x, y, String(s || "").toUpperCase(), { size, font: S.body, fill, weight: 800, spacing: 1 }); fit(t, maxW, size); return t; };
    const pop = (tl, node, t, ox, oy, d = 0.35) => { gsap.set(node, { svgOrigin: `${ox} ${oy}` }); tl.fromTo(node, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: d, ease: "back.out(2)" }, t); };
    return function gag(g, tl, t0, a) {
      const back = el("rect", { x: BX, y: BY, width: BW, height: BH, rx: 22, fill: S.bg, stroke: S.ink, "stroke-width": a.treatment === "stamp" ? 0 : 5,
                                opacity: a.treatment === "stamp" ? 0 : 1 }, g);
      if (a.treatment !== "stamp") tl.fromTo(back, { opacity: 0 }, { opacity: 1, duration: 0.2 }, t0);
      if (a.treatment === "compare") {
        const L = el("g", {}, g), R = el("g", {}, g);
        pic(L, a.left, 110, 360, 360, 360); label(L, 290, 790, a.left_label, 40);
        pic(R, a.right, 610, 360, 360, 360); label(R, 790, 790, a.right_label, 40);
        const j = txt(g, 540, 560, a.joiner || "=", { size: 120, font: S.head, fill: S.red, weight: 900 });
        pop(tl, L, t0 + 0.05, 290, 540); pop(tl, j, t0 + 0.45, 540, 560); pop(tl, R, t0 + 0.7, 790, 540);
      } else if (a.treatment === "scale") {
        const big = txt(g, 540, 400, a.big || "", { size: 130, font: S.head, fill: S.red, weight: 900 }); fit(big, 900, 130);
        pop(tl, big, t0 + 0.05, 540, 400);
        const cells = el("g", {}, g);
        for (let i = 0; i < 12; i++) { const c = el("g", {}, cells); pic(c, a.image, 132 + (i % 6) * 140, 500 + Math.floor(i / 6) * 150, 116, 116, 14); pop(tl, c, t0 + 0.3 + i * 0.07, 190 + (i % 6) * 140, 558 + Math.floor(i / 6) * 150, 0.25); }
        const l = label(g, 540, 850, a.label, 42, S.text, 900); tl.fromTo(l, { opacity: 0 }, { opacity: 1, duration: 0.3 }, t0 + 1.2);
      } else if (a.treatment === "photo") {
        const im = pic(g, a.image, BX + 20, BY + 20, BW - 40, BH - 40, 18);
        gsap.set(im, { svgOrigin: `540 640` });
        tl.fromTo(im, { scale: 1.15, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.5, ease: "power3.out" }, t0);
        const bar = el("g", {}, g);
        el("rect", { x: BX + 20, y: BY + BH - 150, width: BW - 40, height: 110, fill: S.red }, bar);
        const c = txt(bar, 540, BY + BH - 95, String(a.caption || "").toUpperCase(), { size: 56, font: S.head, fill: S.textOnRed, weight: 900 }); fit(c, BW - 100, 56);
        tl.fromTo(bar, { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.3, ease: "power3.out" }, t0 + 0.4);
      } else {   // stamp: slams over whatever is on screen
        const st = el("g", { transform: "rotate(-12 540 640)" }, g);
        const w = Math.max(360, 64 * String(a.word).length + 80);
        el("rect", { x: 540 - w / 2, y: 560, width: w, height: 160, rx: 14, fill: "none", stroke: S.red, "stroke-width": 14 }, st);
        const t = txt(st, 540, 642, String(a.word || "").toUpperCase(), { size: 110, font: S.head, fill: S.red, weight: 900, spacing: 4 }); fit(t, w - 60, 110);
        gsap.set(st, { svgOrigin: "540 640" });
        tl.fromTo(st, { scale: 3, opacity: 0 }, { scale: 1, opacity: 0.92, duration: 0.18, ease: "power4.in" }, t0);
      }
      tl.to(g, { opacity: 0, duration: 0.25 }, t0 + a.dur - 0.25);
    };
  }

  window.SHOW = { build(cfg) {
    const S = SETS[cfg.set];
    const q = (f) => f.replace(/"/g, "'");   // font names inside an innerHTML style="..." attribute
    const esc = (v) => String(v ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
    const DUR = cfg.dur;
    const tl = gsap.timeline({ paused: true });
    window.__timelines["main"] = tl;
    const root = document.getElementById("show");
    root.style.cssText = `position:absolute;inset:0;overflow:hidden;background:${S.bg}`;

    // layer 1: graphics (full frame, content inside y 300-980)
    const vis = div(root, `position:absolute;inset:0;background:${S.bg}`);
    const visSvg = svgBox(vis);
    defs(visSvg, S);
    if (cfg.set === "riso") for (let y = 0; y < H; y += 48) el("rect", { x: 0, y, width: W, height: 2, fill: S.panel }, visSvg);
    if (cfg.set === "paper") el("rect", { x: 0, y: 0, width: W, height: H, fill: "#efe7d8" }, visSvg);
    if (cfg.set === "night") { for (let x = 0; x < W; x += 60) el("rect", { x, y: 0, width: 1, height: H, fill: "#151b36" }, visSvg); for (let y = 0; y < H; y += 60) el("rect", { x: 0, y, width: W, height: 1, fill: "#151b36" }, visSvg); }
    const G = graphics(S, cfg);
    const media = mediaBuilder(S);
    const gag = gagBuilder(S);
    const groups = cfg.segments.map((seg, si) => {
      const hasG = seg.g && G[seg.g.type];
      if (!hasG && !seg.media && !seg.gag) return null;
      const g = el("g", {}, visSvg);
      const m = seg.media ? seg.media.dur : 0;   // real visuals first (P25.2.2), then the data graphic
      const gr = hasG ? el("g", { filter: look(S) }, g) : null;
      if (hasG) G[seg.g.type](gr, tl, seg.start + 0.15 + m, seg.g);
      if (seg.media) media(el("g", {}, g), tl, seg.start + 0.15, seg.media, si);
      if (seg.gag) {   // the graphic steps back while the gag is on (a stamp over live text read as a clash)
        const a0 = seg.start + seg.gag.at, gg = el("g", {}, g);
        gsap.set(gg, { opacity: 0 }); tl.set(gg, { opacity: 1 }, a0); gag(gg, tl, a0, seg.gag);
        if (gr) { tl.to(gr, { opacity: seg.gag.treatment === "stamp" ? 0.12 : 0, duration: 0.15 }, a0); tl.to(gr, { opacity: 1, duration: 0.2 }, a0 + seg.gag.dur - 0.2); }
      }
      return g;
    });

    // layer 2: the studio, seen through a window (clip + seam mask) by a camera (transform)
    const studio = div(root, "position:absolute;inset:0;");
    const cam = div(studio, "position:absolute;left:0;top:0;width:1080px;height:1920px;transform-origin:0 0");
    const setSvg = svgBox(cam);
    drawSetBack(setSvg, S, cfg);
    const wall = drawWall(setSvg, S, cfg);
    const rig = RIGS[cfg.look](cam);
    const deskSvg = svgBox(cam); defs(deskSvg, S);
    drawDesk(deskSvg, S, cfg);
    const sweeps = Array.from(setSvg.querySelectorAll(".sweep"));

    const pipFrame = div(root, `position:absolute;left:${PIP.x - 8}px;top:${PIP.y - 8}px;width:${PIP.s + 16}px;height:${PIP.s + 16}px;border:8px solid ${S.red};border-radius:36px;box-sizing:border-box;opacity:0`);
    const live = div(pipFrame, `position:absolute;left:16px;top:16px;padding:6px 14px;border-radius:20px;background:${S.ink};color:${S.bg};font:800 22px/1 ${S.body};letter-spacing:2px`);
    live.innerHTML = `<span style="display:inline-block;width:12px;height:12px;border-radius:6px;background:${S.red};margin-right:8px;vertical-align:1px"></span>HABIT`;

    // package: show bug (top left), topic countdown (top right), topic strip, source chip, breaking bar, ticker, sting, end card
    const pkg = div(root, "position:absolute;inset:0;pointer-events:none");
    const bug = div(pkg, `position:absolute;left:48px;top:64px;display:flex;gap:12px;align-items:center;font:800 28px/1 ${S.body};letter-spacing:3px`);
    bug.innerHTML = `<span style="background:${S.red};color:${S.textOnRed};padding:12px 18px">EP ${esc(cfg.episode)}</span><span style="color:${S.text};background:${S.bg};padding:12px 14px;border:3px solid ${S.text}">THE DAILY HABIT</span>`;
    // countdown to the next topic: a ring that empties over the topic, the seconds left, and n/N
    const cd = div(pkg, `position:absolute;right:48px;top:44px;width:132px;height:132px;opacity:0`);
    const cdSvg = svgBox(cd, 132, 132, "position:absolute;left:0;top:0");
    el("circle", { cx: 66, cy: 66, r: 58, fill: S.bg, stroke: S.ink, "stroke-width": 5 }, cdSvg);
    const ring = el("circle", { cx: 66, cy: 66, r: 50, fill: "none", stroke: S.red, "stroke-width": 12, "stroke-dasharray": `${2 * Math.PI * 50}`, transform: "rotate(-90 66 66)" }, cdSvg);
    const cdNum = txt(cdSvg, 66, 62, "", { size: 52, font: S.head, fill: S.text, weight: 800 });
    const cdOf = txt(cdSvg, 66, 100, "", { size: 18, font: S.body, fill: S.text, weight: 800, spacing: 1 });
    const strip = div(pkg, `position:absolute;left:48px;top:176px;width:984px;opacity:0;display:flex;align-items:stretch;font:800 40px/1.15 ${q(S.head)}`);
    const chip = div(pkg, `position:absolute;left:48px;top:250px;background:${S.bg};color:${S.text};border:3px solid ${S.text};font:700 24px/1 ${S.body};padding:10px 16px;opacity:0`);
    const ticker = div(pkg, `position:absolute;left:0;top:1432px;width:1080px;height:64px;background:${S.ink};overflow:hidden;opacity:0`);
    const tickTag = div(ticker, `position:absolute;left:0;top:0;height:64px;z-index:2;background:${S.red};color:${S.textOnRed};font:800 28px/64px ${S.body};padding:0 22px;letter-spacing:3px`);
    tickTag.textContent = "TODAY";
    const tickText = div(ticker, `position:absolute;left:0;top:0;height:64px;white-space:nowrap;color:${S.bg};font:700 30px/64px ${S.body};letter-spacing:2px`);
    tickText.textContent = ((cfg.ticker || []).join("   ◆   ") + "   ◆   ").repeat(3);
    const breaking = div(pkg, `position:absolute;left:0;top:1160px;width:1080px;opacity:0`);
    breaking.innerHTML = `<div style="background:${S.red};color:${S.textOnRed};font:900 70px/1 ${q(S.head)};padding:22px 48px;letter-spacing:4px">BREAKING</div>
      <div style="background:${S.ink};color:${S.bg};font:700 36px/1.2 ${q(S.body)};padding:16px 48px">${esc(cfg.breakingText)}</div>`;

    const capBox = div(root, `position:absolute;left:0;top:0;width:1080px;height:0`);
    const cap = div(capBox, `position:absolute;left:60px;width:960px;text-align:center;font:800 62px/1.1 ${S.body === '"FF Mono", monospace' ? '"FF Display", sans-serif' : S.body};color:${S.text}`);
    const capStyle = (shot) => {
      if (shot === "pip") return { left: 400, width: 640, top: 1240, align: "left" };
      if (shot === "split") return { left: 60, width: 960, top: 990, align: "center" };
      if (shot === "wide") return { left: 60, width: 960, top: 1380, align: "center" };   // under the breaking bar
      return { left: 60, width: 960, top: 1210, align: "center" };
    };

    const sting = div(root, `position:absolute;inset:0;opacity:0;background:${S.red}`);
    const stingSvg = svgBox(sting);
    if (cfg.set === "riso") { FF.pixelText(stingSvg, 540, 820, "THE DAILY", 22, "p"); FF.pixelText(stingSvg, 540, 1000, "HABIT", 34, "p"); }
    else { txt(stingSvg, 540, 820, "THE DAILY", { size: 150, font: S.head, fill: S.textOnRed, weight: 900 }); txt(stingSvg, 540, 1000, "HABIT", { size: 230, font: S.head, fill: S.textOnRed, weight: 900 }); }
    txt(stingSvg, 540, 1170, `${cfg.date} · EP ${cfg.episode} · ${cfg.segments.filter((x) => x.topic).length} STORIES`, { size: 44, font: S.body, fill: S.textOnRed, weight: 700, spacing: 6 });
    const stingBar = el("rect", { x: 0, y: 0, width: 24, height: H, fill: S.ink }, stingSvg);

    const end = div(root, `position:absolute;inset:0;opacity:0;background:${S.bg}`);
    const endSvg = svgBox(end);
    FF.pixel(endSvg, FF.HABIT_PX, 540 - 6 * 22, 520, 22);
    txt(endSvg, 540, 1060, "Make learning", { size: 110, font: S.head, fill: S.text, weight: 800 });
    txt(endSvg, 540, 1190, "a Habit.", { size: 130, font: S.head, fill: S.red, weight: 800 });
    txt(endSvg, 540, 1330, "A THIRDSPACE PRODUCTION", { size: 34, font: S.body, fill: S.text, weight: 700, spacing: 6 });

    const grain = div(root, `position:absolute;inset:0;pointer-events:none;opacity:${S.grain}`);
    const gs = svgBox(grain); const gf = el("filter", { id: "grain" }, el("defs", {}, gs));
    el("feTurbulence", { type: "fractalNoise", baseFrequency: 0.9, numOctaves: 2, seed: 11 }, gf);
    el("rect", { x: 0, y: 0, width: W, height: H, filter: "url(#grain)" }, gs);

    // ---------- timeline of framings: [time, shot] keyframes ----------
    const keys = [];
    cfg.segments.forEach((seg) => (seg.shots || [[0, seg.shot]]).forEach(([off, shot]) => keys.push([seg.start + off, shot])));
    keys.sort((a, b) => a[0] - b[0]);
    const TR = 0.5;
    const frameAt = (t) => {
      let i = 0;
      while (i + 1 < keys.length && keys[i + 1][0] <= t) i++;
      const cur = framing(keys[i][1]);
      if (i === 0) return { f: cur, shot: keys[i][1], since: t - keys[0][0] };
      const k = clamp((t - keys[i][0]) / TR);
      return { f: k >= 1 ? cur : mixF(framing(keys[i - 1][1]), cur, ease(k)), shot: keys[i][1], since: t - keys[i][0] };
    };
    const segAt = (t) => { const i = cfg.segments.findIndex((s) => t >= s.start && t < s.start + s.dur); return i < 0 ? cfg.segments.length - 1 : i; };
    const env = cfg.env || [], fps = cfg.envFps || 30;
    const mouthAt = (t) => { const i = Math.floor(t * fps); const v = env[i] ?? 0; return clamp((v - 0.06) / 0.5); };
    const blinkAt = (t) => { const p = (t + 0.7) % 3.7; return p < 0.08 ? p / 0.08 : p < 0.16 ? 1 - (p - 0.08) / 0.08 : 0; };
    const emoAt = (t, si) => {
      const cur = EMO[cfg.segments[si]?.emotion] || EMO.neutral;
      const prev = EMO[cfg.segments[si - 1]?.emotion] || EMO.neutral;
      return si > 0 ? mixEmo(prev, cur, ease(clamp((t - cfg.segments[si].start) / 0.35))) : cur;
    };
    const words = cfg.words || [];
    let lastStrip = -1;

    const frame = (t) => {
      const { f, shot, since } = frameAt(t);
      cam.style.transform = `translate(${f.tx}px, ${f.ty}px) scale(${f.s})`;
      studio.style.clipPath = `inset(${f.ct}px ${f.cr}px ${f.cb}px ${f.cl}px round ${f.rad}px)`;
      const m = `linear-gradient(to bottom, transparent ${f.ma}px, #000 ${f.mb}px)`;
      studio.style.webkitMaskImage = m; studio.style.maskImage = m;
      studio.style.opacity = f.op;
      vis.style.visibility = shot === "wide" && Math.abs(f.s - 1) < 1e-3 && f.ma < 0 ? "hidden" : "";
      pipFrame.style.opacity = shot === "pip" ? clamp((since - 0.3) / 0.3) : 0;
      const si = segAt(t);
      const seg = cfg.segments[si];
      groups.forEach((g, i) => { if (g) g.style.display = i === si || (i === si - 1 && t - seg.start < 0.15) ? "" : "none"; });
      wall.set(seg.wall || "TODAY", seg.wallSub || "THE DAILY HABIT");
      const lookY = shot === "split" ? 0.8 : 0, lookX = shot === "pip" ? 0.7 : Math.sin(t * 0.7) * 0.15;
      const talking = mouthAt(t);
      rig.pose({ mouth: talking, blink: blinkAt(t), lookX, lookY, bob: Math.sin(t * 2.1) * 6 + talking * 4, brow: talking > 0.6 ? 0.6 : 0.1,
        tilt: Math.sin(t * 0.9) * 2 + (seg.emotion === "doubtful" ? 4 : seg.emotion === "laughing" ? Math.sin(t * 9) * 2 : 0), emo: emoAt(t, si) });
      sweeps.forEach((s, i) => { const p = ((t * 0.18 + i / 3) % 1); s.setAttribute("x", -300 + p * 1700); s.setAttribute("opacity", 0.9); });
      const inSting = cfg.stingAt != null && t > cfg.stingAt && t < cfg.stingAt + 1.6;
      const atEnd = cfg.endAt != null && t > cfg.endAt;
      bug.style.opacity = inSting || atEnd ? 0 : 1;
      // topic countdown + strip
      if (seg.topic && !atEnd) {
        const left = Math.max(seg.start + seg.dur - t, 0);
        const k = clamp((t - seg.start) / 0.3);
        cd.style.opacity = k; cd.style.transform = `scale(${0.7 + 0.3 * ease(k)})`;
        cdNum.textContent = String(Math.ceil(left - 1e-6));
        ring.setAttribute("stroke-dashoffset", `${2 * Math.PI * 50 * (1 - left / seg.dur)}`);
        ring.setAttribute("stroke", left < 3 ? S.red : S.blue);
        cdOf.textContent = `${seg.topic}/${cfg.topics}`;
        if (lastStrip !== si) {
          strip.innerHTML = `<span style="background:${S.red};color:${S.textOnRed};padding:12px 18px 8px;font-family:${q(S.body)};font-size:30px;letter-spacing:2px">${String(seg.topic).padStart(2, "0")} · ${esc(seg.lane).toUpperCase()}</span>` +
            `<span style="background:${S.ink};color:${S.bg};padding:12px 20px 8px;white-space:nowrap;font-size:${String(seg.headline).length > 32 ? 30 : String(seg.headline).length > 26 ? 35 : 40}px">${esc(seg.headline)}</span>`;
          lastStrip = si;
        }
        const sk = clamp((t - seg.start - 0.1) / 0.3);
        strip.style.opacity = shot === "wide" ? 0 : sk; strip.style.transform = `translateX(${(1 - ease(sk)) * -60}px)`;
        chip.textContent = `SOURCE · ${seg.source || ""}`;
        chip.style.opacity = seg.source && shot !== "wide" ? clamp((t - seg.start - 0.6) / 0.3) : 0;
      } else { cd.style.opacity = 0; strip.style.opacity = 0; chip.style.opacity = 0; }
      const tk = cfg.tickerAt != null ? clamp((t - cfg.tickerAt) / 0.4) : 0;
      ticker.style.opacity = atEnd ? 0 : tk;
      tickText.style.transform = `translateX(${1080 - ((t - (cfg.tickerAt ?? 0)) * 170) % 2600}px)`;
      const bk = cfg.breakingAt != null ? clamp((t - cfg.breakingAt) / 0.25) * clamp((cfg.breakingAt + (cfg.breakingDur ?? 4) - t) / 0.25) : 0;
      breaking.style.opacity = bk; breaking.style.transform = `translateX(${(1 - bk) * -120}px)`;
      if (cfg.stingAt != null) {
        const p = t - cfg.stingAt;
        sting.style.opacity = p >= 0 && p < 1.55 ? 1 : 0;
        sting.style.clipPath = `inset(0 ${p < 0.25 ? (1 - ease(clamp(p / 0.25))) * 100 : 0}% 0 ${p > 1.1 ? ease(clamp((p - 1.1) / 0.42)) * 100 : 0}%)`;
        stingBar.setAttribute("transform", `translate(${p > 1.1 ? ease(clamp((p - 1.1) / 0.42)) * W - 24 : -W} 0)`);
      }
      if (cfg.endAt != null) end.style.opacity = clamp((t - cfg.endAt) / 0.3);
      const w = words.findIndex((x) => t >= x.s && t < x.e + 0.25);
      if (w < 0 || atEnd || inSting) cap.textContent = "";
      else {
        const grp = words.filter((x) => x.g === words[w].g);
        cap.innerHTML = `<span style="background:${S.bg};padding:8px 20px;border-radius:${cfg.set === "riso" ? 0 : 14}px;box-shadow:0 0 0 3px ${S.text}">` +
          grp.map((x) => `<span style="color:${x === words[w] ? S.red : S.text}">${esc(x.w)}</span>`).join(" ") + "</span>";
        const c = capStyle(shot);
        Object.assign(cap.style, { left: c.left + "px", width: c.width + "px", top: c.top + "px", textAlign: c.align, display: "block" });
      }
    };
    const clock = { t: 0 };
    tl.fromTo(clock, { t: 0 }, { t: DUR, duration: DUR, ease: "none", onUpdate: () => frame(clock.t) }, 0);
    frame(0);
  } };
})();
