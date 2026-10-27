/* Studio-show spike (P24.1.2): The Daily Habit as a show. One composition draws a set (riso | paper | night),
   a Habit look (pixel | puppet | low3d) and the four framings (wide | split | pip | full), plus the show package
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

  // ---------- Habit, three looks: one pose API (mouth 0-1, blink 0-1, lookX/lookY -1..1, bob px, brow 0-1) ----------
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
    el("path", { d: "M 120 196 Q 140 186 160 194", fill: "none", stroke: INK, "stroke-width": 7, "stroke-linecap": "round" }, brows);
    el("path", { d: "M 200 194 Q 220 186 240 196", fill: "none", stroke: INK, "stroke-width": 7, "stroke-linecap": "round" }, brows);
    const eyes = el("g", {}, head);
    const eL = el("ellipse", { cx: 140, cy: 230, rx: 12, ry: 16, fill: INK }, eyes);
    const eR = el("ellipse", { cx: 220, cy: 230, rx: 12, ry: 16, fill: INK }, eyes);
    const gL = el("circle", { cx: 144, cy: 224, r: 4, fill: "#fff" }, eyes), gR = el("circle", { cx: 224, cy: 224, r: 4, fill: "#fff" }, eyes);
    const mouthO = el("ellipse", { cx: 180, cy: 300, rx: 24, ry: 4, fill: "#5B1D1D", ...st, "stroke-width": 4 }, head);
    const tongue = el("ellipse", { cx: 180, cy: 312, rx: 14, ry: 6, fill: "#FF6B5B" }, head);
    const smile = el("path", { d: "M 152 296 Q 180 318 208 296", fill: "none", stroke: INK, "stroke-width": 6, "stroke-linecap": "round" }, head);
    misreg.innerHTML = `<ellipse cx="180" cy="228" rx="108" ry="122" fill="#1F3A93"/><path d="M 40 560 Q 40 400 180 392 Q 320 400 320 560 Z" fill="#1F3A93"/>`;
    return { el: box, pose(p) {
      const ry = 16 * (1 - 0.9 * p.blink);
      eL.setAttribute("ry", ry); eR.setAttribute("ry", ry);
      eyes.setAttribute("transform", `translate(${p.lookX * 9} ${p.lookY * -7})`);
      brows.setAttribute("transform", `translate(0 ${-p.brow * 12})`);
      const m = p.mouth;
      mouthO.setAttribute("ry", 3 + 22 * m); mouthO.setAttribute("rx", 22 + 6 * (1 - m)); mouthO.setAttribute("cy", 300 + 8 * m);
      mouthO.setAttribute("opacity", m > 0.08 ? 1 : 0); tongue.setAttribute("opacity", m > 0.45 ? 1 : 0); tongue.setAttribute("cy", 300 + 20 * m);
      smile.setAttribute("opacity", m > 0.08 ? 0 : 1);
      head.setAttribute("transform", `rotate(${p.lookX * 4 + p.tilt} 180 330) translate(0 ${p.bob * 0.6})`);
      box.style.transform = `translateY(${p.bob * 0.4}px)`;
    } };
  }

  function rigLow3d(parent) {
    const CW = 480, CH = 640;
    const canvas = document.createElement("canvas");
    canvas.width = CW; canvas.height = CH;
    canvas.style.cssText = `position:absolute;left:${FACE.x - 240}px;top:${FACE.y - 250}px;width:${CW}px;height:${CH}px`;
    parent.appendChild(canvas);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1); renderer.setSize(CW, CH, false);
    const scene = new THREE.Scene();
    const cam = new THREE.OrthographicCamera(-2.4, 2.4, 2.5, -3.9, 0.1, 50);   // 1 unit = 100 px; head centre at canvas (240, 250)
    cam.position.set(0, 0, 10);
    scene.add(new THREE.AmbientLight(0xffffff, 1.4));
    scene.add(new THREE.HemisphereLight(0xfff4e6, 0x8a7a90, 1.6));
    const key = new THREE.DirectionalLight(0xffffff, 2.4); key.position.set(-3, 4, 6); scene.add(key);
    const mat = (c) => new THREE.MeshStandardMaterial({ color: c, flatShading: true, roughness: 0.75, metalness: 0.0 });
    const rig = new THREE.Group(); scene.add(rig);
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 1.35, 2.2, 7), mat(SHIRT)); body.position.set(0, -2.6, -0.3); rig.add(body);
    const collar = new THREE.Mesh(new THREE.ConeGeometry(0.42, 0.5, 3), mat(CREAM)); collar.position.set(0, -1.55, 0.45); collar.rotation.x = Math.PI; rig.add(collar);
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.36, 0.6, 6), mat(SKIN)); neck.position.set(0, -1.25, -0.1); rig.add(neck);
    const head = new THREE.Group(); rig.add(head);
    const skull = new THREE.Mesh(new THREE.IcosahedronGeometry(1.12, 1), mat(SKIN)); skull.scale.set(0.95, 1.08, 0.95); head.add(skull);
    const hair = new THREE.Mesh(new THREE.SphereGeometry(1.17, 9, 6, 0, Math.PI * 2, 0, Math.PI * 0.42), mat(HAIR)); hair.position.y = 0.1; head.add(hair);
    const band = new THREE.Mesh(new THREE.TorusGeometry(1.25, 0.1, 5, 14, Math.PI), mat(PHONES)); band.rotation.z = 0; head.add(band);
    for (const sx of [-1, 1]) {
      const cup = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.3, 8), mat(HAIR)); cup.rotation.z = Math.PI / 2; cup.position.set(sx * 1.15, -0.05, 0); head.add(cup);
    }
    for (const sx of [-1, 1]) { const w = new THREE.Mesh(new THREE.SphereGeometry(0.22, 8, 6), mat("#ffffff")); w.scale.z = 0.4; w.position.set(sx * 0.4, 0.05, 0.98); head.add(w); }
    const eyes = [-1, 1].map((sx) => { const e = new THREE.Mesh(new THREE.SphereGeometry(0.13, 6, 5), mat(INK)); e.position.set(sx * 0.4, 0.05, 1.07); head.add(e); return e; });
    for (const sx of [-1, 1]) { const c = new THREE.Mesh(new THREE.SphereGeometry(0.14, 6, 5), mat("#FF8A7A")); c.scale.z = 0.3; c.position.set(sx * 0.62, -0.35, 0.92); head.add(c); }
    const mouth = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.1, 0.12), mat("#5B1D1D")); mouth.position.set(0, -0.6, 0.95); head.add(mouth);
    return { el: canvas, pose(p) {
      head.rotation.y = p.lookX * 0.35 + p.tilt * 0.02; head.rotation.x = -p.lookY * 0.18 + 0.04; head.rotation.z = p.tilt * 0.03;
      head.position.y = p.bob * -0.006;
      eyes.forEach((e) => (e.scale.y = 1 - 0.85 * p.blink));
      mouth.scale.set(1 - 0.25 * p.mouth, 1 + 4.2 * p.mouth, 1); mouth.position.y = -0.6 - 0.16 * p.mouth;
      rig.rotation.y = p.lookX * 0.08;
      renderer.render(scene, cam);
    } };
  }
  const RIGS = { pixel: rigPixel, puppet: rigPuppet, low3d: rigLow3d };

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

  // ---------- graphics: one builder per visual; each returns its group; entrances on the timeline at t0 ----------
  function graphics(S, cfg) {
    const H1 = (g, x, y, s, size, o = {}) => txt(g, x, y, s, { size, font: S.head, fill: o.fill ?? S.text, weight: o.weight ?? 800, anchor: o.anchor });
    const B = (g, x, y, s, size, o = {}) => txt(g, x, y, s, { size, font: S.body, fill: o.fill ?? S.text, weight: o.weight ?? 600, anchor: o.anchor, spacing: o.spacing });
    const card = (g, x, y, w, h, fill, o = {}) => el("rect", { x, y, width: w, height: h, rx: o.rx ?? (cfg.set === "riso" ? 0 : 18), fill, stroke: o.stroke ?? S.ink, "stroke-width": o.sw ?? 5 }, g);
    const piv = (n, x, y) => gsap.set(n, { svgOrigin: `${x} ${y}` });
    const truck = (g, x, y, sc, fill) => {
      const t = el("g", {}, el("g", { transform: `translate(${x} ${y}) scale(${sc})` }, g));
      card(t, -90, -50, 120, 80, fill, { rx: 6 }); card(t, 30, -30, 60, 60, S.panel, { rx: 6 });
      el("circle", { cx: -55, cy: 34, r: 16, fill: S.ink }, t); el("circle", { cx: 55, cy: 34, r: 16, fill: S.ink }, t);
      return t;   // animate this inner group: the outer one holds the placement
    };
    return {
      headline(g, tl, t0) {
        const a = H1(g, 540, 560, "AI FREIGHT,", 150), b = H1(g, 540, 730, "STOLEN.", 190, { fill: S.red });
        fit(a, 960, 150); fit(b, 960, 190);
        const bar = el("rect", { x: 140, y: 820, width: 800, height: 16, fill: S.blue }, g); piv(bar, 140, 828);
        const k = B(g, 540, 930, "$100 MILLION · MOSTLY WITH PAPERWORK", 40, { spacing: 2 }); fit(k, 960, 40);
        [a, b].forEach((n, i) => { piv(n, 540, 600 + i * 170); tl.fromTo(n, { scale: 2.4, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.24, ease: "power4.in" }, t0 + 0.05 + i * 0.2); });
        tl.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: 0.4, ease: "power3.out" }, t0 + 0.55);
        tl.fromTo(k, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.35 }, t0 + 1.4);
      },
      rack(g, tl, t0) {
        const r = el("g", {}, g);
        card(r, 180, 260, 300, 640, S.panel2);
        for (let i = 0; i < 9; i++) { card(r, 210, 290 + i * 66, 240, 50, S.dark, { sw: 3, rx: 4 }); el("circle", { cx: 420, cy: 315 + i * 66, r: 8, fill: i % 3 ? S.blue : S.red }, r); }
        const n = { v: 0 };
        const num = H1(g, 760, 520, "$0", 120, { fill: S.red });
        B(g, 760, 610, "PER AI SERVER RACK", 34);
        tl.fromTo(r, { opacity: 0, y: 60 }, { opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }, t0);
        tl.fromTo(n, { v: 0 }, { v: 3, duration: 1.2, ease: "power2.out", onUpdate: () => (num.textContent = `$${n.v.toFixed(1)}M`) }, t0 + 0.4);
        const tr = truck(g, 760, 760, 1.6, S.blue);
        tl.fromTo(tr, { x: 400, opacity: 0 }, { x: 0, opacity: 1, duration: 0.7, ease: "power3.out" }, t0 + 2.6);
        const v = B(g, 760, 880, "A VAULT ON WHEELS", 40, { fill: S.red, weight: 800 });
        tl.fromTo(v, { opacity: 0 }, { opacity: 1, duration: 0.3 }, t0 + 3.2);
      },
      map(g, tl, t0) {
        card(g, 70, 170, 940, 860, cfg.set === "night" ? "#10142a" : "#fbf8f1");
        const road = el("path", { d: "M 120 940 C 300 820 260 560 480 520 S 820 380 960 250", fill: "none", stroke: S.ink, "stroke-width": 26, "stroke-linecap": "round" }, g);
        const lane = el("path", { d: "M 120 940 C 300 820 260 560 480 520 S 820 380 960 250", fill: "none", stroke: S.bg, "stroke-width": 4, "stroke-dasharray": "20 18" }, g);
        tl.fromTo([road, lane], { drawSVG: "0%" }, { drawSVG: "100%", duration: 1.0, ease: "power2.inOut" }, t0);
        const real = el("circle", { cx: 0, cy: 0, r: 24, fill: S.blue, stroke: S.ink, "stroke-width": 5 }, g);
        tl.fromTo(real, { motionPath: { path: road, align: road, alignOrigin: [0.5, 0.5], start: 0, end: 0 } },
          { motionPath: { path: road, align: road, alignOrigin: [0.5, 0.5], start: 0, end: 0.9 }, duration: 5.5, ease: "none" }, t0 + 0.6);
        const ghost = el("g", {}, g);
        el("path", { d: "M 780 520 c -50 0 -70 40 -70 70 c 0 50 70 110 70 110 c 0 0 70 -60 70 -110 c 0 -30 -20 -70 -70 -70 z", fill: S.red, stroke: S.ink, "stroke-width": 5 }, ghost);
        el("circle", { cx: 780, cy: 590, r: 22, fill: S.bg }, ghost);
        B(ghost, 780, 750, "TRACKER SAYS: HERE", 30, { fill: S.red, weight: 800 });
        piv(ghost, 780, 700);
        tl.fromTo(ghost, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.4, ease: "back.out(2)" }, t0 + 1.8);
        const dash = el("g", {}, g); card(dash, 110, 210, 400, 110, S.dark, { rx: 12 });
        B(dash, 310, 265, "GPS: ON ROUTE ✓", 34, { fill: "#7CFFB2", weight: 800 });
        tl.fromTo(dash, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.35 }, t0 + 3.2);
      },
      stat(g, tl, t0) {
        const n = { v: 0 };
        const num = H1(g, 540, 560, "0%", 330, { fill: S.red });
        tl.fromTo(n, { v: 0 }, { v: 92, duration: 1.3, ease: "power3.out", onUpdate: () => (num.textContent = `${Math.round(n.v)}%`) }, t0 + 0.1);
        const l1 = B(g, 540, 760, "OF HIGH-VALUE TECH THEFTS", 44, { weight: 800 });
        const l2 = H1(g, 540, 850, "used deception, not force", 62, { fill: S.blue });
        fit(l2, 960, 62);
        tl.fromTo([l1, l2], { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.35, stagger: 0.25 }, t0 + 0.9);
        const dots = el("g", {}, g);
        for (let i = 0; i < 100; i++) el("rect", { x: 165 + (i % 25) * 30, y: 950 + Math.floor(i / 25) * 30, width: 22, height: 22, rx: 4, fill: i < 92 ? S.red : S.soft }, dots);
        tl.fromTo(dots.children, { opacity: 0 }, { opacity: 1, duration: 0.05, stagger: 0.012 }, t0 + 1.5);
      },
      broker(g, tl, t0) {
        const node = (x, y, label, fill, sub) => {
          const n = el("g", {}, g); card(n, x - 150, y - 90, 300, 180, fill);
          B(n, x, y - 10, label, 40, { weight: 800, fill: fill === S.dark || fill === S.blue ? "#fbf8f1" : S.text }); if (sub) B(n, x, y + 44, sub, 26, { fill: fill === S.dark || fill === S.blue ? "#fbf8f1" : S.text });
          piv(n, x, y); return n;
        };
        const a = node(220, 330, "CARGO", S.panel), c = node(540, 640, "BROKER", S.red, "the marriage bureau"), b = node(860, 330, "TRUCKERS", S.blue);
        const p1 = el("path", { d: "M 260 430 Q 330 600 400 620", stroke: S.ink, "stroke-width": 7, fill: "none" }, g);
        const p2 = el("path", { d: "M 820 430 Q 750 600 680 620", stroke: S.ink, "stroke-width": 7, fill: "none" }, g);
        [a, b].forEach((n, i) => tl.fromTo(n, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.4, ease: "back.out(2)" }, t0 + 0.2 + i * 0.3));
        tl.fromTo([p1, p2], { drawSVG: "0%" }, { drawSVG: "100%", duration: 0.6 }, t0 + 1.4);
        tl.fromTo(c, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.45, ease: "back.out(2)" }, t0 + 2.6);
        const heart = el("path", { d: "M 540 900 c -40 -50 -110 -10 -70 40 l 70 60 l 70 -60 c 40 -50 -30 -90 -70 -40 z", fill: S.red, stroke: S.ink, "stroke-width": 5 }, g);
        piv(heart, 540, 950);
        tl.fromTo(heart, { scale: 0 }, { scale: 1, duration: 0.5, ease: "elastic.out(1, 0.5)" }, t0 + 3.6);
      },
      board(g, tl, t0) {
        card(g, 80, 170, 920, 880, cfg.set === "night" ? "#10142a" : "#fbf8f1");
        B(g, 540, 240, "LOAD BOARD", 46, { weight: 800, spacing: 6 });
        const rows = [["#4471", "SERVERS · CA → TX", true], ["#4472", "GPUs · NV → IL", false], ["#4473", "SERVERS · TX → GA", true], ["#4474", "RACKS · AZ → OH", false]];
        rows.forEach(([id, what, fake], i) => {
          const r = el("g", {}, g); const y = 330 + i * 165;
          card(r, 120, y, 840, 130, S.panel, { sw: 4 });
          B(r, 150, y + 50, id, 34, { anchor: "start", weight: 800, fill: S.blue }); B(r, 150, y + 95, what, 30, { anchor: "start" });
          B(r, 920, y + 70, `${3 + i} BIDS`, 30, { anchor: "end", weight: 800 });
          tl.fromTo(r, { opacity: 0, x: -60 }, { opacity: 1, x: 0, duration: 0.35, ease: "power3.out" }, t0 + 0.2 + i * 0.25);
          if (fake) {
            const s = el("g", {}, g); card(s, 470, y + 25, 220, 80, "none", { stroke: S.red, sw: 7, rx: 8 });
            B(s, 580, y + 67, "FAKE", 48, { fill: S.red, weight: 800, spacing: 6 });
            piv(s, 580, y + 65);
            tl.fromTo(s, { scale: 2.2, opacity: 0, rotation: -14 }, { scale: 1, opacity: 1, rotation: -8, duration: 0.22, ease: "power4.in" }, t0 + 2.2 + i * 0.4);
          }
        });
      },
      link(g, tl, t0) {
        const m = el("g", {}, g); card(m, 110, 260, 860, 420, cfg.set === "night" ? "#10142a" : "#fbf8f1");
        B(m, 160, 340, "From: dispatch-updates", 32, { anchor: "start" }); B(m, 160, 400, "Re: your load #4473", 40, { anchor: "start", weight: 800 });
        B(m, 160, 470, "Confirm pickup here:", 32, { anchor: "start" });
        const lk = B(m, 160, 540, "track-shipment.co/4473", 38, { anchor: "start", fill: S.blue, weight: 800 });
        el("rect", { x: 160, y: 562, width: 470, height: 5, fill: S.blue }, m);
        tl.fromTo(m, { opacity: 0, y: 50 }, { opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }, t0 + 0.1);
        const cur = el("path", { d: "M 0 0 L 0 64 L 18 48 L 32 78 L 44 72 L 30 44 L 54 44 Z", fill: S.text === "#EDEBF5" ? "#fff" : "#fff", stroke: S.ink, "stroke-width": 4 }, g);
        tl.fromTo(cur, { x: 900, y: 1000 }, { x: 420, y: 535, duration: 1.0, ease: "power3.inOut" }, t0 + 1.0);
        const ring = el("circle", { cx: 420, cy: 540, r: 20, fill: "none", stroke: S.red, "stroke-width": 6 }, g); piv(ring, 420, 540);
        tl.fromTo(ring, { scale: 0.2, opacity: 1 }, { scale: 3, opacity: 0, duration: 0.5 }, t0 + 2.1);
        const acc = el("g", {}, g); card(acc, 260, 760, 560, 230, S.dark);
        B(acc, 540, 830, "TRUCKING CO. ACCOUNT", 34, { fill: "#fbf8f1", weight: 800 });
        const own = H1(acc, 540, 920, "OWNED", 80, { fill: S.red });
        piv(acc, 540, 875);
        tl.fromTo(acc, { rotationX: 90, opacity: 0 }, { rotationX: 0, opacity: 1, duration: 0.45, ease: "back.out(1.6)" }, t0 + 2.4);
      },
      chat(g, tl, t0) {
        card(g, 150, 170, 780, 900, cfg.set === "night" ? "#0f1a16" : "#efe6d6", { rx: 36 });
        el("rect", { x: 150, y: 170, width: 780, height: 120, fill: "#2A7F62", rx: cfg.set === "riso" ? 0 : 36 }, g);
        B(g, 540, 232, "Mummy", 44, { fill: "#fbf8f1", weight: 800 });
        const bub = (x, y, w, s, mine, at) => { const b = el("g", {}, g); card(b, x, y, w, 120, mine ? "#DCF8C6" : "#fff", { sw: 4, rx: 24 }); B(b, x + 30, y + 64, s, 34, { anchor: "start", fill: "#1d1a22" }); tl.fromTo(b, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.3, ease: "back.out(2)" }, at); return b; };
        bub(190, 360, 640, "Give dad's suits to my friend", false, t0 + 0.6);
        bub(470, 520, 420, "Ok ji, sending", true, t0 + 2.4);
        const chk = el("g", {}, g); card(chk, 230, 760, 620, 150, S.blue);
        B(chk, 540, 838, "ACCOUNT LOOKED RIGHT ✓", 40, { fill: "#fbf8f1", weight: 800 });
        piv(chk, 540, 835);
        tl.fromTo(chk, { scale: 0.4, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.35, ease: "back.out(2)" }, t0 + 4.2);
      },
      drivers(g, tl, t0) {
        const id = (x, title, sub, fill, at) => {
          const c = el("g", {}, g); card(c, x - 200, 300, 400, 560, cfg.set === "night" ? "#10142a" : "#fbf8f1");
          el("rect", { x: x - 200, y: 300, width: 400, height: 90, fill, rx: cfg.set === "riso" ? 0 : 18 }, c);
          B(c, x, 348, "DRIVER ID", 34, { fill: "#fbf8f1", weight: 800, spacing: 4 });
          el("circle", { cx: x, cy: 520, r: 90, fill: S.panel2, stroke: S.ink, "stroke-width": 5 }, c);
          B(c, x, 690, title, 38, { weight: 800 }); B(c, x, 750, sub, 28);
          piv(c, x, 580);
          tl.fromTo(c, { rotationY: 90, opacity: 0 }, { rotationY: 0, opacity: 1, duration: 0.45, ease: "power3.out" }, at);
          return c;
        };
        id(290, "REAL DRIVER", "hired without knowing", S.blue, t0 + 0.4);
        id(790, "ACCOMPLICE", "fake licence", S.red, t0 + 2.4);
        const s = el("g", {}, g); card(s, 640, 780, 300, 100, "none", { stroke: S.red, sw: 8, rx: 8 });
        B(s, 790, 832, "FAKE", 60, { fill: S.red, weight: 800, spacing: 8 }); piv(s, 790, 830);
        tl.fromTo(s, { scale: 2.4, opacity: 0, rotation: -18 }, { scale: 1, opacity: 1, rotation: -10, duration: 0.2, ease: "power4.in" }, t0 + 3.6);
      },
      ram(g, tl, t0) {
        const road = el("rect", { x: 0, y: 700, width: W, height: 260, fill: S.dark }, g);
        for (let i = 0; i < 8; i++) el("rect", { x: 20 + i * 140, y: 822, width: 80, height: 14, fill: S.bg }, g);
        const esc = el("g", {}, g); card(esc, 560, 740, 180, 100, S.blue, { rx: 14 }); B(esc, 650, 795, "ESCORT", 28, { fill: "#fbf8f1", weight: 800 });
        const tr = truck(g, 0, 790, 1.5, S.red);   // x moves the inner group
        tl.fromTo(tr, { x: -200 }, { x: 420, duration: 1.4, ease: "power2.in" }, t0 + 0.2);
        tl.fromTo(esc, { x: 0, rotation: 0 }, { x: 260, rotation: 18, svgOrigin: "650 790", duration: 0.5, ease: "power2.out" }, t0 + 1.6);
        const big = H1(g, 540, 430, "RAMMED", 190, { fill: S.red }); fit(big, 960, 190); piv(big, 540, 430);
        tl.fromTo(big, { scale: 2.4, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.2, ease: "power4.in" }, t0 + 1.6);
        const sub = B(g, 540, 1060, "ON TWO LOADS · THE DRIVERS KEPT GOING", 36, { weight: 800 }); fit(sub, 960, 36);
        tl.fromTo(sub, { opacity: 0 }, { opacity: 1, duration: 0.3 }, t0 + 2.6);
        FF.shake(tl, g, t0 + 1.6, 0.4, 16, 3);
      },
      quote(g, tl, t0) {
        card(g, 90, 260, 900, 660, cfg.set === "night" ? "#10142a" : "#fbf8f1");
        const q = H1(g, 160, 420, "“", 220, { fill: S.red, anchor: "start" });
        const lines = ["Those drivers", "weren't properly", "vetted."];
        lines.forEach((s, i) => { const t = H1(g, 540, 470 + i * 120, s, 92, { fill: i === 2 ? S.red : S.text }); fit(t, 820, 92);
          tl.fromTo(t, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.35 }, t0 + 0.3 + i * 0.35); });
        const who = B(g, 540, 850, "SCOTT CORNELL · SPG CARGO AND LOGISTICS", 30, { weight: 800, spacing: 2 }); fit(who, 840, 30);
        tl.fromTo([q, who], { opacity: 0 }, { opacity: 1, duration: 0.3 }, t0 + 0.2);
      },
      lading(g, tl, t0) {
        const p = el("g", {}, g); card(p, 110, 220, 400, 560, "#fbf8f1");
        B(p, 310, 290, "BILL OF LADING", 30, { weight: 800, fill: "#1d1a22" });
        for (let i = 0; i < 6; i++) el("rect", { x: 150, y: 340 + i * 50, width: 320 - (i % 2) * 80, height: 12, fill: "#cfc4b0" }, p);
        B(p, 310, 680, "CONTENTS: SERVERS", 28, { weight: 800, fill: "#1d1a22" });
        const strike = el("rect", { x: 150, y: 676, width: 320, height: 8, fill: S.red }, p); piv(strike, 150, 680);
        const fake = txt(p, 310, 740, "BLANKETS", { size: 44, font: S.hand, fill: S.red, weight: 700 });
        tl.fromTo(p, { opacity: 0, x: -60 }, { opacity: 1, x: 0, duration: 0.4 }, t0 + 0.1);
        tl.fromTo(strike, { scaleX: 0 }, { scaleX: 1, duration: 0.3 }, t0 + 1.4);
        tl.fromTo(fake, { opacity: 0 }, { opacity: 1, duration: 0.3 }, t0 + 1.7);
        const d = el("g", {}, g); card(d, 570, 220, 400, 560, S.dark);
        B(d, 770, 290, "DIGITAL", 32, { weight: 800, fill: "#fbf8f1" });
        el("rect", { x: 720, y: 380, width: 100, height: 80, rx: 10, fill: S.blue }, d);
        el("path", { d: "M 735 380 v -30 a 35 35 0 0 1 70 0 v 30", fill: "none", stroke: S.blue, "stroke-width": 12 }, d);
        B(d, 770, 560, "SIGNED · LOCKED", 30, { fill: "#fbf8f1", weight: 800 });
        H1(d, 770, 670, "✓", 120, { fill: "#7CFFB2" });
        tl.fromTo(d, { opacity: 0, x: 60 }, { opacity: 1, x: 0, duration: 0.4 }, t0 + 2.6);
        const v = B(g, 540, 900, "+ PROPER DRIVER CHECKS", 44, { weight: 800, fill: S.red });
        tl.fromTo(v, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.3 }, t0 + 0.6);
      },
      today(g, tl, t0) {   // teaser intro cards
        B(g, 540, 420, "TODAY", 54, { weight: 800, fill: S.red, spacing: 10 });
        const a = H1(g, 540, 560, "The truck that", 110); const b = H1(g, 540, 690, "wasn't there", 110, { fill: S.blue });
        fit(a, 940, 110); fit(b, 940, 110);
        tl.fromTo([a, b], { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.35, stagger: 0.15 }, t0 + 0.1);
        const w = B(g, 540, 880, "WHY IT MATTERS", 44, { weight: 800, fill: S.red, spacing: 8 });
        const c = H1(g, 540, 980, "your logins work the same way", 64); fit(c, 960, 64);
        tl.fromTo([w, c], { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.35, stagger: 0.15 }, t0 + 2.2);
      },
    };
  }

  // ---------- the show ----------
  window.SHOW = { build(cfg) {
    const S = SETS[cfg.set];
    const q = (f) => f.replace(/"/g, "'");   // font names inside an innerHTML style="..." attribute
    const DUR = cfg.dur;
    const tl = gsap.timeline({ paused: true });
    window.__timelines["main"] = tl;
    const root = document.getElementById("show");
    root.style.cssText = `position:absolute;inset:0;overflow:hidden;background:${S.bg}`;

    // layer 1: graphics (full frame, content inside y 150-1080)
    const vis = div(root, `position:absolute;inset:0;background:${S.bg}`);
    const visSvg = svgBox(vis);
    defs(visSvg, S);
    if (cfg.set === "riso") for (let y = 0; y < H; y += 48) el("rect", { x: 0, y, width: W, height: 2, fill: S.panel }, visSvg);
    if (cfg.set === "paper") el("rect", { x: 0, y: 0, width: W, height: H, fill: "#efe7d8" }, visSvg);
    if (cfg.set === "night") { for (let x = 0; x < W; x += 60) el("rect", { x, y: 0, width: 1, height: H, fill: "#151b36" }, visSvg); for (let y = 0; y < H; y += 60) el("rect", { x: 0, y, width: W, height: 1, fill: "#151b36" }, visSvg); }
    const G = graphics(S, cfg);
    const groups = cfg.segments.map((seg) => {
      if (!seg.vis || !G[seg.vis]) return null;
      const g = el("g", { filter: look(S) }, visSvg);
      G[seg.vis](g, tl, seg.start + (seg.visLead ?? 0));
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

    // PiP frame: branded monitor border, LIVE dot, name
    const pipFrame = div(root, `position:absolute;left:${PIP.x - 8}px;top:${PIP.y - 8}px;width:${PIP.s + 16}px;height:${PIP.s + 16}px;border:8px solid ${S.red};border-radius:36px;box-sizing:border-box;opacity:0`);
    const live = div(pipFrame, `position:absolute;left:16px;top:16px;padding:6px 14px;border-radius:20px;background:${S.ink};color:${S.bg};font:800 22px/1 ${S.body};letter-spacing:2px`);
    live.innerHTML = `<span style="display:inline-block;width:12px;height:12px;border-radius:6px;background:${S.red};margin-right:8px;vertical-align:1px"></span>HABIT`;

    // package: lane bug, lower-third, source chip, ticker, sting, end card
    const pkg = div(root, "position:absolute;inset:0;pointer-events:none");
    const bug = div(pkg, `position:absolute;left:48px;top:64px;display:flex;gap:12px;align-items:center;font:800 28px/1 ${S.body};letter-spacing:3px`);
    bug.innerHTML = `<span style="background:${S.red};color:${S.textOnRed};padding:12px 18px">${cfg.lane}</span><span style="color:${S.text};background:${S.bg};padding:12px 14px;border:3px solid ${S.text}">THE DAILY HABIT</span>`;
    const l3 = div(pkg, `position:absolute;left:0;top:1170px;width:780px;opacity:0`);
    l3.innerHTML = `<div style="background:${S.red};color:${S.textOnRed};font:800 50px/1.1 ${q(S.head)};padding:18px 30px 14px 48px">${cfg.storyTitle[0]}</div>
      <div style="background:${S.ink};color:${S.bg};font:600 30px/1 ${q(S.body)};padding:14px 30px 14px 48px;width:max-content;letter-spacing:2px">${cfg.storyTitle[1].toUpperCase()}</div>`;
    const chip = div(pkg, `position:absolute;right:48px;top:64px;background:${S.bg};color:${S.text};border:3px solid ${S.text};font:700 26px/1 ${S.body};padding:10px 16px;opacity:0`);
    chip.textContent = `SOURCE · ${cfg.source}`;
    const ticker = div(pkg, `position:absolute;left:0;top:1432px;width:1080px;height:64px;background:${S.ink};overflow:hidden;opacity:0`);
    const tickTag = div(ticker, `position:absolute;left:0;top:0;height:64px;z-index:2;background:${S.red};color:${S.textOnRed};font:800 28px/64px ${S.body};padding:0 22px;letter-spacing:3px`);
    tickTag.textContent = "NEXT";
    const tickText = div(ticker, `position:absolute;left:0;top:0;height:64px;white-space:nowrap;color:${S.bg};font:700 30px/64px ${S.body};letter-spacing:2px`);
    tickText.textContent = (cfg.ticker.join("   ◆   ") + "   ◆   ").repeat(3);
    const breaking = div(pkg, `position:absolute;left:0;top:1160px;width:1080px;opacity:0`);
    breaking.innerHTML = `<div style="background:${S.red};color:${S.textOnRed};font:900 70px/1 ${q(S.head)};padding:22px 48px;letter-spacing:4px">BREAKING</div>
      <div style="background:${S.ink};color:${S.bg};font:700 36px/1.2 ${q(S.body)};padding:16px 48px">$100M of AI freight stolen, mostly with paperwork</div>`;

    // captions
    const capBox = div(root, `position:absolute;left:0;top:0;width:1080px;height:0`);
    const cap = div(capBox, `position:absolute;left:60px;width:960px;text-align:center;font:800 62px/1.1 ${S.body === '"FF Mono", monospace' ? '"FF Display", sans-serif' : S.body};color:${S.text};-webkit-text-stroke:0;text-shadow:0 0 0 transparent`);
    const capStyle = (shot) => {
      if (shot === "pip") return { left: 400, width: 640, top: 1240, align: "left" };
      if (shot === "split") return { left: 60, width: 960, top: 990, align: "center" };
      if (shot === "wide") return { left: 60, width: 960, top: 1336, align: "center" };
      return { left: 60, width: 960, top: 1210, align: "center" };
    };

    // sting
    const sting = div(root, `position:absolute;inset:0;opacity:0;background:${S.red}`);
    const stingSvg = svgBox(sting);
    if (cfg.set === "riso") { FF.pixelText(stingSvg, 540, 820, "THE DAILY", 22, "p"); FF.pixelText(stingSvg, 540, 1000, "HABIT", 34, "p"); }
    else { txt(stingSvg, 540, 820, "THE DAILY", { size: 150, font: S.head, fill: S.textOnRed, weight: 900 }); txt(stingSvg, 540, 1000, "HABIT", { size: 230, font: S.head, fill: S.textOnRed, weight: 900 }); }
    txt(stingSvg, 540, 1170, `${cfg.date} · ${cfg.lane}`, { size: 44, font: S.body, fill: S.textOnRed, weight: 700, spacing: 8 });
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

    // platform UI mock (layout sheet only): YouTube / Instagram / Facebook overlays, union of their areas
    if (cfg.ui) {
      const ui = div(root, "position:absolute;inset:0;pointer-events:none");
      div(ui, "position:absolute;left:0;top:1500px;width:1080px;height:420px;background:rgba(0,0,0,.45);border-top:4px dashed #ff0");
      div(ui, "position:absolute;left:900px;top:1000px;width:180px;height:920px;background:rgba(0,0,0,.45);border-left:4px dashed #ff0");
      const lab = div(ui, "position:absolute;left:30px;top:1530px;color:#ff0;font:800 30px/1.3 sans-serif");
      lab.innerHTML = "PLATFORM UI: title, caption, channel, music<br>(YouTube Shorts · IG Reels · FB Reels)";
      const lab2 = div(ui, "position:absolute;left:915px;top:1020px;width:150px;color:#ff0;font:800 24px/1.2 sans-serif");
      lab2.textContent = "like · comment · share · remix";
    }

    // ---------- timeline of framings: [time, shot] keyframes ----------
    const keys = [];
    cfg.segments.forEach((seg) => (seg.shots || [[0, seg.shot]]).forEach(([off, shot]) => keys.push([seg.start + off, shot])));
    keys.sort((a, b) => a[0] - b[0]);
    const TR = 0.55;
    const frameAt = (t) => {
      let i = 0;
      while (i + 1 < keys.length && keys[i + 1][0] <= t) i++;
      const cur = framing(keys[i][1]);
      if (i === 0) return { f: cur, shot: keys[i][1], since: t - keys[0][0] };
      const k = clamp((t - keys[i][0]) / TR);
      return { f: k >= 1 ? cur : mixF(framing(keys[i - 1][1]), cur, ease(k)), shot: keys[i][1], since: t - keys[i][0] };
    };
    const segAt = (t) => cfg.segments.findIndex((s) => t >= s.start && t < s.start + s.dur);
    const env = cfg.env || [], fps = cfg.envFps || 30;
    const mouthAt = (t) => { const i = Math.floor(t * fps); const v = env[i] ?? 0; return clamp((v - 0.06) / 0.5); };
    const blinkAt = (t) => { const p = (t + 0.7) % 3.7; return p < 0.08 ? p / 0.08 : p < 0.16 ? 1 - (p - 0.08) / 0.08 : 0; };
    const words = cfg.words || [];

    const frame = (t) => {
      const { f, shot, since } = frameAt(t);
      cam.style.transform = `translate(${f.tx}px, ${f.ty}px) scale(${f.s})`;
      studio.style.clipPath = `inset(${f.ct}px ${f.cr}px ${f.cb}px ${f.cl}px round ${f.rad}px)`;
      const m = `linear-gradient(to bottom, transparent ${f.ma}px, #000 ${f.mb}px)`;
      studio.style.webkitMaskImage = m; studio.style.maskImage = m;
      studio.style.opacity = f.op;
      vis.style.visibility = shot === "wide" && Math.abs(f.s - 1) < 1e-3 && f.ma < 0 ? "hidden" : "";   // fully behind the studio
      const pipK = shot === "pip" ? clamp((since - 0.3) / 0.3) : 0;
      pipFrame.style.opacity = pipK;
      // graphics visible while their beat runs (and through the incoming transition)
      const si = segAt(t);
      groups.forEach((g, i) => { if (g) g.style.display = i === si || (i === si - 1 && t - cfg.segments[si].start < 0.15) ? "" : "none"; });
      const seg = cfg.segments[si] || cfg.segments[cfg.segments.length - 1];
      wall.set(seg.wall || cfg.wallDefault || "TRUST", seg.wallSub || cfg.storyTitle[0].toUpperCase());
      // Habit: talks with the voice envelope, blinks, looks up at the graphic in the split, at it in the PiP
      const lookY = shot === "split" ? 0.8 : 0, lookX = shot === "pip" ? 0.7 : Math.sin(t * 0.7) * 0.15;
      const talking = mouthAt(t);
      rig.pose({ mouth: talking, blink: blinkAt(t), lookX, lookY, bob: Math.sin(t * 2.1) * 6 + talking * 4, brow: talking > 0.6 ? 0.6 : 0.1, tilt: Math.sin(t * 0.9) * 2 });
      sweeps.forEach((s, i) => { const p = ((t * 0.18 + i / 3) % 1); s.setAttribute("x", -300 + p * 1700); s.setAttribute("opacity", 0.9); });
      // package
      bug.style.opacity = t < (cfg.stingAt ?? -9) + 1.6 && t > (cfg.stingAt ?? -9) ? 0 : t > DUR - (cfg.endDur ?? 0) ? 0 : 1;
      const l3k = cfg.l3At != null ? clamp((t - cfg.l3At) / 0.35) * clamp((cfg.l3At + 4 - t) / 0.35) : 0;
      l3.style.opacity = l3k; l3.style.transform = `translateX(${(1 - l3k) * -80}px)`;
      chip.style.opacity = seg.claim && shot !== "wide" ? clamp((t - seg.start - 0.5) / 0.3) : 0;
      const tk = cfg.tickerAt != null ? clamp((t - cfg.tickerAt) / 0.4) : 0;
      ticker.style.opacity = t > DUR - (cfg.endDur ?? 0) ? 0 : tk;
      tickText.style.transform = `translateX(${1080 - ((t - (cfg.tickerAt ?? 0)) * 170) % 2600}px)`;
      const bk = cfg.breakingAt != null ? clamp((t - cfg.breakingAt) / 0.25) * clamp((cfg.breakingAt + (cfg.breakingDur ?? 4) - t) / 0.25) : 0;
      breaking.style.opacity = bk; breaking.style.transform = `translateX(${(1 - bk) * -120}px)`;
      // sting: red field in, title, an ink wipe out
      if (cfg.stingAt != null) {
        const p = t - cfg.stingAt;
        sting.style.opacity = p >= 0 && p < 1.55 ? 1 : 0;
        // wipes on from the left, holds, slides off to the right with an ink edge leading
        sting.style.clipPath = `inset(0 ${p < 0.25 ? (1 - ease(clamp(p / 0.25))) * 100 : 0}% 0 ${p > 1.1 ? ease(clamp((p - 1.1) / 0.42)) * 100 : 0}%)`;
        stingBar.setAttribute("transform", `translate(${p > 1.1 ? ease(clamp((p - 1.1) / 0.42)) * W - 24 : -W} 0)`);
      }
      if (cfg.endAt != null) end.style.opacity = clamp((t - cfg.endAt) / 0.3);
      // captions: groups of up to 3 words, placed by the framing
      const w = words.findIndex((x) => t >= x.s && t < x.e + 0.25);
      if (w < 0 || t > (cfg.endAt ?? DUR) || (cfg.stingAt != null && t > cfg.stingAt && t < cfg.stingAt + 1.5)) cap.textContent = "";
      else {
        const grp = words.filter((x) => x.g === words[w].g);
        // a pill in the set's paper colour keeps the words readable over any framing (Habit's red shirt included)
        cap.innerHTML = `<span style="background:${S.bg};padding:8px 20px;border-radius:${cfg.set === "riso" ? 0 : 14}px;box-shadow:0 0 0 3px ${S.text}">` +
          grp.map((x) => `<span style="color:${x === words[w] ? S.red : S.text}">${x.w}</span>`).join(" ") + "</span>";
        const c = capStyle(shot);
        Object.assign(cap.style, { left: c.left + "px", width: c.width + "px", top: c.top + "px", textAlign: c.align,
          background: S.bg, padding: "10px 18px", boxDecorationBreak: "clone", display: "block" });
        cap.style.background = "transparent";
      }
    };
    const clock = { t: 0 };
    tl.fromTo(clock, { t: 0 }, { t: DUR, duration: DUR, ease: "none", onUpdate: () => frame(clock.t) }, 0);
    frame(0);
  } };
})();
