// Home full-text search parity verification (greek-reader depth port).
// Run: node tests/search-parity.mjs [--json out]   (vite :4176 live)
//
// Checks:
//   P1 dual-script: 'rāma' and 'राम' return the SAME work-hit set
//      (house-mandatory IAST ⇄ Devanagari parity)
//   P2 sandhi variant probe: 'रामः' (visarga form) still resolves
//   P3 translation snippets: section renders with <mark> highlight
//   P4 Pali corpus searchable from the word index (roman keys)
//   P5 title filter regression: zh + IAST title search unchanged
//   P6 pali toggle view unaffected (#/pali/ home renders)
//   B  latency benchmarks (5 queries, ms from keystroke to settled DOM;
//      first hit includes its shard/index network load — reported as cold)
import { chromium } from "@playwright/test";
import { writeFileSync } from "node:fs";

const OUT_JSON = process.argv.includes("--json")
  ? process.argv[process.argv.indexOf("--json") + 1]
  : null;
const BASE = process.env.BASE_URL ?? "http://localhost:4176/";
const NO_SW = `
  navigator.serviceWorker.register = () => new Promise(() => {});
  navigator.serviceWorker.getRegistrations = async () => [];
`;
const EXE = process.env.CHROMIUM ??
  "/Users/huyan00/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium";

