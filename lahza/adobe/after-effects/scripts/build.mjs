// CEP paneli uchun bitta IIFE bundle: dist/main.js + dist/main.css.
// CEP 12 = Chromium 99 (CEP 12 HTML Extension Cookbook), shuning uchun target chrome99.
// index.html bundle'ni nisbiy yo'l (./dist/main.js) bilan oladi — file:// da ishlaydi.
import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const options = {
  entryPoints: ["src/main.tsx"],
  bundle: true,
  format: "iife",
  target: ["chrome99"],
  outdir: "dist",
  entryNames: "main",
  minify: !watch,
  sourcemap: watch ? "inline" : false,
  jsx: "automatic",
  define: { "process.env.NODE_ENV": watch ? '"development"' : '"production"' },
  logLevel: "info",
  legalComments: "eof",
};

if (watch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
} else {
  await esbuild.build(options);
}
