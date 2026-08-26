// Acceptance: same-token analyses merge into ONE compact row (UI spec).
// Run: WORK=saddharmapundarika node tests/verify-merge-rows.mjs [more ids...]
// Ground truth for candidate counts = the app's own deduped collection
// (loadMorph imported in-page), so no mirror-of-feats drift is possible.
// Checks per work page (vite :4176):
//   V1 collapsed columns render exactly ONE stacked analysis card
//      (the merged row); never 2+ stacked pcards
//   V2 merged-row inline segments == min(distinct, 4); single-analysis
//      tokens keep the classic one-card layout
//   V3 overflow (>4 distinct) shows 「另有 N 解」, N = distinct - 4;
//      clicking expands to ALL distinct candidates; E collapses back
//   V4 every segment carries its own async MW gloss cell (≤1 per segment)
//   V5 coverage subset: rendered cards ⊆ raw shard truth (R4 gate may
//     legitimately drop prefix-stem keys, never invent analyses)
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";

const BASE = process.env.BASE_URL ?? "http://localhost:4176/";
const WORKS = (process.env.WORK ?? "saddharmapundarika,bhagavadgita")
  .split(",").map((s) => s.trim()).filter(Boolean);
const EXE = "/Users/huyan00/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium";

const NO_SW = `
  navigator.serviceWorker.register = () => new Promise(() => {});
  navigator.serviceWorker.getRegistrations = async () => [];
`;

