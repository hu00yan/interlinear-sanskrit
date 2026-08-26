// Golden audit: N tokens per page x 3 pages, spec checks A1-A7.
// usage: node tests/golden-audit.mjs <baseUrl> <outJson>
import { chromium } from "@playwright/test";
const EXE = "/Users/huyan00/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium";
const BASE = process.argv[2] || "http://localhost:4176";
const OUT = process.argv[3] || "test-results/golden-audit.json";
const PER_PAGE = 20;
const browser = await chromium.launch({ executablePath: EXE });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
await page.goto(`${BASE}/#/bhagavadgita`, { waitUntil: "domcontentloaded" });
await page.waitForSelector(".unit-scripts .w", { timeout: 30000 });

async function auditPage(PG) {
  const perPage = PER_PAGE;
  // Phase 1: click every sampled word (click toggles expansion for multi-
  // analysis forms — exactly how readers surface expanded cards/panels).
  await page.waitForTimeout(2800);
  await page.evaluate(() => {
    const pairs = [];
    document.querySelectorAll(".line").forEach((ln) => {
      const ws = [...ln.querySelectorAll(".unit-scripts .w")];
      const cs = [...ln.querySelectorAll(".parse-row .pcol")];
      ws.forEach((w, i) => cs[i] && pairs.push([w, cs[i]]));
    });
    const step = Math.max(1, Math.floor(pairs.length / 20));
    for (let i = 0; i < pairs.length; i += step) pairs[i][0].click();
  });
  await page.waitForTimeout(1200);
  return page.evaluate(() => {
    const cjkBad = /[\u4e00-\u9fff]/;
    const sanctioned = /^(另有 \d+ 解|复合词成分 Samāsa · \d+|深度解析|未裁定|仅理论存在)$/;
    const cols = [...document.querySelectorAll(".parse-row .pcol")];
    const words = [...document.querySelectorAll(".unit-scripts .w")];
    // pair by index within each line
    const pairs = [];
    document.querySelectorAll(".line").forEach((ln) => {
      const ws = [...ln.querySelectorAll(".unit-scripts .w")];
      const cs = [...ln.querySelectorAll(".parse-row .pcol")];
      ws.forEach((w, i) => cs[i] && pairs.push([w, cs[i]]));
    });
    const step = Math.max(1, Math.floor(pairs.length / 20));
    const dev = [];
    const sample = [];
    let checked = 0;
    for (let i = 0; i < pairs.length && checked < 20; i += step) {
      const [wEl, col] = pairs[i];
      checked++;
      const orig = wEl.getAttribute("data-orig") ?? "";
      const rec = { tok: wEl.textContent?.trim(), orig, devs: [] };
      const cards = col.querySelectorAll(".pcard").length;
      const merged = col.querySelector(".pcard-merged");
      const segs = [...col.querySelectorAll(".cand-seg")];
      const chip = col.querySelector(".more-chip:not(.wasm-deep-btn)");
      const comp = col.querySelector(".compound");
      // A1 segments <= 4
      if (merged && segs.length > 4) rec.devs.push(`A1 segs=${segs.length}`);
      // A2 consecutive duplicate glosses
      let prevG = null;
      segs.forEach((s) => {
        const g = s.querySelector(".seg-gloss")?.textContent ?? null;
        const txt = g ? g.replace(/^—\s*/, "").trim() : null;
        if (!g) return; // removed cell ok
        if (txt === "") rec.devs.push("A1b empty gloss cell");
        if (prevG && txt === prevG && txt !== "") rec.devs.push("A2 dup gloss");
        prevG = txt;
      });
      // A3 unsanctioned CJK anywhere in column
      col.querySelectorAll("*").forEach((n) => {
        if (n.children.length && n.tagName !== "BUTTON") return;
        const t = (n.textContent ?? "").trim();
        if (t && cjkBad.test(t) && !sanctioned.test(t)) rec.devs.push(`A3 CJK ${t.slice(0, 20)}`);
      });
      // A5 zero analyses -> no card
      if (cards === 0) {
        const deep = col.querySelectorAll(".pcard, .cand-row, .noparse").length;
        if (deep > 0) rec.devs.push("A5 ghost card");
        rec.empty = true;
      }
      // A6 homonym digit in displayed lemma
      col.querySelectorAll(".lemma-iast").forEach((l) => {
        if (/\D\d$/.test(l.textContent ?? "")) rec.devs.push("A6 homonym digit");
      });
      // A7 chip math
      if (chip) {
        const m = chip.getAttribute("aria-label")?.match(/(\d+) analyses for .*; (\d+) more/);
        if (!m) rec.devs.push("A7 chip aria");
        else if (Number(m[2]) !== Number(m[1]) - segs.length) rec.devs.push(`A7 math ${m[2]}!=${m[1]}-${segs.length}`);
      }
      // A4 compound block facts
      if (comp) {
        rec.comp = {
          head: comp.querySelector(".comp-head")?.textContent ?? "?",
          members: [...comp.querySelectorAll(".comp-member")].map((r) => ({
            form: r.querySelector(".lemma-iast")?.textContent,
            hasFeats: !!r.querySelector(".comp-feats"),
            glossLen: r.querySelector(".comp-gloss")?.textContent?.length ?? 0,
          })),
        };
        const n = Number(rec.comp.head.match(/·\s*(\d+)$/)?.[1] ?? 0);
        if (!rec.comp.head.startsWith("复合词成分 Samāsa ·")) rec.devs.push("A4 header");
        else if (n !== rec.comp.members.length) rec.devs.push("A4 count");
        if (rec.comp.members.length < 2) rec.devs.push("A4 members<2");
      }
      rec.hasBlock = !!comp;
      sample.push(rec);
      dev.push(...rec.devs.map((d) => ({ tok: rec.orig, d })));
    }
    return { sampled: checked, blocks: sample.filter(s => s.hasBlock).length,
      empties: sample.filter(s => s.empty).length, deviations: dev, sample };
  }, perPage);
}

const all = [];
for (let p = 1; p <= 3; p++) {
  all.push({ ...await auditPage(p), pg: p });
  if (p < 3) {
    await page.locator(".pager button", { hasText: "Next" }).first().click();
    await page.waitForSelector(".unit-scripts .w", { timeout: 20000 });
  }
}
const fs = await import("node:fs");
fs.writeFileSync(OUT, JSON.stringify(all, null, 1));
const tot = all.reduce((a, r) => a + r.deviations.length, 0);
console.log(JSON.stringify({
  pages: all.map(r => ({ pg: r.pg, sampled: r.sampled, blocks: r.blocks, empties: r.empties, devs: r.deviations.length })),
  totalDeviations: tot,
}, null, 1));
await browser.close();
process.exit(0);
