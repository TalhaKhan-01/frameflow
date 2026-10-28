import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  // Thirdspace House is one engine shared with the Studio web app (web/src/office)
  resolve: { alias: { "@office": resolve(import.meta.dirname, "../web/src/office") } },
  server: { fs: { allow: [resolve(import.meta.dirname, "..")] } },
  build: {
    rollupOptions: {
      input: { index: resolve(import.meta.dirname, "index.html"), documentation: resolve(import.meta.dirname, "documentation.html"),
        architecture: resolve(import.meta.dirname, "architecture.html") },
    },
  },
});
