// The Studio: index.html (the HQ) + architecture.html, whose body and script are shared with the betadoc (../betadoc).
// The architecture page reads the betadoc's live.json and frames, served here from ../betadoc/public and copied into dist.
import { cpSync, existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";
import { archInclude } from "../betadoc/arch-include.js";

const BETA = resolve(import.meta.dirname, "../betadoc/public");
const archData = () => ({
  name: "arch-data",
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      const path = (req.url ?? "").split("?")[0];
      if (path !== "/live.json" && !/^\/frames\/f\d\d\.webp$/.test(path)) return next();
      const file = resolve(BETA, "." + path);
      if (!existsSync(file)) return next();
      res.setHeader("Content-Type", path.endsWith(".json") ? "application/json" : "image/webp");
      res.end(readFileSync(file));
    });
  },
  closeBundle() {
    const out = resolve(import.meta.dirname, "dist");
    cpSync(resolve(BETA, "live.json"), resolve(out, "live.json"));
    cpSync(resolve(BETA, "frames"), resolve(out, "frames"), { recursive: true });
  },
});

export default defineConfig({
  plugins: [archInclude(), archData()],
  // gsap and lenis come from this app's node_modules (Vercel installs only web/), even when imported from ../betadoc/src
  resolve: { alias: { "@betadoc": resolve(import.meta.dirname, "../betadoc/src") }, dedupe: ["gsap", "lenis"] },
  server: { fs: { allow: [resolve(import.meta.dirname, "..")] } },
  build: {
    rollupOptions: {
      input: { index: resolve(import.meta.dirname, "index.html"), architecture: resolve(import.meta.dirname, "architecture.html") },
    },
  },
});
