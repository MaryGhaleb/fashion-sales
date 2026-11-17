#!/usr/bin/env node
/*
 * svg_to_png.js
 * Renders every SVG in a charts folder to a high-resolution PNG.
 * Uses `sharp` (npm). Requires: npm install sharp
 *
 * Usage: node svg_to_png.js <charts_dir> <out_dir> [density]
 */
const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

const chartsDir = process.argv[2];
const outDir = process.argv[3];
const density = parseInt(process.argv[4] || "200", 10); // 200 DPI ~= 2.7x scale

if (!chartsDir || !outDir) {
  console.error("Usage: node svg_to_png.js <charts_dir> <out_dir> [density]");
  process.exit(1);
}

fs.mkdirSync(outDir, { recursive: true });

const files = fs.readdirSync(chartsDir).filter((f) => f.toLowerCase().endsWith(".svg")).sort();

(async () => {
  let ok = 0, fail = 0;
  for (const f of files) {
    const src = path.join(chartsDir, f);
    const dst = path.join(outDir, f.replace(/\.svg$/i, ".png"));
    try {
      const info = await sharp(src, { density })
        .png({ compressionLevel: 9 })
        .toFile(dst);
      console.log(`  ✓ ${f}  ->  ${path.basename(dst)}  (${info.width}x${info.height})`);
      ok++;
    } catch (e) {
      console.error(`  ✗ ${f}: ${e.message}`);
      fail++;
    }
  }
  console.log(`\nConverted ${ok} SVG -> PNG (${fail} failed).`);
  if (fail > 0) process.exit(1);
})();