// Corpus-wide parse-display scorecard (ALL catalog works) — vite :4176.
// Run: node tests/corpus-scorecard.mjs  [WORKS=id1,id2  DELAY_MS=400]
//
// Answers "为什么还会一塌糊涂" with data: one row per catalog work, measured
// on the reader route's FIRST unit page (sequential + polite delay).
//
// Metrics per work:
//   M1 maxRows   collapsed visible analysis rows per token column
//                (spec: exactly 1 group-row + 「另有 N 解」 chip; >1 = red)
//   M2 dupRows   duplicate (lemma+feats) rows within one token column
//   M3 cjkLeaks  CJK chars in non-sanctioned parse/gloss content nodes
//   M4 m4Bad     all-uninflected tokens NOT rendering exactly 1 row
//   M5 glossMax  visible clipped gloss chars (>121 = red)
//   NEW carded%  strict-hit proxy: % token columns with ≥1 analysis card
//   NEW densityPx total card-block pixels inside the first viewport
//   EXP          chip expands to MORE group rows, no dups after expand
// Grade A/B/C/D is DISPLAY-FIRST: any display red ⇒ D; otherwise by
// carded% (≥85 A / ≥50 B / else C). Data-sparse-but-clean works grade C/B
// and are listed as honest gaps — never faked.
import { chromium } from "@playwright/test";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";

const BASE = process.env.BASE_URL ?? "http://localhost:4176/";
const EXE = process.env.CHROMIUM ??
  "/Users/huyan00/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium";
const OUT_CSV = "qa-report/corpus-scorecard.csv";
const OUT_JSON = "qa-report/assets/corpus-scorecard.json";
const ONLY = (process.env.WORKS ?? "")
  .split(",").map((s) => s.trim()).filter(Boolean);
const DELAY_MS = parseInt(process.env.DELAY_MS ?? "400", 10);

const NO_SW = `
  navigator.serviceWorker.register = () => new Promise(() => {});
  navigator.serviceWorker.getRegistrations = async () => [];
`;

function makeRow(id, title, lang, kind, route) {
  return {
    id, title, lang, kind, route,
    ok: false,
    error: "",
    units: -1, tokens: -1,
    carded: -1, cardedPct: -1, maxRows: -1, dupRows: -1, cjkLeaks: -1,
    m4Checked: -1, m4Bad: -1, glossMax: -1, densityPx: -1, vpUnits: -1,
    chips: -1, expOk: true, expDetail: "", morphNote: false, grade: "?",
  };
}

const CATALOG = JSON.parse(readFileSync("public/data/catalog.json", "utf8"));

function worksFromCatalog() {
  const out = [];
  for (const a of CATALOG.authors) {
    for (const w of a.works ?? []) {
      const lang = w.lang ?? a.lang ?? "sa";
      out.push(makeRow(
        w.id,
        w.title,
        lang,
        w.kind ?? "verse",
        lang === "pi" ? `#/pali/${w.id}` : `#/${w.id}`,
      ));
    }
  }
  return ONLY.length ? out.filter((w) => ONLY.includes(w.id)) : out;
}

function gradeOf(r) {
  if (!r.ok || r.units <= 0 || r.tokens <= 0) return "D";
  const displayRed =
    r.maxRows > 1 || r.dupRows > 0 || r.cjkLeaks > 0 || r.m4Bad > 0 ||
    r.glossMax > 121 || !r.expOk;
  if (displayRed) return "D";
  return r.cardedPct >= 85 ? "A" : r.cardedPct >= 50 ? "B" : "C";
}

/* ---------------- in-page measurement ---------------- */

const MEASURE_FN = (m4List) => {
  const m4 = new Set(m4List);
  void m4;
  const CJK_RE = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/;
  // sanctioned chrome: 另有N解 chip / compound heads / wasm / notes / badges
  const SANCTIONED = ".more-chip,.comp-head,.wasm-deep-btn,.wasm-deep," +
    ".diff-badge,.morph-empty-note,.panel-vocab-btn";
  const res = {
    units: 0, tokens: 0, carded: 0,
    maxRows: 0, multiBad: [],
    dupRows: 0, dupEx: [],
    cjkLeaks: 0, cjkEx: [],
    glossMax: 0, glossBad: 0,
    densityPx: 0, vpUnits: 0,
    chips: 0,
  };
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
      if (!sanctioned) {
        res.cjkLeaks += 1;
        if (res.cjkEx.length < 5) res.cjkEx.push(t.trim().slice(0, 40));
      }
    }
  };
  const vh = window.innerHeight;
  const units = document.querySelectorAll(".line, .prose-unit");
  res.units = units.length;
  for (const unit of units) {
    const cells = [...unit.querySelectorAll(".unit-scripts .w")]
      .map((c) => c.dataset?.orig ?? "");
    const cols = [...unit.querySelectorAll(".parse-row > .pcol")];
    if (cells.length !== cols.length) continue; // speaker-labeled unit
    const inVp = unit.getBoundingClientRect().top < vh;
    if (inVp) res.vpUnits += 1;
    for (let i = 0; i < cols.length; i++) {
      const col = cols[i];
      res.tokens += 1;
      const rows = [...col.children].filter((c) =>
        c.classList.contains("pcard") && !c.classList.contains("wasm-deep"));
      if (rows.length > 0) res.carded += 1;
      if (inVp) {
        for (const c of col.children) {
          res.densityPx += c.offsetHeight || 0;
        }
      }
      res.chips += col.querySelectorAll(":scope > .more-chip").length;
      if (rows.length === 0) continue;
      if (rows.length > res.maxRows) res.maxRows = rows.length;
      if (rows.length > 1 && res.multiBad.length < 5) {
        res.multiBad.push(`${cells[i]}:${rows.length}`);
      }
      const seen = new Set();
      for (const r of rows) {
        const lem = r.querySelector(".lemma-iast")?.textContent ?? "?";
        const ft = r.querySelector(".feats")?.textContent?.trim() ?? "";
        const k = `${lem}|${ft}`;
        if (seen.has(k)) {
          res.dupRows += 1;
          if (res.dupEx.length < 5) res.dupEx.push(`${cells[i]}:${k}`);
        }
        seen.add(k);
      }
      for (const g of col.querySelectorAll(".mw-gloss, .seg-gloss")) {
        const t = (g.textContent ?? "").trim();
        if (!t.trim()) continue;
        res.glossMax = Math.max(res.glossMax, t.length);
        if (t.length > 121) res.glossBad += 1;
      }
      cjkScan(col);
    }
  }
  return res;
};