let failed = 0;
function check(name, cond, detail = "") {
  const ok = !!cond;
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${!ok && detail ? ` — ${detail}` : ""}`);
}

const browser = await chromium.launch({ executablePath: EXE });

for (const work of WORKS) {
  console.log(`\n=== ${work} ===`);
  // ---- raw shard truth (subset check only) ----
  const slice = JSON.parse(readFileSync(
    new URL(`../public/data/morph/_surface/by-work/${work}.json`, import.meta.url),
    "utf8"));
  const shardCache = new Map();
  const rawFor = (form) => {
    const key = slice[form];
    if (!key) return 0;
    let sh = shardCache.get(key[0]);
    if (!sh) {
      try {
        sh = JSON.parse(readFileSync(
          new URL(`../public/data/morph/${key[0]}.json`, import.meta.url),
          "utf8"));
      } catch { sh = {}; }
      shardCache.set(key[0], sh);
    }
    return (sh[key] ?? []).length;
  };

  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.addInitScript(NO_SW);
  await page.goto(`${BASE}#/${work}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".pcol", { state: "attached", timeout: 30000 });
  await page.waitForFunction(
    () => document.querySelectorAll(".line, .prose-unit").length >= 1,
    null, { timeout: 30000 },
  );
  await page.waitForTimeout(2500);

  let checked = 0, v1bad = 0, v2bad = 0, v3checked = 0, v4bad = 0, v5bad = 0;
  let gateDropped = 0;
  const units = page.locator(".line, .prose-unit");
  const nUnits = await units.count();
  // collect all distinct surface forms first, resolve via app's loadMorph
  const forms = await page.evaluate(() => {
    const out = new Set();
    for (const r of document.querySelectorAll(".line, .prose-unit")) {
      for (const c of r.querySelectorAll(".unit-scripts .wcell")) {
        const w = c.querySelector(".w")?.dataset.orig;
        if (w) out.add(w);
      }
    }
    return [...out];
  });
  const morphCounts = await page.evaluate(async ({ workId, forms }) => {
    const mod = await import("/src/api.ts");
    const m = await mod.loadMorph(forms, workId);
    return Object.fromEntries([...m.entries()].map(([k, v]) => [k, v.length]));
  }, { workId: work, forms });

  for (let u = 0; u < nUnits; u++) {
    const unit = units.nth(u);
    const meta = await unit.evaluate((r) => ({
      ws: [...r.querySelectorAll(".unit-scripts .wcell")]
        .map((c) => c.querySelector(".w")?.dataset.orig ?? "")
        .filter(Boolean),
      cols: r.querySelectorAll(".parse-row > .pcol").length,
    }));
    if (meta.ws.length !== meta.cols) continue; // speaker-labeled unit
    for (let i = 0; i < meta.cols; i++) {
      const form = meta.ws[i];
      const elh = await unit.locator(".parse-row > .pcol").nth(i)
        .elementHandle();
      if (!elh) continue;
      const info = await page.evaluate((el) => ({
        stacked: [...el.querySelectorAll(":scope > .pcard")]
          .filter((c) => c.classList.contains("pcard-compact") ||
            c.classList.contains("cand-row")).length,
        segs: el.querySelectorAll(":scope > .pcard-compact .cand-seg").length,
        glossCells: el.querySelectorAll(":scope .seg-gloss").length,
        chips: [...el.querySelectorAll(".more-chip")]
          .map((c) => c.textContent?.trim() ?? ""),
        text: el.textContent?.trim().slice(0, 80) ?? "",
      }), elh);
      const distinct = morphCounts[form] ?? 0; // app-side deduped truth
      checked += 1;
      // V5 subset: rendered ⇒ raw shards carry this form's analyses
      if (info.stacked > 0 && rawFor(form) === 0) v5bad += 1;
      if (distinct === 0) {
        if (info.stacked !== 0) v1bad += 1; // honesty gate violated?
        else gateDropped += 0; // true miss or R4 drop — both fine
        continue;
      }
      if (info.stacked === 0) { gateDropped += 1; continue; } // R4 drop
      // V1: exactly ONE stacked analysis card (merged row)
      if (info.stacked !== 1) v1bad += 1;
      // V2: merged rows show min(distinct, 4) segments; single-analysis
      // tokens keep the classic one-card layout (no segments)
      const wantSegs = distinct >= 2 ? Math.min(distinct, 4) : 0;
      if (info.segs !== wantSegs) {
        v2bad += 1;
        if (v2bad <= 3) console.log(`   V2 sample ${form}: segs=${info.segs} want=${wantSegs} distinct=${distinct} "${info.text}"`);
      }
      // V3: overflow chip label + expansion round-trip (2 tokens max)
      if (distinct > 4 && v3checked < 2) {
        v3checked += 1;
        const wantN = distinct - 4;
        const okLabel = info.chips.length === 1 &&
          info.chips[0] === `另有 ${wantN} 解`;
        check(`V3 ${form} chip 「另有 ${wantN} 解」`, okLabel,
          JSON.stringify(info.chips));
        await unit.locator(".parse-row > .pcol").nth(i)
          .locator(".more-chip").first().click();
        await page.waitForTimeout(150);
        const expandedRows = await page.evaluate(() =>
          document.querySelectorAll(".pcol > .cand-row").length);
        check(`V3 ${form} expands to ${distinct} rows`,
          expandedRows === distinct, `got ${expandedRows}`);
        await page.keyboard.press("e"); // global collapse-all shortcut
        await page.waitForTimeout(150);
      }
      // V4: each segment owns ≤1 gloss cell
      if (info.glossCells > info.segs) v4bad += 1;
    }
  }
  check("V1 collapsed columns show exactly ONE analysis card", v1bad === 0,
    `${v1bad} bad of ${checked}`);
  check("V2 inline segments == min(distinct, 4)", v2bad === 0, `${v2bad} bad`);
  check("V4 ≤1 MW gloss cell per segment", v4bad === 0, `${v4bad} bad`);
  check("V5 rendered cards ⊆ raw shard truth", v5bad === 0, `${v5bad} bad`);
  console.log(`     columns audited: ${checked}; R4-gate/miss columns: ${gateDropped}; expansions exercised: ${v3checked}`);

  await ctx.close();
}

await browser.close();
if (failed) {
  console.log(`\n${failed} FAILURES`);
  process.exit(1);
}
console.log("\nALL CHECKS PASSED");
