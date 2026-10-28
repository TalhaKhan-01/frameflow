// Headless walk of the betadoc (P13.2.2): index + documentation at 1440, 390 and reduced motion.
// 0 console errors, no horizontal overflow, live numbers filled, frames scrub. Screenshots in betadoc/walk/.
// Usage: node scripts/walk.mjs [base-url]   (default: vite preview on 127.0.0.1:7309)
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

let base = process.argv[2];
let server;
if (!base) {
  base = "http://127.0.0.1:7309";
  server = spawn("npx", ["vite", "preview", "--host", "127.0.0.1", "--port", "7309", "--strictPort"], { stdio: "ignore" });
  for (let i = 0; i < 50; i++) { try { await fetch(base); break; } catch { await new Promise((r) => setTimeout(r, 200)); } }
}
mkdirSync("walk", { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
let failures = 0;
const fail = (m) => { failures++; console.log("FAIL", m); };

for (const [name, width, reduced] of [["desktop", 1440, false], ["phone", 390, false], ["reduced", 1440, true]]) {
  const ctx = await browser.newContext({ viewport: { width, height: width > 500 ? 900 : 844 }, reducedMotion: reduced ? "reduce" : "no-preference" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  for (const path of ["/", "/documentation.html", "/architecture.html"]) {
    await page.goto(base + path, { waitUntil: "load" });
    await page.waitForTimeout(2500);
    const tag = `${name}${path === "/" ? "" : path === "/documentation.html" ? "-docs" : "-arch"}`;
    await page.screenshot({ path: `walk/${tag}-0.png` });
    if (path === "/") {
      const wire = await page.textContent("#wire-text");
      if (!/Live wire · .+ lane/.test(wire ?? "")) fail(`${tag}: live wire not filled (${wire})`);
      const posted = await page.textContent('[data-count="videos_posted"]');
      if (!/\d/.test(posted ?? "")) fail(`${tag}: counters not filled`);
      const H = await page.evaluate(() => document.documentElement.scrollHeight);
      for (const f of [0.2, 0.3, 0.42, 0.6, 0.8]) {
        await page.evaluate((y) => window.scrollTo(0, y), Math.round(H * f));
        await page.waitForTimeout(900);
        await page.screenshot({ path: `walk/${tag}-${Math.round(f * 100)}.png` });
      }
      // Thirdspace House (P16): scrolling to a floor story takes the building inside that floor
      await page.evaluate(() => {   // into the trigger band: mid-screen on desktop, below the sticky stage on phones
        const li = document.querySelector('.floors li[data-floor="2"]'), r = li.getBoundingClientRect();
        const band = innerWidth <= 900 ? 0.77 : 0.5;
        window.scrollBy(0, r.top + r.height / 2 - innerHeight * band);
      });
      await page.waitForTimeout(1600);
      const inside = await page.evaluate(() => [document.querySelector("#house-stage")?.getAttribute("data-view"), document.querySelector("#house-stage .house-where b")?.textContent]);
      if (inside[0] !== "int" || !inside[1]?.includes("Booth")) fail(`${tag}: the house did not go inside the Booth (${inside})`);
      await page.screenshot({ path: `walk/${tag}-house.png` });
      await page.evaluate(() => document.getElementById("house").scrollIntoView({ block: "start" }));
      await page.waitForTimeout(1200);
      await page.screenshot({ path: `walk/${tag}-house-top.png` });
      const drawn = await page.evaluate(() => {
        const c = document.getElementById("scrub"); const d = c.getContext("2d").getImageData(180, 320, 1, 1).data; return d[3];
      });
      if (!drawn) fail(`${tag}: scrub canvas never drew a frame`);
      await page.click('a[href="#tour"]');
      await page.waitForTimeout(1500);
      const inView = await page.evaluate(() => { const r = document.getElementById("tour-video").getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; });
      if (!inView) fail(`${tag}: the tour button did not bring the video into view`);
      const ok = await page.evaluate(async () => { const v = document.getElementById("tour-video"); v.muted = true;
        try { await v.play(); } catch { return false; } await new Promise((r) => setTimeout(r, 1500)); const t = v.currentTime; v.pause(); return v.readyState >= 2 && t > 0; });
      if (!ok) fail(`${tag}: tour video did not play`);
      await page.screenshot({ path: `walk/${tag}-tour.png` });
    }
    if (path === "/architecture.html") {
      // every diagram drawn, live numbers in, the packets moving; screenshots down the page
      const st = await page.evaluate(() => ({ packets: document.querySelectorAll(".map .packets circle").length,
        ticks: document.querySelectorAll(".dial .d-ticks line").length, bars: document.querySelectorAll(".funnel .f-bars rect").length,
        strip: document.querySelectorAll("#strip img").length, ideas: document.querySelector('[data-live="ideas"]')?.textContent }));
      if (st.packets < 20 || st.ticks !== 24 || st.bars !== 15 || st.strip !== 12) fail(`${tag}: diagrams not built ${JSON.stringify(st)}`);
      if (!/\d/.test(st.ideas ?? "")) fail(`${tag}: live numbers not filled`);
      for (const id of ["clock", "intake", "brief", "board", "show", "render", "gates", "publish", "learn", "models", "infra"]) {
        await page.evaluate((i) => { const el = document.getElementById(i); window.scrollTo(0, el.getBoundingClientRect().top + scrollY + (i === "board" || i === "clock" || i === "render" ? innerHeight * 0.9 : 0)); }, id);
        await page.waitForTimeout(1100);
        await page.screenshot({ path: `walk/${tag}-${id}.png` });
      }
      const gantt = await page.evaluate(() => document.querySelectorAll("#gantt .g-row").length);
      if (!gantt) fail(`${tag}: latest make timeline empty`);
    }
    const over = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    if (over > 1) fail(`${tag}: horizontal overflow ${over}px`);
    console.log(`${tag}: ok`);
  }
  if (errors.length) fail(`${name}: console errors: ${errors.join(" | ")}`);
  await ctx.close();
}
await browser.close();
server?.kill();
console.log(failures ? `${failures} failure(s)` : "WALK OK");
process.exit(failures ? 1 : 0);