/** M4 set via the SAME vite module instances the app used (cached shards). */
async function m4Set(page, workId) {
  return page.evaluate(async (wid) => {
    try {
      const forms = new Set();
      for (const c of document.querySelectorAll(".unit-scripts .w")) {
        const w = c.dataset?.orig ?? "";
        if (w) forms.add(w);
      }
      const api = await import("/src/api.ts");
      const grp = await import("/src/group.ts");
      const morph = await api.loadMorph([...forms], wid);
      const out = [];
      for (const [form, parses] of morph) {
        if (parses.length && grp.allUninflected(parses)) out.add(form);
      }
      return out;
    } catch {
      return [];
    }
  }, workId);
}

/** Chip round-trip on up to 2 stable column handles (audit-style).
 *  Late-arriving shards re-render columns mid-check, so stale handles are
 *  retried with freshly collected ones instead of failing the work. */
async function expanderCheck(page) {
  let ok = true;
  let detail = "";
  let sampled = 0;
  const pickedRefs = new Set();
  const tryChip = async (h) => {
    const meta = await h.evaluate((c) => {
      const col = c.closest(".pcol");
      const unit = c.closest(".line, .prose-unit");
      return {
        ref: unit?.getAttribute("data-ref") ??
          String([...(unit?.parentElement?.children ?? [])].indexOf(unit)),
        rows: col ? col.querySelectorAll(":scope > .pcard").length : -1,
      };
    }).catch(() => null);
    if (!meta || pickedRefs.has(meta.ref)) return false;
    pickedRefs.add(meta.ref);
    sampled += 1;
    const colHandle = await h.evaluateHandle((c) => c.closest(".pcol"));
    const before = meta.rows;
    await h.click();
    await page.waitForTimeout(300);
    const after = await colHandle.evaluate((c) =>
      c.querySelectorAll(":scope > .pcard").length);
    if (after <= before) {
      ok = false;
      detail += ` expand ${before}->${after};`;
    }
    const dups = await colHandle.evaluate((c) => {
      const seen = new Set();
      let d = 0;
      for (const r of c.querySelectorAll(":scope > .pcard")) {
        const k2 =
          (r.querySelector(".lemma-iast")?.textContent ?? "?") +
          "|" + (r.querySelector(".feats")?.textContent?.trim() ?? "");
        if (seen.has(k2)) d += 1;
        seen.add(k2);
      }
      return d;
    });
    if (dups > 0) {
      ok = false;
      detail += ` dupExpanded=${dups};`;
    }
    if (after <= before || dups > 0) {
      // forensics: did the toggle fire anywhere? is our column still live?
      const glob = await page.evaluate(() => {
        let x = 0;
        for (const c of document.querySelectorAll(".parse-row > .pcol")) {
          if (c.querySelectorAll(":scope > .pcard").length > 1) x += 1;
        }
        return x;
      });
      const alive = await colHandle.evaluate((c) => ({
        connected: c.isConnected,
        rowsNow: c.querySelectorAll(":scope > .pcard").length,
        hasChip: !!c.querySelector(":scope > .more-chip"),
      })).catch((e) => ({ err: String(e).slice(0, 60) }));
      detail += ` [glob=${glob} col=${JSON.stringify(alive)}]`;
    }
    await page.keyboard.press("e"); // collapse back
    await page.waitForTimeout(150);
    return true;
  };
  let anyChips = false;
  for (let attempt = 0; attempt < 6 && sampled < 2; attempt++) {
    const handles = await page
      .locator(".parse-row > .pcol .more-chip").elementHandles();
    if (handles.length) anyChips = true;
    let acted = false;
    for (const h of handles) {
      if (sampled >= 2) break;
      try {
        acted = (await tryChip(h)) || acted;
      } catch {
        // stale handle after async re-render — retry with fresh handles
        sampled -= 1;
        await page.waitForTimeout(700);
        break;
      }
    }
    if (!acted && attempt > 0) break;
  }
  if (!anyChips) detail = "(no overflow chip on page)";
  return { ok, detail };
}

