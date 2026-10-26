// Put local files on a page's <input type=file> without DOM.setFileInputFiles (Chrome 154 kills the renderer
// on that call for Instagram's and Facebook's photo inputs). The bytes go in over DevTools in base64 chunks,
// the page builds File objects, sets them on the input and fires change, as a real file pick would.
//   node scripts/inject-file.mjs <devtools-port> <url-substring> <css-selector> <file>...
import { readFileSync } from "node:fs";
import { basename, extname } from "node:path";

const [port, urlPart, selector, ...files] = process.argv.slice(2);
const TYPES = { ".mp4": "video/mp4", ".mov": "video/quicktime", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg" };
const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const target = targets.find((t) => t.type === "page" && t.url.includes(urlPart));
if (!target) { console.error(`no tab whose URL contains ${urlPart}`); process.exit(2); }

const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
await new Promise((r) => (ws.onopen = r));
const evaluate = (expression) => new Promise((resolve, reject) => {
  const n = ++id;
  pending.set(n, (d) => (d.error || d.result?.exceptionDetails ? reject(new Error(JSON.stringify(d.error || d.result.exceptionDetails).slice(0, 400))) : resolve(d.result.result.value)));
  ws.send(JSON.stringify({ id: n, method: "Runtime.evaluate", params: { expression, awaitPromise: true, returnByValue: true } }));
});

const CHUNK = 3 * 1024 * 1024;   // a multiple of 3, so every chunk is whole base64
await evaluate("window.__ffFiles = []; 1");
for (const f of files) {
  const buf = readFileSync(f);
  await evaluate("window.__ffParts = []; 1");
  for (let i = 0; i < buf.length; i += CHUNK) {
    const b64 = buf.subarray(i, i + CHUNK).toString("base64");
    await evaluate(`window.__ffParts.push(Uint8Array.from(atob(${JSON.stringify(b64)}), c => c.charCodeAt(0))); 1`);
  }
  const type = TYPES[extname(f).toLowerCase()] || "application/octet-stream";
  await evaluate(`window.__ffFiles.push(new File(window.__ffParts, ${JSON.stringify(basename(f))}, {type: ${JSON.stringify(type)}, lastModified: Date.now()})); window.__ffParts = null; 1`);
}
const drop = selector.startsWith("drop:");   // drop:<css> drops the files on that element instead of setting an input
const n = await evaluate(drop ? `(() => { const e = [...document.querySelectorAll(${JSON.stringify(selector.slice(5))})].pop(); if (!e) return -1;
  const dt = new DataTransfer(); window.__ffFiles.forEach(f => dt.items.add(f));
  for (const t of ['dragenter', 'dragover', 'drop']) e.dispatchEvent(new DragEvent(t, {bubbles: true, cancelable: true, dataTransfer: dt}));
  window.__ffFiles = null; return dt.files.length; })()` : `(() => { const i = [...document.querySelectorAll(${JSON.stringify(selector)})].pop(); if (!i) return -1;
  const dt = new DataTransfer(); window.__ffFiles.forEach(f => dt.items.add(f)); i.files = dt.files;
  i.dispatchEvent(new Event('input', {bubbles: true})); i.dispatchEvent(new Event('change', {bubbles: true}));
  window.__ffFiles = null; return dt.files.length; })()`);   // not i.files: some pages empty the input once they've read it
ws.close();
if (n === -1) { console.error(`nothing matching ${selector}`); process.exit(3); }   // callers check the page for the upload itself
console.log(JSON.stringify({ files: n }));
