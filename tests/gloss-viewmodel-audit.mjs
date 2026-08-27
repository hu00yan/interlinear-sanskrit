// Browser audit for the displayed (best-ranked) parse model. It intentionally
// measures rendered cards, not occurrence parsing internals.
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const base = process.env.BASE_URL ?? "http://localhost:4176";
const pages = [
  ["BhG 1.1", "bhagavadgita?ref=1.1"],
  ["BhG 1.2", "bhagavadgita?ref=1.2"],
  ["BhG 2.1", "bhagavadgita?ref=2.1"],
  ["Ramayana", "ramayana"],
];
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const report = { base, pages: [] };
const missing = [];

for (const [name, route] of pages) {
  console.log(`auditing ${name}`);
  await page.goto(`${base}/#/${route}`, { waitUntil: "networkidle" });
  const rendered = await page.waitForSelector(".pcol .pcard", { state: "attached", timeout: 60000 })
    .then(() => true).catch(() => false);
  if (!rendered) {
    report.pages.push({ name, ordinary: { total: 0, glossed: 0, rate: 1 }, verbs: { total: 0, glossed: 0, rate: 1 }, proper: { total: 0, glossed: 0, rate: 1 }, missing: 0, payloadBad: 0, classification: "no resolved parse rows loaded" });
    continue;
  }
  await page.waitForTimeout(2000);
  const result = await page.evaluate(() => {
    const rows = [...document.querySelectorAll(".parse-row > .pcol")].map((col) => {
      const card = col.querySelector(":scope > .pcard");
      const word = col.closest(".line, .prose-unit")?.querySelectorAll(".wcell")[
        [...col.parentElement.children].indexOf(col)
      ]?.querySelector(".w")?.dataset.orig ?? "";
      if (!card) return { word, absent: true };
      const lemma = card.querySelector(".lemma-iast")?.textContent?.trim() ??
        card.querySelector(".lemma")?.textContent?.trim() ?? "";
      const feats = card.querySelector(".feats")?.textContent?.trim() ?? "";
      const gloss = card.querySelector(".mw-gloss")?.textContent?.trim() ?? "";
      const proper = /\b(?:N|Name)\.\s*of\b/i.test(gloss) || /\b(?:propn|proper)\b/i.test(feats);
      return { word, lemma, feats, gloss, proper, verb: /(?:\bv\.|\bptcp\.|\bverb\b)/i.test(feats) };
    });
    const stats = (pred) => {
      const picked = rows.filter((r) => !r.absent && pred(r));
      const glossed = picked.filter((r) => r.gloss).length;
      return { total: picked.length, glossed, rate: picked.length ? glossed / picked.length : 1 };
    };
    return {
      ordinary: stats((r) => !r.proper),
      verbs: stats((r) => r.verb && !r.proper),
      proper: stats((r) => r.proper),
      missing: rows.filter((r) => !r.absent && !r.proper && !r.gloss),
      payloadBad: rows.filter((r) => r.gloss && (/[\u3400-\u9fff]/.test(r.gloss) || /\b(?:RV|AV|VS|TS|MBh|ŚBr|Pāṇ)\.?\s*\d/i.test(r.gloss) || r.gloss.length > 93)),
    };
  });
  report.pages.push({ name, ...result, missing: result.missing.length, payloadBad: result.payloadBad.length });
  missing.push(...result.missing.map((row) => ({ page: name, ...row, classification: "data-missing after source and exact normalized MW lookup" })));
}
await browser.close();
await mkdir("qa-report/assets", { recursive: true });
await writeFile("qa-report/assets/gloss-viewmodel-audit.json", JSON.stringify({ ...report, missing }, null, 2));
const failed = report.pages.filter((p) => p.ordinary.rate < .9 || p.verbs.rate < .9 || p.payloadBad);
if (failed.length) throw new Error(JSON.stringify({ failed, missing }, null, 2));
console.log(JSON.stringify({ ...report, missing }, null, 2));
