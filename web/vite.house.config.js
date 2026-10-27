// Thirdspace House as one ES module for the local control panel (Code/frameflow-control serves dist-house/).
// npm run build:house  ->  dist-house/house.js + house.css
import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  publicDir: false,
  build: {
    outDir: "dist-house",
    emptyOutDir: true,
    lib: { entry: resolve(import.meta.dirname, "src/office/house.ts"), formats: ["es"], fileName: () => "house.js", cssFileName: "house" },
  },
});
