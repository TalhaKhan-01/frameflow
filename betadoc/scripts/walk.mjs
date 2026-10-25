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
  for (const path of ["/", "/documentation.html"]) {
    await page.goto(base + path, { waitUntil: "load" });
    await page.waitForTimeout(2500);
    const tag = `${name}${path === "/" ? "" : "-docs"}`;
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
      const drawn = await page.evaluate(() => {
        const c = document.getElementById("scrub"); const d = c.getContext("2d").getImageData(180, 320, 1, 1).data; return d[3];
      });
      if (!drawn) fail(`${tag}: scrub canvas never drew a frame`);
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
