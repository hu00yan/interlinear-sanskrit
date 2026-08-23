import { defineConfig, type Plugin } from "vite";
import { gzipSync, brotliCompressSync } from "node:zlib";
import { readdirSync, statSync, readFileSync, writeFileSync } from "node:fs";
import { join, extname } from "node:path";

function compressionPlugin(): Plugin {
  return {
    name: "precompress",
    closeBundle() {
      const outDir = "dist";
      const threshold = 1024;
      const skipExts = new Set([".gz", ".br", ".map"]);
      const walk = (dir: string) => {
        for (const e of readdirSync(dir, { withFileTypes: true })) {
          const p = join(dir, e.name);
          if (e.isDirectory()) {
            if (p === join(outDir, "data")) continue;
            walk(p);
          } else if (e.isFile()) {
            if (skipExts.has(extname(p))) continue;
            try {
              const st = statSync(p);
              if (st.size < threshold) continue;
              if (st.size > 5 * 1024 * 1024) continue;
              const buf = readFileSync(p);
              try {
                writeFileSync(p + ".gz", gzipSync(buf, { level: 9 }));
              } catch {}
              try {
                writeFileSync(
                  p + ".br",
                  brotliCompressSync(buf, {
                    params: {
                      [0x06]: 11,
                      [0x0b]: 10,
                      [0x05]: 22,
                    },
                  }),
                );
              } catch {}
            } catch {}
          }
        }
      };
      walk(outDir);
    },
  };
}

export default defineConfig({
  plugins: [compressionPlugin()],
});
