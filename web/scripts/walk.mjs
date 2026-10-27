// Headless walk of the Studio (P13.1.2): every view at 1440 and 390 px, 0 console errors, no horizontal overflow.
// Locked mode: a wrong PIN fails and the right PIN opens it. Open mode (web/access.json): no PIN screen at all.
// Screenshots in web/walk/ (gitignored).
// Usage: [FRAMEFLOW_WEB_PIN=...] node scripts/walk.mjs [--reduced] [base-url]   (--reduced: prefers-reduced-motion)   (default: vite preview on 127.0.0.1:7308)
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const pin = process.env.FRAMEFLOW_WEB_PIN;
const reduced = process.argv.includes("--reduced");
let base = process.argv.slice(2).find((a) => !a.startsWith("--"));
let server;
if (!base) {
  base = "http://127.0.0.1:7308";
  server = spawn("npx", ["vite", "preview", "--host", "127.0.0.1", "--port", "7308", "--strictPort"], { stdio: "ignore" });
  for (let i = 0; i < 50; i++) { try { await fetch(base); break; } catch { await new Promise((r) => setTimeout(r, 200)); } }
}
mkdirSync("walk", { recursive: true });
const views = ["lobby", "cast", "videos", "board", "video/2026-10-25-black-october", "cards", "lessons", "library", "build"];
const browser = await chromium.launch({ channel: "chrome", headless: true });
let failures = 0;
const fail = (m) => { failures++; console.log("FAIL", m); };

for (const width of [1440, 390]) {
  const page = await browser.newPage({ viewport: { width, height: width > 500 ? 900 : 844 }, reducedMotion: reduced ? "reduce" : "no-preference" });
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(base + "/");
  await page.waitForSelector(".street, .mast, #pin", { timeout: 15000 });
  if (await page.locator(".street, .mast").count()) {
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
  await page.waitForSelector(".street, .mast", { timeout: 15000 }).catch(() => fail(`${width}: right PIN did not open`));
  }
  // the HQ (P17.3): the street entrance, the door into the lobby, the crew's ID cards
  await page.goto(base + "/");
  await page.waitForSelector(".street .door", { timeout: 15000 }).catch(() => fail(`${width} street: no entrance`));
  if (!(await page.locator(".door").textContent())?.includes("Enter the Daily Habit HQ")) fail(`${width} street: the door does not say Enter the Daily Habit HQ`);
  { const over = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    if (over > 1) fail(`${width} street: horizontal overflow ${over}px`); }
  await page.waitForTimeout(600);
  await page.screenshot({ path: `walk/street-${width}.png` });
  await page.locator(".door").click();
  await page.waitForSelector(".reception", { timeout: 15000 }).then(() => console.log(`${width} street: door opens the lobby`))
    .catch(() => fail(`${width} street: the door did not open the lobby`));
  await page.goto(`${base}/#/cast`);
  await page.waitForSelector(".idcard", { timeout: 15000 });
  const crew = await page.evaluate(() => ({ cards: document.querySelectorAll(".idcard").length,
    drawn: [...document.querySelectorAll("canvas[data-portrait]")].filter((c) => {
      const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data; let ink = 0;
      for (let i = 0; i < d.length; i += 4) if (d[i] + d[i + 1] + d[i + 2] < 200) ink++;
      return ink > 40; }).length }));
  if (crew.cards < 20 || crew.drawn !== crew.cards) fail(`${width} cast: ${crew.cards} cards, ${crew.drawn} portraits drawn`);
  else console.log(`${width} cast: ${crew.cards} ID cards, every portrait drawn`);
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
  await page.goto(`${base}/#/lobby`);
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
  else if (!(await page.locator(".house-card").textContent())?.includes("Kavi Kalam")) fail(`${width} house: the writer's card does not name Kavi Kalam`);
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
  // voice cues (P17.2.4): off until the visitor turns them on; then a bubble brings its person's cue
  if ((await page.locator(".house-sound").getAttribute("aria-pressed")) !== "false") fail(`${width} cues: sound is not off by default`);
  const cueResp = page.waitForResponse((r) => r.url().includes("/cues/") && r.url().endsWith(".ogg"), { timeout: 30000 }).catch(() => null);
  await page.locator(".house-sound").click();
  if (await page.locator(".hr-play").getAttribute("aria-label") === "Play") await page.locator(".hr-play").click();
  const r = await cueResp;
  if (!r || ![200, 206].includes(r.status())) fail(`${width} cues: no cue played after sound on (${r ? r.status() : "none"})`);
  else console.log(`${width} cues: ${r.url().split("/").pop()} played`);

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
