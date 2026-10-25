import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  build: {
    rollupOptions: {
      input: { index: resolve(import.meta.dirname, "index.html"), documentation: resolve(import.meta.dirname, "documentation.html") },
    },
  },
});