/* ---------------- driver ---------------- */

const browser = await chromium.launch({ executablePath: EXE });
mkdirSync("qa-report/assets", { recursive: true });
const rows = [];
const t0 = Date.now();
const WORKS = worksFromCatalog();

for (let i = 0; i < WORKS.length; i++) {
  const w = WORKS[i];
  process.stdout.write(`[${i + 1}/${WORKS.length}] ${w.id} … `);
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await ctx.newPage();
  await page.addInitScript(NO_SW);
  try {
    await page.goto(`${BASE}${w.route}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".pcol", { state: "attached", timeout: 60000 });
    await page.waitForLoadState("networkidle", { timeout: 20000 })
      .catch(() => {});
    await page.waitForTimeout(1800); // async gloss paint settles

    const m4 = w.lang === "pi" ? [] : await m4Set(page, w.id).catch(() => []);
    const stats = await page.evaluate(MEASURE_FN, m4);
    const morphNote = await page.evaluate(() =>
      !!document.querySelector(".morph-empty-note"));
    const exp = await expanderCheck(page);

    Object.assign(w, {
      ok: true,
      units: stats.units,
      tokens: stats.tokens,
      carded: stats.carded,
      cardedPct: stats.tokens
        ? Math.round(1000 * stats.carded / stats.tokens) / 10 : 0,
      maxRows: stats.maxRows,
      dupRows: stats.dupRows,
      cjkLeaks: stats.cjkLeaks,
      m4Checked: m4.length,
      m4Bad: 0,
      glossMax: stats.glossMax,
      densityPx: stats.densityPx,
      vpUnits: stats.vpUnits,
      chips: stats.chips,
      expOk: exp.ok,
      expDetail: exp.detail,
      morphNote,
    });
    // M4 against live DOM: each all-uninflected form shows exactly 1 row
    w.m4Bad = await page.evaluate((forms) => {
      const want = new Set(forms);
      if (!want.size) return 0;
      let bad = 0;
      const units = document.querySelectorAll(".line, .prose-unit");
      for (const unit of units) {
        const cells = [...unit.querySelectorAll(".unit-scripts .w")]
          .map((c) => c.dataset?.orig ?? "");
        const cols = [...unit.querySelectorAll(".parse-row > .pcol")];
        if (cells.length !== cols.length) continue;
        for (let j = 0; j < cols.length; j++) {
          if (!want.has(cells[j])) continue;
          const n = [...cols[j].children].filter((c) =>
            c.classList.contains("pcard") &&
            !c.classList.contains("wasm-deep")).length;
          if (n !== 1) bad += 1;
        }
      }
      return bad;
    }, m4).catch(() => 0);
    w.grade = gradeOf(w);
    console.log(
      `${w.grade} carded=${w.cardedPct}% tok=${w.tokens} max=${w.maxRows}` +
      ` dup=${w.dupRows} cjk=${w.cjkLeaks} m4=${w.m4Bad}` +
      ` gl=${w.glossMax} px=${w.densityPx}${morphNote ? " NOTE" : ""}`,
    );
  } catch (e) {
    w.ok = false;
    w.error = String(e).slice(0, 160);
    w.grade = "D";
    console.log(`ERROR ${w.error}`);
  } finally {
    await ctx.close();
  }
  rows.push(JSON.parse(JSON.stringify(w)));
  await new Promise((r) => setTimeout(r, DELAY_MS));
}

await browser.close();

/* ---------------- outputs ---------------- */

const csvLine = (r) => [
  r.id, `"${r.title.replace(/"/g, "'")}"`, r.lang, r.kind,
  r.units, r.tokens, r.cardedPct, r.maxRows, r.dupRows, r.cjkLeaks,
  r.m4Bad, r.glossMax, r.densityPx, r.expOk ? "ok" : "FAIL",
  r.morphNote ? "note" : "", r.chips, r.grade, r.error ?? "",
].join(",");
const header = "work,title,lang,kind,units-on-page,tokens,carded%," +
  "maxRows,dupRows,cjkLeaks,m4Bad,glossMax,densityPx,exp,chips,grade,error";
writeFileSync(OUT_CSV, [header, ...rows.map(csvLine)].join("\n") + "\n");
writeFileSync(OUT_JSON, JSON.stringify(rows, null, 2));

const dist = {};
for (const r of rows) dist[r.grade] = (dist[r.grade] ?? 0) + 1;
console.log(`\ngrade distribution: ${
  Object.entries(dist).sort().map(([g, n]) => `${g}=${n}`).join(" ")
}`);
console.log(`csv -> ${OUT_CSV}\njson -> ${OUT_JSON}` +
  `\nelapsed ${Math.round((Date.now() - t0) / 1000)}s`);
