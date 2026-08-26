// Parse-display closed-loop audit (kim/ka disaster fix) — vite :4176.
// Run: node tests/parse-audit.mjs [--json out]
//
// Pages: BhG 1–3, Lotus part01 ch1–2 range, Meghadūta sarga 1,
// Raghuvamśa opening, Rāmāyaṇa bāla sample, Dhammapada 1–20 (Pali),
// plus home lookup-box queries {kim, ka, ca, vā, rāma, deva}.
//
// HARD metrics:
//   M1 collapsed visible analysis rows per token ≤ 3
//   M2 zero duplicate (lemma+feats) rows per token column
//   M3 zero CJK chars inside parse/gloss content nodes
//      (sanctioned chrome exempt: 另有 N 解 chips, 复合词成分 heads,
//       解析 Grammar headings, wasm/vocab/morph-note chrome)
//   M4 indeclinable tokens render exactly 1 row
//   M5 visible gloss ≤ 120 chars pre-expansion (full text stays in
//      expander surfaces: panel MW section / lexicon drawer / dict-gloss)
//   M6 function words' TOP row is the particle/pronoun reading
import { chromium } from "@playwright/test";
import { writeFileSync } from "node:fs";

const BASE = process.env.BASE_URL ?? "http://localhost:4176/";
const EXE = process.env.CHROMIUM ??
  "/Users/huyan00/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium";
const OUT_JSON = "tests/out-parse-audit.json";

const NO_SW = `
  navigator.serviceWorker.register = () => new Promise(() => {});
  navigator.serviceWorker.getRegistrations = async () => [];
`;

const PAGES = [
  { name: "BhG 1–3", hash: "#/bhagavadgita?ref=3.28", work: "bhagavadgita",
    settleRef: "3.28", pali: false },
  { name: "Lotus ch1–2", hash: "#/saddharmapundarika?ref=2.50",
    work: "saddharmapundarika", settleRef: "2.50", pali: false },
  { name: "Meghadūta sarga 1", hash: "#/meghaduta?ref=20", work: "meghaduta",
    settleRef: "20", pali: false },
  { name: "Raghuvamśa opening", hash: "#/raghuvamsa", work: "raghuvamsa",
    settleRef: null, pali: false },
  { name: "Rāmāyaṇa bāla sample", hash: "#/ramayana?ref=1.5", work: "ramayana",
    settleRef: "1.5", pali: false },
  { name: "Dhammapada 1–20", hash: "#/pali/pali-dhammapada",
    work: "pali-dhammapada", settleRef: null, pali: true },
];

const LOOKUPS = [
  { q: "kim", topLemma: "kim", indecl: true },
  // ka's top reading is the inflected interrogative क (noun-class in the
  // shards) — assert lemma identity; the Prajāpati homograph ख must lose
  { q: "ka", topLemma: "ka" },
  { q: "ca", topLemma: "ca", indecl: true, exactlyOne: true },
  { q: "vā", topLemma: "vā", indecl: true },
  { q: "rāma", topLemmas: ["rāma", "rāmā"] },
  { q: "deva", topLemmas: ["deva"] },
];

/** CJK ideographs (content nodes must never carry them). */
const CJK_RE = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/;

let failures = [];
function metric(id, label, ok, detail = "") {
  console.log(`  ${ok ? "PASS" : "FAIL"} ${id} ${label}${ok ? "" : ` — ${detail}`}`);
  if (!ok) failures.push(`${id} ${label}${detail ? ` (${detail})` : ""}`);
}

const browser = await chromium.launch({ executablePath: EXE });
const report = { pages: [], lookups: [] };

/* ================= reader pages ================= */

