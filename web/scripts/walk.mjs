// Headless walk of the Studio (P13.1.2): every view at 1440 and 390 px, 0 console errors, no horizontal overflow.
// Locked mode: a wrong PIN fails and the right PIN opens it. Open mode (web/access.json): no PIN screen at all.
// Screenshots in web/walk/ (gitignored).
// Usage: [FRAMEFLOW_WEB_PIN=...] node scripts/walk.mjs [base-url]   (default: vite preview on 127.0.0.1:7308)
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const pin = process.env.FRAMEFLOW_WEB_PIN;
let base = process.argv[2];
let server;
if (!base) {
  base = "http://127.0.0.1:7308";
  server = spawn("npx", ["vite", "preview", "--host", "127.0.0.1", "--port", "7308", "--strictPort"], { stdio: "ignore" });
  for (let i = 0; i < 50; i++) { try { await fetch(base); break; } catch { await new Promise((r) => setTimeout(r, 200)); } }
}
mkdirSync("walk", { recursive: true });
const views = ["today", "videos", "board", "video/2026-10-25-black-october", "cards", "lessons", "library", "build"];
const browser = await chromium.launch({ channel: "chrome", headless: true });
let failures = 0;
const fail = (m) => { failures++; console.log("FAIL", m); };

for (const width of [1440, 390]) {
  const page = await browser.newPage({ viewport: { width, height: width > 500 ? 900 : 844 } });
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(base + "/");
  await page.waitForSelector(".mast, #pin", { timeout: 15000 });
  if (await page.locator(".mast").count()) {
    console.log(`${width}: open mode, no PIN screen`);
  } else {
  if (!pin) { console.error("locked mode: FRAMEFLOW_WEB_PIN is not set"); process.exit(2); }
  await page.fill("#pin", "00000000");
  await page.click("button[type=submit]");
  await page.waitForFunction(() => document.getElementById("pin-msg")?.textContent?.includes("doesn't open"), null, { timeout: 15000 })
    .then(() => console.log(`${width}: wrong PIN refused`)).catch(() => fail(`${width}: wrong PIN was not refused`));
  await page.screenshot({ path: `walk/lock-${width}.png` });
  await page.fill("#pin", pin);
  await page.click("button[type=submit]");
  await page.waitForSelector(".mast", { timeout: 15000 }).catch(() => fail(`${width}: right PIN did not open`));
  }
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
  // Thirdspace House (P16): tap a floor, the lift buttons, a desk card, back to the street, the replay scrubber
  await page.goto(`${base}/#/today`);
  await page.waitForSelector(".house canvas", { timeout: 15000 });
  await page.waitForTimeout(800);
  const viewOf = () => page.evaluate(() => document.querySelector(".house")?.getAttribute("data-view"));
  await page.locator(".house-lift button[data-floor='2']").click();
  await page.waitForTimeout(900);
  if (await viewOf() !== "int") fail(`${width} house: the lift button did not go inside`);
  if (!(await page.locator(".house-where b").textContent())?.includes("Booth")) fail(`${width} house: floor 2 is not the Booth`);
  await page.locator(".house-lift button[data-floor='1']").click();
  await page.waitForTimeout(700);
  if (!(await page.locator(".house-where b").textContent())?.includes("Writers")) fail(`${width} house: the lift did not change floors`);
  await page.screenshot({ path: `walk/house-inside-${width}.png` });
  await page.locator(".house-mirror button[data-desk='writer']").focus();
  await page.keyboard.press("Enter");
  await page.waitForTimeout(300);
  if (await page.locator(".house-card").isHidden()) fail(`${width} house: the desk card did not open`);
  else if (!(await page.locator(".house-card h3").textContent())?.includes("Writer")) fail(`${width} house: wrong desk card`);
  await page.screenshot({ path: `walk/house-card-${width}.png` });
  await page.locator(".house-stage").focus();
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(800);
  if (await viewOf() !== "ext") fail(`${width} house: Escape did not return to the street`);
  await page.locator(".house-stage canvas").click();   // the middle of the street view is always a floor
  await page.waitForTimeout(900);
  if (await viewOf() !== "int") fail(`${width} house: tapping a floor did not go inside`);
  await page.locator(".house-street").click();
  await page.waitForTimeout(800);
  if (await page.locator(".hr-scrub").count()) {
    await page.locator(".hr-scrub").evaluate((el) => { el.value = "990"; el.dispatchEvent(new Event("input")); });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `walk/house-end-${width}.png` });
  }
  console.log(`${width} house: floors, lift, card, street, scrub ok`);

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