const errors = [];
let failed = 0;
function check(name, cond, detail = "") {
  const ok = !!cond;
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${!ok && detail ? ` — ${detail}` : ""}`);
}

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext();
await ctx.addInitScript(NO_SW);
const page = await ctx.newPage();
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => {
  if (m.type() === "error") errors.push(`console: ${m.text()}`);
});

/** Type into the home search and resolve when a result head naming the
 *  query appears ("…containing “q”"), or timeout. Returns renderMs =
 *  keystroke -> results rendered (incl. 60ms debounce + index fetches),
 *  plus which sections matched. */
async function searchAndSettle(q, timeout = 10000) {
  return page.evaluate(async ({ q, timeout }) => {
    const input = document.querySelector("input[type=search]");
    input.focus();
    input.value = "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 250));
    const t0 = performance.now();
    let renderMs = 0;
    input.value = q;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    const needle = `\u201c${q}\u201d`;
    for (;;) {
      await new Promise((r) => setTimeout(r, 30));
      const sa = document.querySelector(".sa-hits .text-hits-head")
        ?.textContent ?? "";
      const tr = document.querySelector(
        ".text-hits:not(.sa-hits) .text-hits-head")?.textContent ?? "";
      if (!renderMs && (sa.includes(needle) || tr.includes(needle))) {
        renderMs = Math.round(performance.now() - t0);
        break;
      }
      if (performance.now() - t0 > timeout) break;
    }
    const sa = document.querySelector(".sa-hits .text-hits-head")
      ?.textContent ?? "";
    const tr = document.querySelector(
      ".text-hits:not(.sa-hits) .text-hits-head")?.textContent ?? "";
    return {
      renderMs,
      saHit: sa.includes(needle),
      transHit: tr.includes(needle),
      settle: Math.round(performance.now() - t0),
    };
  }, { q, timeout });
}

async function saHitHrefs() {
  return page.$$eval(".sa-hits a.text-hit", (as) =>
    as.map((a) => ({ href: a.getAttribute("href"),
                     title: a.querySelector(".hit-title")?.textContent })));
}

await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForSelector(".work-link");

// ---- P1 dual-script parity ----
const r1 = await searchAndSettle("rāma");
const iastHits = await saHitHrefs();
check("P1a 'rāma' yields Sanskrit/Pali text hits", r1.saHit &&
    iastHits.length >= 3,
  `got ${iastHits.length}: ${JSON.stringify(iastHits.slice(0, 3))}`);

const r2 = await searchAndSettle("राम");
const devaHits = await saHitHrefs();
check("P1b 'राम' same work set as 'rāma'", r2.saHit &&
    JSON.stringify(devaHits) === JSON.stringify(iastHits),
  `iast=${JSON.stringify(iastHits)} deva=${JSON.stringify(devaHits)}`);

// ---- P2 sandhi variant ----
const r3 = await searchAndSettle("रामः");
const visargaHits = await saHitHrefs();
check("P2 'रामः' resolves via visarga-folded variant", r3.saHit &&
  visargaHits.length >= 1 &&
  visargaHits.some((h) => h.href === "#/ramayana"),
  JSON.stringify(visargaHits.slice(0, 3)));

// ---- P3 translation snippet hits with <mark> highlight ----
const r4 = await searchAndSettle("kurukshetra");
await page.waitForTimeout(250);
const markCount = await page.locator(".text-hits:not(.sa-hits) mark").count();
check("P3 translation hits render with highlighted <mark> span",
  r4.transHit && markCount >= 1, `marks=${markCount}`);
const transHead = await page
  .locator(".text-hits:not(.sa-hits) .text-hits-head")
  .textContent()
  .catch(() => "");
check("P3b translations head names the corpus",
  /In translations: \d+ passages? containing/.test(transHead ?? ""),
  transHead ?? "(none)");

// ---- P4 Pali reachable ----
const r5 = await searchAndSettle("padam");
const padamHrefs = (await saHitHrefs()).map((h) => h.href);
check("P4 Pali work appears in word-index hits", r5.saHit &&
  padamHrefs.some((h) => h.startsWith("#/pali/")),
  JSON.stringify(padamHrefs.slice(0, 5)));

// ---- P5 title filter regressions (count line only — catalog filter) ----
await searchAndSettle("meghaduta");
const meghaVisible = await page
  .locator("a.work-link[href='#/meghaduta']:not([hidden])")
  .count();
check("P5a title search 'meghaduta' still filters catalog",
  meghaVisible === 1, `visible=${meghaVisible}`);
await searchAndSettle("鸠摩罗");
const kumZh = await page
  .locator("a.work-link[href='#/kumarasambhava']:not([hidden])")
  .count();
check("P5b zh title search '鸠摩罗' still finds Kumārasaṃbhava card",
  kumZh === 1, `visible=${kumZh}`);

// ---- P6 pali toggle unaffected ----
await page.goto(`${BASE}#/pali/`, { waitUntil: "networkidle" });
await page.waitForSelector(".work-link");
const paliLinks = await page.locator(".work-link").count();
const toggleOk = await page.locator(".lang-toggle .lang-btn").count();
check("P6 pali home renders with toggle intact",
  paliLinks >= 20 && toggleOk === 2, `links=${paliLinks} btns=${toggleOk}`);
const r6 = await searchAndSettle("dhammo");
const paliSectionHits = await saHitHrefs();
check("P6b word search works on pali home too", r6.saHit &&
  paliSectionHits.length >= 3, JSON.stringify(paliSectionHits.slice(0, 2)));

// ---- B benchmarks (fresh context for an honest COLD first query) ----
const ctx2 = await browser.newContext();
await ctx2.addInitScript(NO_SW);
const page2 = await ctx2.newPage();
await page2.goto(BASE, { waitUntil: "networkidle" });
await page2.waitForSelector(".work-link");
const benchPage = page2;
const bench = [];
async function benchQuery(label, q, cold) {
  const r = await benchPage.evaluate(async ({ q, timeout }) => {
    const input = document.querySelector("input[type=search]");
    input.focus();
    input.value = "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 250));
    const t0 = performance.now();
    let renderMs = 0;
    input.value = q;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    const needle = `\u201c${q}\u201d`;
    for (;;) {
      await new Promise((r) => setTimeout(r, 30));
      const sa = document.querySelector(".sa-hits .text-hits-head")
        ?.textContent ?? "";
      const tr = document.querySelector(
        ".text-hits:not(.sa-hits) .text-hits-head")?.textContent ?? "";
      if (!renderMs && (sa.includes(needle) || tr.includes(needle))) {
        renderMs = Math.round(performance.now() - t0);
        break;
      }
      if (performance.now() - t0 > timeout) break;
    }
    return renderMs;
  }, { q, timeout: 15000 });
  bench.push({ q, label, cold, ms: r });
  console.log(`BENCH ${cold ? "cold" : "warm"}  ${q}  ${r}ms`);
}
await benchQuery("word-index first shard load", "rāma", true);       // r.json
await benchQuery("dual-script re-query", "राम", false);
await benchQuery("second letter shard", "धर्मक्षेत्रे", true);         // d.json
await benchQuery("same-shard warm probe", "dhammo", false);
await benchQuery("translation index first load", "arjuna", true);    // 4.6MB

const out = {
  when: new Date().toISOString(),
  base: BASE,
  checks_failed: failed,
  iast_rama_hits: iastHits,
  benchmarks: bench,
};
if (OUT_JSON) writeFileSync(OUT_JSON, JSON.stringify(out, null, 2));

await ctx.close();
await ctx2.close();
await browser.close();
check("ZERO console/page errors", errors.length === 0,
  errors.slice(0, 5).join(" | "));
console.log(failed === 0 ? "\nALL CHECKS PASSED"
  : `\n${failed} CHECK(S) FAILED`);
process.exit(failed === 0 ? 0 : 1);