for (const cfg of PAGES) {
  console.log(`\n=== ${cfg.name} (${cfg.hash}) ===`);
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.addInitScript(NO_SW);
  try {
    await page.goto(`${BASE}${cfg.hash}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".pcol", { state: "attached", timeout: 60000 });
    if (cfg.settleRef) {
      await page.waitForSelector(
        `[data-ref="${cfg.settleRef.replace(/"/g, '\\"')}"]`,
        { timeout: 90000 },
      ).catch(() => {});
    }
    await page.waitForTimeout(3000); // async gloss fills settle

    // ---- app-truth: which surface forms are ALL-uninflected (M4 set) ----
    const m4Set = cfg.pali ? new Set() : await page.evaluate(async (workId) => {
      const forms = new Set();
      for (const c of document.querySelectorAll(".unit-scripts .w")) {
        const w = c.dataset?.orig ?? "";
        if (w) forms.add(w);
      }
      const api = await import("/src/api.ts");
      const grp = await import("/src/group.ts");
      const morph = await api.loadMorph([...forms], workId);
      const out = new Set();
      for (const [form, parses] of morph) {
        if (parses.length && grp.allUninflected(parses)) out.add(form);
      }
      return [...out];
    }, cfg.work).catch(() => new Set());

    const stats = await page.evaluate((m4List) => {
      const m4 = new Set(m4List);
      const CJK_RE = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/;
      const SANCTIONED = ".more-chip,.comp-head,.wasm-deep-btn,.wasm-deep," +
        ".diff-badge,.morph-empty-note,.panel-vocab-btn";
      const res = {
        tokens: 0, m1Max: 0, m1Bad: [], m2Bad: [], m4Bad: [],
        m4Checked: 0, m5Bad: [], glossMax: 0, cjkBad: [],
        emptyCols: 0,
      };
      // walk text nodes; a node counts as violation only when NO ancestor
      // (up past `root`) is sanctioned chrome or a button
      const cjkScan = (root) => {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        for (let n = walker.nextNode(); n; n = walker.nextNode()) {
          const t = n.textContent;
          if (!t || !CJK_RE.test(t)) continue;
          let e2 = n.parentElement;
          let sanctioned = false;
          while (e2 && e2 !== root.parentElement) {
            if (e2.matches?.(SANCTIONED) || e2.tagName === "BUTTON") {
              sanctioned = true;
              break;
            }
            e2 = e2.parentElement;
          }
          if (!sanctioned) res.cjkBad.push(t.trim().slice(0, 40));
        }
      };
      const units = document.querySelectorAll(".line, .prose-unit");
      for (const unit of units) {
        const cells = [...unit.querySelectorAll(".unit-scripts .wcell")]
          .map((c) => c.querySelector(".w")?.dataset.orig ?? "");
        const cols = [...unit.querySelectorAll(".parse-row > .pcol")];
        if (cells.length !== cols.length) continue; // speaker-labeled unit
        for (let i = 0; i < cols.length; i++) {
          const col = cols[i];
          res.tokens += 1;
          // M1: visible analysis card rows (compound box/wasm/chips excluded
          // by class: compound=div.compound, chip=button.more-chip)
          const rows = [...col.children].filter((c) =>
            c.classList.contains("pcard") && !c.classList.contains("wasm-deep"));
          if (rows.length === 0) {
            res.emptyCols += 1;
            continue; // honesty gate / no coverage
          }
          if (rows.length > res.m1Max) res.m1Max = rows.length;
          if (rows.length > 3) {
            res.m1Bad.push(`${cells[i]}:${rows.length}:${rows[0]?.textContent.slice(0, 30)}`);
          }
          // M2: duplicate (lemma + feats-summary) rows
          const seen = new Set();
          for (const r of rows) {
            const lem = r.querySelector(".lemma-iast")?.textContent ?? "?";
            const ft = r.querySelector(".feats")?.textContent?.trim() ?? "";
            const k = `${lem}|${ft}`;
            if (seen.has(k)) res.m2Bad.push(`${cells[i]}:${k}`);
            seen.add(k);
          }
          // M4: all-uninflected tokens must show EXACTLY one row
          if (m4.has(cells[i])) {
            res.m4Checked += 1;
            if (rows.length !== 1) {
              res.m4Bad.push(`${cells[i]}:${rows.length}`);
            }
          }
          // M5: visible clipped glosses ≤120 chars (+ellipsis tolerance)
          for (const g of col.querySelectorAll(".mw-gloss, .seg-gloss")) {
            const t = g.textContent ?? "";
            if (!t.trim()) continue;
            res.glossMax = Math.max(res.glossMax, t.trim().length);
            if (t.trim().length > 121) res.m5Bad.push(`${cells[i]}:${t.slice(0, 50)}`);
          }
          cjkScan(col);
        }
      }
      // panel sweep if open (opened separately by the driver)
      const panel = document.querySelector(".side-panel:not(.hidden) .panel-body");
      if (panel) {
        for (const g of panel.querySelectorAll(".entry .mw-gloss")) {
          const t = (g.textContent ?? "").trim();
          if (t.length > 121) res.m5Bad.push(`panel:${t.slice(0, 50)}`);
        }
        cjkScan(panel);
      }
      return res;
    }, [...m4Set]).catch((e) => ({ error: String(e) }));

    if (stats.error) {
      metric(cfg.name, "evaluate", false, stats.error);
      report.pages.push({ name: cfg.name, error: stats.error });
      await ctx.close();
      continue;
    }

    metric("M1", `${cfg.name} rows≤3 (max ${stats.m1Max}, tokens ${stats.tokens})`,
      stats.m1Bad.length === 0, JSON.stringify(stats.m1Bad.slice(0, 3)));
    metric("M2", `${cfg.name} no duplicate rows`, stats.m2Bad.length === 0,
      JSON.stringify(stats.m2Bad.slice(0, 3)));
    metric("M3", `${cfg.name} no CJK in content`, stats.cjkBad.length === 0,
      JSON.stringify(stats.cjkBad.slice(0, 3)));
    metric("M4", `${cfg.name} indecl tokens == 1 row (checked ${stats.m4Checked})`,
      stats.m4Bad.length === 0,
      JSON.stringify(stats.m4Bad.slice(0, 3)));

    // ---- expanded spot-check (chip round-trip, ≤2 tokens/page) ----
    // NOTE: use STABLE element handles — index locators re-resolve against
    // the live DOM, and after one expansion the "first chip column" can be
    // a different token entirely.
    let expOk = true;
    let expDetail = "";
    let expSampled = 0;
    {
      const chipHandles = await page
        .locator(".parse-row > .pcol .more-chip").elementHandles();
      const pickedRefs = new Set();
      for (const h of chipHandles) {
        if (expSampled >= 2) break;
        const meta = await h.evaluate((c) => {
          const col = c.closest(".pcol");
          const unit = c.closest(".line, .prose-unit");
          return {
            ref: unit?.dataset?.ref ?? String(
              [...unit?.parentElement?.children ?? []].indexOf(unit ?? new Element())),
            rows: col ? col.querySelectorAll(":scope > .pcard").length : -1,
          };
        }).catch(() => null);
        if (!meta || pickedRefs.has(meta.ref)) continue;
        pickedRefs.add(meta.ref);
        expSampled += 1;
        const colHandle = await h.evaluateHandle((c) => c.closest(".pcol"));
        const before = meta.rows;
        await h.click();
        await page.waitForTimeout(300);
        const after = await colHandle.evaluate((c) =>
          c.querySelectorAll(":scope > .pcard").length);
        if (after <= before) {
          expOk = false;
          expDetail += ` expand ${before}->${after};`;
        }
        const dups = await colHandle.evaluate((c) => {
          const seen = new Set();
          let d = 0;
          for (const r of c.querySelectorAll(":scope > .pcard")) {
            const k2 = (r.querySelector(".lemma-iast")?.textContent ?? "?") +
              "|" + (r.querySelector(".feats")?.textContent?.trim() ?? "");
            if (seen.has(k2)) d += 1;
            seen.add(k2);
          }
          return d;
        });
        if (dups > 0) {
          expOk = false;
          expDetail += ` dupExpanded=${dups};`;
        }
      }
      await page.keyboard.press("e"); // collapse-all back
      await page.waitForTimeout(200);
    }
    metric("EXP", `${cfg.name} chip expands to MORE group rows, no dups` +
      (expSampled ? ` (${expSampled} sampled)` : " (no overflow on page)"),
      expOk, expDetail);

    // ---- word-click panel spot-check (first page token with many rows) ----
    if (cfg.work === "bhagavadgita") {
      const panelInfo = await clickKimAndReadPanel(page);
      if (panelInfo) {
        metric("PANEL", `${cfg.name} किम् panel grouped (entries ${panelInfo.entries})`,
          panelInfo.entries > 0 && panelInfo.entries <= 12 &&
            panelInfo.dupKeys === 0 && panelInfo.longGloss === 0,
          `dups=${panelInfo.dupKeys} longGloss=${panelInfo.longGloss}`);
      } else {
        metric("PANEL", `${cfg.name} किम् panel opened`, false, "panel did not open");
      }
    }

    report.pages.push({ name: cfg.name, ...stats, m1Bad: stats.m1Bad.length,
      m2BadCount: stats.m2Bad.length });
  } finally {
    await ctx.close();
  }
}

