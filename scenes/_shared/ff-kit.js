/* Frameflow drawing kit: hand-drawn SVG pieces, seek-safe motion helpers and scene transitions.
   Loaded once by index.html after GSAP, its plugins and rough.js. Every scene template uses window.FF.

   Determinism: nothing here calls Math.random or reads the clock. Rough shapes take a seed; jitter comes
   from FF.rng(seed). Everything is placed on the scene's paused GSAP timeline, so any frame can be seeked.
   Colours come from theme tokens (--ff-ink, --ff-fill, ...), so a drawn scene follows the visual identity. */
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const tok = (name, fallback) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

  // mulberry32: small seeded PRNG
  const rng = (seed) => {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };

  const el = (tag, attrs = {}, parent = null) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };

  const svg = (parent, id) => {
    const s = el("svg", { id, class: "ff-svg", viewBox: "0 0 1080 1920", width: 1080, height: 1920 });
    parent.appendChild(s);
    return s;
  };

  const colors = () => ({
    ink: tok("--ff-ink", "#1d1a22"), fill: tok("--ff-fill", "#fbf8f1"), fill2: tok("--ff-fill-2", "#e7dfcf"),
    lit: tok("--ff-lit", "#f5c84b"), dark: tok("--ff-dark", "#3b3743"), accent: tok("--ff-accent", "#1f5fd1"),
    red: tok("--ff-accent-2", "#c8372a"), violet: tok("--ff-accent-3", "#7a4fd6"), muted: tok("--ff-muted", "#5d564b"),
    bg: tok("--ff-bg", "#f3eee4"), marker: tok("--ff-marker", "rgba(245,200,75,.55)"),
  });

  /* A sketcher bound to one <svg>: every shape is a flat fill (plain SVG, easy to recolour) under a rough ink
     outline (rough.js, seeded). Each call takes the next seed, so the same scene always draws the same lines. */
  const sketcher = (s, seed = 1) => {
    const rc = rough.svg(s);
    let n = seed * 101;
    const C = colors();
    const base = (o = {}) => ({ seed: ++n, roughness: o.roughness ?? 1.3, bowing: o.bowing ?? 1.1, stroke: o.stroke ?? C.ink,
      strokeWidth: o.width ?? 4.5, disableMultiStroke: o.single ?? false, preserveVertices: true,
      ...(o.hachure ? { fill: o.hachure, fillStyle: "hachure", hachureGap: o.gap ?? 14, fillWeight: o.fillWeight ?? 2.5, hachureAngle: o.angle ?? -41 } : {}) });
    const wrap = (parent, flat, rough_) => {
      const g = el("g", {}, parent);
      if (flat) { flat.setAttribute("class", "ff-flat"); g.appendChild(flat); }
      rough_.setAttribute("class", "ff-ink");
      g.appendChild(rough_);
      return g;
    };
    return {
      C,
      rect: (p, x, y, w, h, o = {}) => wrap(p, o.fill === "none" ? null : el("rect", { x, y, width: w, height: h, rx: o.r ?? 6, fill: o.fill ?? C.fill }),
        rc.rectangle(x, y, w, h, base(o))),
      circle: (p, cx, cy, d, o = {}) => wrap(p, o.fill === "none" ? null : el("circle", { cx, cy, r: d / 2, fill: o.fill ?? C.fill }),
        rc.circle(cx, cy, d, base(o))),
      ellipse: (p, cx, cy, w, h, o = {}) => wrap(p, o.fill === "none" ? null : el("ellipse", { cx, cy, rx: w / 2, ry: h / 2, fill: o.fill ?? C.fill }),
        rc.ellipse(cx, cy, w, h, base(o))),
      poly: (p, pts, o = {}) => wrap(p, o.fill === "none" ? null : el("polygon", { points: pts.map((q) => q.join(",")).join(" "), fill: o.fill ?? C.fill }),
        rc.polygon(pts, base(o))),
      line: (p, x1, y1, x2, y2, o = {}) => wrap(p, null, rc.line(x1, y1, x2, y2, base({ single: true, ...o }))),
      path: (p, d, o = {}) => wrap(p, o.fill && o.fill !== "none" ? el("path", { d, fill: o.fill }) : null, rc.path(d, base({ single: true, ...o }))),
      curve: (p, pts, o = {}) => wrap(p, null, rc.curve(pts, base({ single: true, ...o }))),
    };
  };

  const text = (parent, x, y, str, o = {}) => {
    // fill="currentColor" + CSS color: the contrast audit hides text by colour, which then reaches SVG text too.
    // Recolour later with gsap .to(text, { color: ... }).
    const t = el("text", { x, y, "text-anchor": o.anchor ?? "middle", "dominant-baseline": o.baseline ?? "middle",
      fill: "currentColor", style: `color:${o.fill ?? colors().ink}`, "font-family": o.font ?? tok("--ff-hand", "cursive"), "font-weight": o.weight ?? 700,
      "font-size": o.size ?? 44, "letter-spacing": o.spacing ?? 0, transform: o.rotate ? `rotate(${o.rotate} ${x} ${y})` : null }, parent);
    t.textContent = str;
    return t;
  };

  /* Shrink an SVG text until it fits maxWidth (call from onUpdate too: exact once the font has loaded). */
  const fitText = (t, maxWidth, size) => {
    let fs = size;
    t.setAttribute("font-size", fs);
    while (t.getComputedTextLength() > maxWidth && fs > 14) { fs -= 2; t.setAttribute("font-size", fs); }
  };

  // ---- motion helpers (all place tweens on a timeline at an absolute time) ----
  const inks = (g) => Array.from(g.querySelectorAll(".ff-ink path"));
  const flats = (g) => Array.from(g.querySelectorAll(".ff-flat"));

  /* Draw a group on: ink strokes trace in (DrawSVG), flat fills fade in behind them. */
  const draw = (tl, g, at, dur = 0.5, o = {}) => {
    const paths = inks(g);
    if (paths.length) tl.fromTo(paths, { drawSVG: "0%" }, { drawSVG: "100%", duration: dur, ease: o.ease ?? "power2.inOut", stagger: o.stagger ?? 0 }, at);
    const f = flats(g);
    if (f.length) tl.fromTo(f, { opacity: 0 }, { opacity: 1, duration: dur * 0.6, ease: "none" }, at + dur * 0.35);
    const texts = Array.from(g.querySelectorAll("text"));
    if (texts.length) tl.fromTo(texts, { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "none", stagger: 0.03 }, at + dur * 0.6);
    return at + dur;
  };

  const hide = (tl, targets, at = 0) => tl.set(targets, { opacity: 0 }, at);

  /* Scale origin. SVG <text> scales about its own anchor point (x, y attributes): a bounding-box origin would be
     measured before the web font loads and leave the text offset once it does. Other SVG pieces use their bbox
     centre (rough paths don't depend on fonts); HTML uses 50% 50%. */
  const origin = (o) => (i, node) => {
    if (o.origin) return o.origin;
    return "50% 50%";
  };
  const svgOrigin = (i, node) => {
    if (node instanceof SVGTextElement) return `${node.getAttribute("x")} ${node.getAttribute("y")}`;
    if (node instanceof SVGGraphicsElement && !(node instanceof SVGSVGElement)) {
      const b = node.getBBox();
      return `${b.x + b.width / 2} ${b.y + b.height / 2}`;
    }
    return undefined;
  };
  /* Pivot set BEFORE the tween (gsap.set): an origin given only in a tween's "to" vars would apply after the
     "from" state, and GSAP's smoothOrigin would then leave the element offset. */
  const originVars = (target, o) => {
    const list = gsap.utils.toArray(target);
    const isSvg = list.length && list[0] instanceof SVGElement;
    gsap.set(list, isSvg && !o.origin ? { svgOrigin: svgOrigin, smoothOrigin: false } : { transformOrigin: origin(o), smoothOrigin: false });
    return {};
  };

  const pop = (tl, target, at, o = {}) =>
    tl.fromTo(target, { scale: o.from ?? 0, opacity: 0, rotation: o.spin ?? 0 },
      { scale: 1, opacity: 1, rotation: 0, duration: o.dur ?? 0.38, ease: o.ease ?? "back.out(2.2)", ...originVars(target, o) }, at);

  const slam = (tl, target, at, o = {}) =>
    tl.fromTo(target, { scale: o.from ?? 2.6, opacity: 0, rotation: o.rotate ?? 0 },
      { scale: 1, opacity: 1, rotation: o.rotate ?? 0, duration: o.dur ?? 0.22, ease: "power4.in", ...originVars(target, o) }, at);

  /* Deterministic shake: relative offsets from a seeded PRNG that sum back to zero, so the target keeps whatever
     position other tweens gave it (never resets x/y to 0). */
  const shake = (tl, target, at, dur = 0.4, amp = 14, seed = 9) => {
    const r = rng(seed);
    const steps = Math.max(4, Math.round(dur / 0.04));
    let px = 0, py = 0;
    for (let i = 0; i < steps; i++) {
      const k = 1 - i / steps;
      const nx = i === steps - 1 ? 0 : (r() * 2 - 1) * amp * k, ny = i === steps - 1 ? 0 : (r() * 2 - 1) * amp * k * 0.6;
      tl.to(target, { x: `+=${nx - px}`, y: `+=${ny - py}`, duration: dur / steps, ease: "none" }, at + (i * dur) / steps);
      px = nx; py = ny;
    }
  };

  /* Pin an SVG element's transform pivot (global SVG coordinates) before any tween touches it. */
  const pivot = (target, x, y) => gsap.set(target, { svgOrigin: `${x} ${y}`, smoothOrigin: false });

  /* Wiggle around a pivot (door knobs, tags): rotation keyframes, ends at rest. */
  const wiggle = (tl, target, at, dur = 0.35, deg = 18, origin = "50% 50%") => {
    const n = 6;
    for (let i = 0; i < n; i++)
      tl.to(target, { rotation: (i % 2 ? -1 : 1) * deg * (1 - i / n), duration: dur / n, ease: "sine.inOut", transformOrigin: origin }, at + (i * dur) / n);
    tl.to(target, { rotation: 0, duration: 0.05, transformOrigin: origin }, at + dur);
  };

  /* "Boil": hand-drawn shimmer. Several seeded redraws of the same object, shown one at a time every `step` s. */
  const boil = (tl, variants, from, to, step = 0.14) => {
    variants.forEach((v, i) => tl.set(v, { opacity: i === 0 ? 1 : 0 }, from));
    let k = 0;
    for (let t = from + step; t < to; t += step) {
      k = (k + 1) % variants.length;
      variants.forEach((v, i) => tl.set(v, { opacity: i === k ? 1 : 0 }, t));
    }
  };

  /* Deterministic text scramble: cycles fixed glyph rows, locks letters left to right. Driven by tween progress
     (onUpdate), never by call(): render workers seek frames in any order, and a progress-driven value is exact. */
  const scramble = (tl, node, finalText, at, dur = 0.7, seed = 5) => {
    const glyphs = "#$%&*+/<>=?@[]{}01";
    const r = rng(seed);
    const rows = Array.from({ length: 12 }, () => Array.from(finalText, (ch) => (ch === " " ? " " : glyphs[Math.floor(r() * glyphs.length)])).join(""));
    const proxy = { p: 0 };
    const paint = () => {
      const i = Math.round(proxy.p * 12);
      const locked = Math.floor((finalText.length * i) / 12);
      node.textContent = i >= 12 ? finalText : finalText.slice(0, locked) + rows[i % rows.length].slice(locked);
    };
    tl.fromTo(proxy, { p: 0 }, { p: 1, duration: dur, ease: "none", onUpdate: paint, onStart: paint, immediateRender: false }, at);
    node.textContent = "";
  };

  /* Typewriter on an element's textContent, progress-driven like scramble. Returns the end time. */
  const type = (tl, node, str, at, cps = 22) => {
    const proxy = { n: 0 };
    const dur = str.length / cps;
    tl.fromTo(proxy, { n: 0 }, { n: str.length, duration: dur, ease: "none", immediateRender: false,
      onUpdate: () => { node.textContent = str.slice(0, Math.round(proxy.n)); } }, at);
    node.textContent = "";
    return at + dur;
  };

  /* Scene transitions. enter/exit animate the scene's root; the build step pairs scene i's exit with scene i+1's enter. */
  const ENTER = {
    "whip-left": (tl, r) => tl.fromTo(r, { xPercent: 70, filter: "blur(18px)" }, { xPercent: 0, filter: "blur(0px)", duration: 0.26, ease: "expo.out" }, 0),
    "whip-right": (tl, r) => tl.fromTo(r, { xPercent: -70, filter: "blur(18px)" }, { xPercent: 0, filter: "blur(0px)", duration: 0.26, ease: "expo.out" }, 0),
    "whip-up": (tl, r) => tl.fromTo(r, { yPercent: 45, filter: "blur(16px)" }, { yPercent: 0, filter: "blur(0px)", duration: 0.28, ease: "expo.out" }, 0),
    punch: (tl, r) => tl.fromTo(r, { scale: 1.22, opacity: 0.2 }, { scale: 1, opacity: 1, duration: 0.24, ease: "power3.out" }, 0),
    drop: (tl, r) => tl.fromTo(r, { yPercent: -18, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 0.42, ease: "bounce.out" }, 0),
    // velocity cut: the outgoing scene speeds into the lens, the new one lands from a rushing zoom and settles
    velocity: (tl, r) => tl.fromTo(r, { scale: 0.68, filter: "blur(16px) brightness(1.15)" }, { scale: 1, filter: "blur(0px) brightness(1)", duration: 0.32, ease: "expo.out" }, 0),
    glitch: (tl, r) => {
      const xs = [26, -34, 18, -12, 6, 0];
      xs.forEach((x, i) => tl.set(r, { x, filter: i < xs.length - 1 ? `hue-rotate(${(i % 2) * 90}deg) contrast(1.4)` : "none" }, i * 0.035));
    },
    cut: () => {},
  };
  const EXIT = {
    "whip-left": (tl, r, d) => tl.to(r, { xPercent: -70, filter: "blur(18px)", duration: 0.2, ease: "expo.in" }, d - 0.2),
    "whip-right": (tl, r, d) => tl.to(r, { xPercent: 70, filter: "blur(18px)", duration: 0.2, ease: "expo.in" }, d - 0.2),
    "whip-up": (tl, r, d) => tl.to(r, { yPercent: -45, filter: "blur(16px)", duration: 0.2, ease: "expo.in" }, d - 0.2),
    punch: (tl, r, d) => tl.to(r, { scale: 0.86, opacity: 0, duration: 0.18, ease: "power2.in" }, d - 0.18),
    drop: (tl, r, d) => tl.to(r, { yPercent: 20, opacity: 0, duration: 0.2, ease: "power2.in" }, d - 0.2),
    // explicit start: tweening a filter up from "none" starts brightness at 0 and flashes the frame black
    velocity: (tl, r, d) => tl.fromTo(r, { scale: 1, filter: "blur(0px) brightness(1)" }, { scale: 1.45, filter: "blur(16px) brightness(1.15)", duration: 0.24, ease: "power3.in", immediateRender: false }, d - 0.24),
    glitch: (tl, r, d) => [0, -22, 30, -8].forEach((x, i) => tl.set(r, { x, filter: i ? "contrast(1.5) saturate(0)" : "none" }, d - 0.14 + i * 0.035)),
    cut: () => {},
  };
  const transitions = (tl, root, D, dur) => {
    (ENTER[D._enter] || ENTER.cut)(tl, root);
    (EXIT[D._exit] || EXIT.cut)(tl, root, dur);
  };

  /* Cue time: a beat's `at` may be a number (seconds from scene start) or a cue name the build resolved from the
     voice's word timings (D._cues). Unknown names fall back. */
  const at = (D, v, fallback = 0) => {
    if (typeof v === "number") return v;
    if (v && D._cues && typeof D._cues[v] === "number") return D._cues[v];
    return fallback;
  };

  /* Gentle constant camera drift so no frame is ever static. */
  const drift = (tl, target, dur, o = {}) =>
    tl.fromTo(target, { scale: o.from ?? 1, x: 0, y: 0 }, { scale: o.to ?? 1.04, x: o.x ?? 0, y: o.y ?? -10, duration: dur, ease: "none", transformOrigin: o.origin ?? "50% 50%" }, 0);


  /* Scene scaffold for drawn templates: root > wrap (transitions) > stage (drift) > paper + shake > cam > svg.
     Returns the pieces and finish(), which adds drift + transitions and registers the timeline. */
  const scene = (id, D, DUR, o = {}) => {
    const root = document.getElementById(id + "-host");   // inner host div: the composition root itself is merged into its slot
    const mk = (cls, parent) => { const d = document.createElement("div"); d.style.cssText = "position:absolute;inset:0"; if (cls) d.className = cls; parent.appendChild(d); return d; };
    const wrap = mk("", root), stage = mk("", wrap);
    stage.style.background = "var(--ff-bg)";   // a real painted background for the contrast audit (the paper grain sits on top)
    mk("ff-paper", stage);
    const shaker = mk("", stage), cam = mk("", shaker);
    const s = svg(cam, id + "-svg");
    const k = sketcher(s, D.seed || o.seed || 1);
    const tl = gsap.timeline({ paused: true });
    let htmlLayer = null;   // HTML layer above the drawing (wrapped text), created on first use only
    const html = () => {
      if (!htmlLayer) { htmlLayer = mk("", cam); htmlLayer.style.pointerEvents = "none"; }
      return htmlLayer;
    };
    let backLayer = null;   // HTML layer under the drawing (set dressing behind drawn text)
    const back = () => {
      if (!backLayer) { backLayer = mk("", cam); cam.insertBefore(backLayer, cam.firstChild); backLayer.style.pointerEvents = "none"; }
      return backLayer;
    };
    const beats = D.beats && D.beats.length ? D.beats : (o.defaultBeats || []);
    const when = (b, i) => at(D, b.at, i === 0 ? 0.05 : (DUR * i) / Math.max(beats.length, 1));
    const finish = () => {
      drift(tl, stage, DUR, { to: o.drift ?? 1.035 });
      transitions(tl, wrap, D, DUR);
      window.__timelines[id] = tl;
    };
    return { root, wrap, stage, shaker, cam, s, k, C: k.C, tl, html, back, beats, when, finish };
  };

  /* Kicker: small caps label at the top of the frame with a drawn rule. */
  const kicker = (sc, str, at_ = 0.05, y = 300) => {
    if (!str) return;
    const g = el("g", {}, sc.s);
    const t = text(g, 80, y, str.toUpperCase(), { anchor: "start", size: 40, fill: sc.C.accent, font: tok("--ff-body"), spacing: 6 });
    fitText(t, 900, 40);
    const r = sc.k.line(g, 80, y + 34, 80 + Math.min(t.getComputedTextLength(), 900), y + 34, { stroke: sc.C.accent, width: 5 });
    draw(sc.tl, r, at_, 0.4);
    sc.tl.fromTo(t, { opacity: 0, x: -20 }, { opacity: 1, x: 0, duration: 0.3 }, at_);
    return g;
  };

  /* Drawn icons shared by templates (flow nodes, end card art): phone, kitchen, server, page, database, robot,
     stranger, door; anything else draws a plain box. k is the scene's sketcher. */
  const icon = (k, g, kind, cx, cy) => {
    const C = k.C;
    if (kind === "phone") {
      k.rect(g, cx - 55, cy - 95, 110, 190, { fill: C.fill, r: 18 });
      k.rect(g, cx - 42, cy - 72, 84, 128, { fill: C.lit, width: 3 });
      k.circle(g, cx, cy + 74, 14, { fill: C.fill2, width: 2.5 });
    } else if (kind === "kitchen") {
      k.ellipse(g, cx, cy + 40, 150, 34, { fill: C.dark, width: 3 });
      k.rect(g, cx - 70, cy - 10, 140, 64, { fill: C.red });
      k.line(g, cx - 92, cy + 4, cx - 70, cy + 4, { width: 6 });
      k.line(g, cx + 70, cy + 4, cx + 92, cy + 4, { width: 6 });
      const steam = el("g", { class: "steam" }, g);
      [-30, 0, 30].forEach((dx) => k.curve(steam, [[cx + dx, cy - 22], [cx + dx + 12, cy - 50], [cx + dx - 10, cy - 76], [cx + dx + 6, cy - 100]], { width: 4, stroke: C.muted }));
    } else if (kind === "server") {
      for (let r = 0; r < 3; r++) { k.rect(g, cx - 80, cy - 90 + r * 62, 160, 50, { fill: C.fill2 }); k.circle(g, cx + 54, cy - 65 + r * 62, 12, { fill: C.lit, width: 2 }); }
    } else if (kind === "page") {
      k.rect(g, cx - 70, cy - 95, 140, 190, { fill: C.fill });
      for (let r = 0; r < 5; r++) k.line(g, cx - 48, cy - 60 + r * 30, cx + (r === 4 ? 10 : 48), cy - 60 + r * 30, { width: 3.5, stroke: C.muted });
    } else if (kind === "database") {
      k.ellipse(g, cx, cy - 70, 150, 44, { fill: C.fill2 });
      k.rect(g, cx - 75, cy - 70, 150, 140, { fill: C.fill2, r: 0 });
      k.ellipse(g, cx, cy + 70, 150, 44, { fill: C.fill2 });
    } else if (kind === "robot") {
      k.rect(g, cx - 60, cy - 70, 120, 100, { fill: C.fill, r: 14 });
      k.circle(g, cx - 24, cy - 22, 24, { fill: C.accent, width: 2 });
      k.circle(g, cx + 24, cy - 22, 24, { fill: C.accent, width: 2 });
      k.rect(g, cx - 50, cy + 40, 100, 60, { fill: C.accent, r: 10 });
    } else if (kind === "stranger") {
      k.path(g, `M ${cx - 62} ${cy + 90} Q ${cx - 70} ${cy - 40} ${cx} ${cy - 96} Q ${cx + 70} ${cy - 40} ${cx + 62} ${cy + 90} Z`, { fill: C.ink, width: 3 });
      k.ellipse(g, cx, cy - 22, 64, 74, { fill: C.dark, width: 2 });
      k.circle(g, cx - 13, cy - 26, 9, { fill: C.lit, width: 1 });
      k.circle(g, cx + 13, cy - 26, 9, { fill: C.lit, width: 1 });
    } else if (kind === "door") {
      k.rect(g, cx - 60, cy - 100, 120, 200, { fill: C.fill2 });
      k.circle(g, cx + 36, cy, 14, { fill: C.ink, width: 2 });
    } else {
      k.rect(g, cx - 80, cy - 60, 160, 120, { fill: C.fill2 });
    }
  };

  /* A vertical position given either in pixels or as a fraction of the frame height (0-1). */
  const ypos = (v, fallback) => (typeof v !== "number" ? fallback : v <= 1 ? v * 1920 : v);

  /* Pixel art from the HQ (web/src/office/sprites.ts): the crew keep their Riso Press colours in every theme.
     FF.pixel draws a grid of slot letters ('.' is clear) as crisp rects; FF.pixelText uses the HQ's 3 x 5 font. */
  const PIX = { k: "#1B1B1B", s: "#F0B8A8", h: "#1F3A93", a: "#D2392B", A: "#1F3A93", b: "#5B2A6E", w: "#F3EBDD",
    m: "#7F8CC0", r: "#D2392B", p: "#FBF6EC", g: "#FF6B5B", y: "#F2C6BC", V: "#1F3A93" };
  const HABIT_PX = [
    "..mmmmmmmm..", ".mhhhhhhhhm.", ".mhhhhhhhhm.", "mmssssssssmm", "mmksssskssmm", "mmssssssssmm", "..sssoosss..",
    "...ssssss...", "..aaawwaaa..", ".aaaaaaaaaa.", "saaaaaaaaaas", "saaaaaaaaaas", "saaaaaaaaaas", ".aaaaaaaaaa.",
    ".bbbbbbbbbb.", ".bbbbbbbbbb.", ".bbbb..bbbb.", ".bbbb..bbbb.", ".kkkk..kkkk."];
  const pixel = (parent, grid, x, y, size, colors = {}) => {
    const g = el("g", { "shape-rendering": "crispEdges" }, parent);
    grid.forEach((row, r) => {
      for (let c = 0; c < row.length; ) {   // one rect per run of the same slot keeps the SVG small
        const ch = row[c]; let e = c + 1;
        while (e < row.length && row[e] === ch) e++;
        const fill = ch === "." ? null : colors[ch] ?? PIX[ch] ?? ch;
        if (fill) el("rect", { x: x + c * size, y: y + r * size, width: (e - c) * size, height: size, fill }, g);
        c = e;
      }
    });
    return g;
  };
  const GLYPHS = "A .#. #.# ### #.# #.#|B ##. #.# ##. #.# ##.|C .## #.. #.. #.. .##|D ##. #.# #.# #.# ##.|E ### #.. ##. #.. ###|F ### #.. ##. #.. #..|G .## #.. #.# #.# .##|H #.# #.# ### #.# #.#|I ### .#. .#. .#. ###|J ..# ..# ..# #.# .#.|K #.# ##. #.. ##. #.#|L #.. #.. #.. #.. ###|M #.# ### ### #.# #.#|N #.# ### ### ### #.#|O .#. #.# #.# #.# .#.|P ##. #.# ##. #.. #..|Q .#. #.# #.# ##. .##|R ##. #.# ##. #.# #.#|S .## #.. .#. ..# ##.|T ### .#. .#. .#. .#.|U #.# #.# #.# #.# ###|V #.# #.# #.# #.# .#.|W #.# #.# ### ### #.#|X #.# #.# .#. #.# #.#|Y #.# #.# .#. .#. .#.|Z ### ..# .#. #.. ###|0 ### #.# #.# #.# ###|1 .#. ##. .#. .#. ###|2 ##. ..# .#. #.. ###|3 ##. ..# .#. ..# ##.|4 #.# #.# ### ..# ..#|5 ### #.. ##. ..# ##.|6 .## #.. ### #.# ###|7 ### ..# .#. .#. .#.|8 ### #.# ### #.# ###|9 ### #.# ### ..# ##.|! .#. .#. .#. ... .#.|? ##. ..# .#. ... .#.|. ... ... ... ... .#.|: ... .#. ... .#. ...|/ ..# ..# .#. #.. #..|- ... ... ### ... ...|+ ... .#. ### .#. ...|$ .## ##. .#. .## ##.|% #.. ..# .#. #.. ..#";
  const FONT = {};
  for (const g of GLYPHS.split("|")) { const [ch, ...rows] = g.trim().split(" "); FONT[ch] = rows; }
  const pixelText = (parent, cx, cy, str, size, slot = "r") => {
    const s_ = str.toUpperCase(), w = s_.length * 4 - 1;
    const rows = [0, 1, 2, 3, 4].map((r) => [...s_].map((ch) => (FONT[ch] ?? ["...", "...", "...", "...", "..."])[r].replace(/#/g, slot)).join("."));
    return pixel(parent, rows, cx - (w * size) / 2, cy - (5 * size) / 2, size);
  };

  window.FF = { pixel, pixelText, HABIT_PX, icon, ypos, pivot, scene, kicker, NS, el, svg, originVars, sketcher, text, fitText, colors, rng, draw, hide, pop, slam, shake, wiggle, boil, scramble, type, transitions, at, drift, tok };
})();
