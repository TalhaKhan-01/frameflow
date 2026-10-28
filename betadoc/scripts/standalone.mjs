// One self-contained HTML file of the architecture page, to share by hand (opens from disk, no server).
// Builds the page alone (fonts inlined), then inlines the CSS and JS, and bakes in live.json plus the frames it shows.
// Usage: node scripts/standalone.mjs [out.html]   (default: ../out/share/frameflow-architecture.html)
import { mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { build } from "vite";
import { archInclude } from "../arch-include.js";

const root = resolve(import.meta.dirname, "..");
const tmp = resolve(root, "dist-standalone");
const out = resolve(process.argv[2] ?? resolve(root, "../out/share/frameflow-architecture.html"));
const SITE = "https://frameflow-betadoc.vercel.app";

await build({
  root, configFile: false, logLevel: "warn", publicDir: false, plugins: [archInclude()],
  build: { outDir: tmp, emptyOutDir: true, assetsInlineLimit: () => true, cssCodeSplit: false, modulePreload: false,
    rollupOptions: { input: resolve(root, "architecture.html"), output: { codeSplitting: false } } },
});

const asset = (href) => readFileSync(resolve(tmp, "." + href), "utf8");
let html = readFileSync(resolve(tmp, "architecture.html"), "utf8");
html = html.replace(/<link rel="stylesheet"[^>]*href="([^"]+)"[^>]*>/g, (_, h) => `<style>${asset(h)}</style>`);
let js = "";
html = html.replace(/<script type="module"[^>]*src="([^"]+)"[^>]*><\/script>/g, (_, h) => { js = asset(h); return ""; });
if (!js) throw new Error("no module script found in the build");

const frames = {};
const used = [...new Set([...Array.from({ length: 12 }, (_, i) => 1 + i * 6), 36])];
for (const n of used) {
  const f = `f${String(n).padStart(2, "0")}.webp`;
  frames[f] = `data:image/webp;base64,${readFileSync(resolve(root, "public/frames", f)).toString("base64")}`;
}
const live = JSON.parse(readFileSync(resolve(root, "public/live.json"), "utf8"));
html = html.replace('src="/frames/f36.webp"', `src="${frames["f36.webp"]}"`)
  .replace('<link rel="icon" href="/favicon.svg" type="image/svg+xml" />',
    `<link rel="icon" href="data:image/svg+xml;base64,${readFileSync(resolve(root, "public/favicon.svg")).toString("base64")}" type="image/svg+xml" />`)
  .replace(/(href|content)="\/(?!\/)/g, `$1="${SITE}/`)      // site links (overview, docs, og image) point at the live betadoc
  .replace("</body>", () => `<script>window.ARCH_BAKED = ${JSON.stringify({ live, frames }).replace(/</g, "\\u003c")};</script>
<script type="module">${js.replace(/<\/script/gi, "<\\/script")}</script>
</body>`);
if (/(src|href)="\/(?!\/)/.test(html)) throw new Error("a root-relative path is left: " + html.match(/(src|href)="\/(?!\/)[^"]*"/)[0]);
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, html);
rmSync(tmp, { recursive: true, force: true });
console.log(`${out} · ${(Buffer.byteLength(html) / 1024).toFixed(0)} KB · live data from ${live.generated}`);
