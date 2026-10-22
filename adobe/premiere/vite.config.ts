// UXP uchun bitta bundle: rasmiy namuna (uxp-premiere-pro-samples/premiere-api) kabi Vite + CJS chiqish,
// host modullari (`premierepro`, `uxp`, `os`, `fs`) tashqi — ularni UXP `require()` beradi.
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const r = (p: string) => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig({
  publicDir: "public",
  base: "./",
  resolve: { alias: { "@shared": r("../shared/src") } },
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    minify: false,
    sourcemap: true,
    target: "es2020",
    rolldownOptions: {
      input: r("src/main.tsx"),
      external: ["premierepro", "uxp", "os", "fs"],
      output: { format: "cjs", entryFileNames: "index.js", codeSplitting: false },
    },
  },
  test: { include: ["test/**/*.test.ts"], environment: "node" },
});
