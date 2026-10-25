// Headless walk of the Studio (P13.1.2): wrong PIN fails, right PIN opens every view at 1440 and 390 px,
// 0 console errors, no horizontal overflow. Screenshots in web/walk/ (gitignored).
// Usage: FRAMEFLOW_WEB_PIN=... node scripts/walk.mjs [base-url]   (default: vite preview on 127.0.0.1:7308)
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const pin = process.env.FRAMEFLOW_WEB_PIN;
if (!pin) { console.error("FRAMEFLOW_WEB_PIN is not set"); process.exit(2); }
let base = process.argv[2];
let server;
if (!base) {
  base = "http://127.0.0.1:7308";
  server = spawn("npx", ["vite", "preview", "--host", "127.0.0.1", "--port", "7308", "--strictPort"], { stdio: "ignore" });
  for (let i = 0; i < 50; i++) { try { await fetch(base); break; } catch { await new Promise((r) => setTimeout(r, 200)); } }
}
mkdirSync("walk", { recursive: true });
const views = ["today", "videos", "video/2026-10-25-black-october", "cards", "lessons", "library", "build"];
const browser = await chromium.launch({ channel: "chrome", headless: true });
let failures = 0;
const fail = (m) => { failures++; console.log("FAIL", m); };

for (const width of [1440, 390]) {
  const page = await browser.newPage({ viewport: { width, height: width > 500 ? 900 : 844 } });
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(base + "/");
  await page.fill("#pin", "00000000");
  await page.click("button[type=submit]");
  await page.waitForFunction(() => document.getElementById("pin-msg")?.textContent?.includes("doesn't open"), null, { timeout: 15000 })
    .then(() => console.log(`${width}: wrong PIN refused`)).catch(() => fail(`${width}: wrong PIN was not refused`));
  await page.screenshot({ path: `walk/lock-${width}.png` });
  await page.fill("#pin", pin);
  await page.click("button[type=submit]");
  await page.waitForSelector(".mast", { timeout: 15000 }).catch(() => fail(`${width}: right PIN did not open`));
  for (const v of views) {
    await page.goto(`${base}/#/${v}`);
    await page.waitForSelector(".page", { timeout: 15000 });
    await page.waitForTimeout(300);
    const { over, text } = await page.evaluate(() => ({ over: document.documentElement.scrollWidth - innerWidth, text: document.querySelector(".page")?.textContent?.length ?? 0 }));
    if (over > 1) fail(`${width} ${v}: horizontal overflow ${over}px`);
    if (text < 100) fail(`${width} ${v}: page looks empty`);
    await page.screenshot({ path: `walk/${v.replace(/\W+/g, "-")}-${width}.png`, fullPage: true });
    console.log(`${width} ${v}: ok (${text} chars)`);
  }
  if (await page.locator("video").count() === 0) {
    await page.goto(`${base}/#/video/2026-10-25-black-october`);
  }
  if (errors.length) fail(`${width}: console errors: ${errors.join(" | ")}`);
  await page.close();
}
await browser.close();
server?.kill();
console.log(failures ? `${failures} failure(s)` : "WALK OK");
process.exit(failures ? 1 : 0);