/** Open the किम् panel on BhG 1.1 and read grouped-entry stats. */
async function clickKimAndReadPanel(page) {
  try {
    const cell = page.locator('[data-ref="1.1"] .unit-scripts .wcell')
      .filter({ has: page.locator('.w[data-orig="किम्"], .w[data-orig="किं"]') })
      .first();
    await cell.locator(".w").first().click();
    await page.waitForSelector(".side-panel:not(.hidden)", { timeout: 5000 });
    await page.waitForTimeout(1200);
    return await page.evaluate(() => {
      const body = document.querySelector(".side-panel .panel-body");
      const entries = [...body.querySelectorAll(".entry")];
      const seen = new Set();
      let dupKeys = 0;
      let longGloss = 0;
      for (const e of entries) {
        const lem = e.querySelector(".lemma-iast")?.textContent ?? "?";
        const ft = e.querySelector(".feats")?.textContent?.trim() ?? "";
        const k = `${lem}|${ft}`;
        if (seen.has(k)) dupKeys += 1;
        seen.add(k);
        const gl = e.querySelector(".mw-gloss");
        if (gl && (gl.textContent ?? "").trim().length > 121) longGloss += 1;
      }
      return { entries: entries.length, dupKeys, longGloss };
    });
  } catch {
    return null;
  }
}

/* ================= home lookup box ================= */

console.log("\n=== lookup box ===");
{
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.addInitScript(NO_SW);
  try {
    await page.goto(`${BASE}#/`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".wl-input", { timeout: 30000 });
    for (const spec of LOOKUPS) {
      await page.fill(".wl-input", "");
      await page.fill(".wl-input", spec.q);
      await page.waitForTimeout(1800);
      const r = await page.evaluate(() => {
        const res = document.querySelector(".wl-results");
        const head = res?.querySelector("h3.wl-head")?.textContent ?? "";
        const cards = [...(res?.querySelectorAll(":scope > .pcard.wl-card") ?? [])];
        const seen = new Set();
        let dups = 0;
        let maxGloss = 0;
        for (const c of cards) {
          const lem = c.querySelector(".lemma-iast")?.textContent ?? "?";
          const ft = c.querySelector(".feats")?.textContent?.trim() ?? "";
          const k = `${lem}|${ft}`;
          if (seen.has(k)) dups += 1;
          seen.add(k);
          const gl = c.querySelector(".mw-gloss");
          if (gl) maxGloss = Math.max(maxGloss, (gl.textContent ?? "").trim().length);
        }
        const first = cards[0];
        return {
          header: head,
          nCards: cards.length,
          dups,
          maxGloss,
          firstLemma: first?.querySelector(".lemma-iast")?.textContent ?? "",
          firstIndecl: !!first &&
            [...first.querySelectorAll(".feat-tag")]
              .some((t) => t.textContent === "indecl."),
        };
      });
      const m = `lookup “${spec.q}”`;
      metric("M1", `${m} cards≤3 collapsed (got ${r.nCards})`,
        r.nCards >= 0 && r.nCards <= 3, `n=${r.nCards}`);
      metric("M2", `${m} no duplicate cards`, r.dups === 0, `dups=${r.dups}`);
      metric("M5", `${m} gloss≤121 (max ${r.maxGloss})`, r.maxGloss <= 121);
      if (spec.exactlyOne) {
        metric("M4", `${m} renders exactly ONE reading row`, r.nCards === 1,
          `n=${r.nCards}`);
      }
      if (spec.topLemma) {
        const okTop = r.firstLemma === spec.topLemma &&
          (!spec.indecl || r.firstIndecl);
        metric("M6", `${m} TOP row = ${spec.topLemma} reading` +
          ` (got "${r.firstLemma}" indecl=${r.firstIndecl})`, okTop);
      } else if (spec.topLemmas) {
        metric("M6", `${m} TOP row = core nominal reading (got "${r.firstLemma}")`,
          spec.topLemmas.includes(r.firstLemma));
      }
      // expansion round-trip
      const chip = page.locator(".wl-results .more-chip");
      if (await chip.count()) {
        const want = parseInt((r.header.match(/·\s*(\d+)/) ?? [])[1] ?? "-1", 10);
        await chip.first().click();
        await page.waitForTimeout(400);
        const after = await page.evaluate(() =>
          document.querySelectorAll(".wl-results > .pcard.wl-card").length);
        metric("EXP", `${m} expands to all ${want} readings (got ${after})`,
          after === want);
      }
      report.lookups.push({ q: spec.q, ...r });
    }
  } finally {
    await ctx.close();
  }
}

await browser.close();

writeFileSync(OUT_JSON, JSON.stringify(report, null, 2));
console.log(`\nreport -> ${OUT_JSON}`);
if (failures.length) {
  console.log(`\nAUDIT RED — ${failures.length} failing checks:`);
  for (const f of failures) console.log(`  ✗ ${f}`);
  process.exit(1);
}
console.log("\nALL METRICS GREEN");
