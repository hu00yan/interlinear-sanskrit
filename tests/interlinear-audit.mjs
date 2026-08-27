import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const base = "http://localhost:4176";
const assets = new URL("../qa-report/assets/", import.meta.url);
await mkdir(assets, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const failures = [];
const report = { base, pages: [], bhg: null, overflow: {} };
const fail = (message) => failures.push(message);

async function reader(route) {
  await page.goto(`${base}/#/${route}`, { waitUntil: "networkidle" });
  await page.waitForSelector(".pcol .pcard", { timeout: 15000 });
  await page.waitForTimeout(350);
}

await reader("bhagavadgita?ref=1.1");
const bhg = await page.evaluate(() => {
  const cards = [...document.querySelectorAll(".pcol .pcard")];
  const ordinary = cards.filter((card) => !/\bN\. of\b|proper name/i.test(card.textContent || ""));
  const missing = ordinary.filter((card) => !card.querySelector(".mw-gloss"));
  return {
    resolved: ordinary.length, glossed: ordinary.length - missing.length,
    rate: ordinary.length ? (ordinary.length - missing.length) / ordinary.length : 0,
    missing: missing.map((card) => card.querySelector(".lemma")?.textContent?.trim() || card.textContent?.trim()).slice(0, 50),
  };
});
report.bhg = bhg;
if (bhg.rate < .9) fail(`BhG gloss rate ${(bhg.rate * 100).toFixed(1)}% is below 90%; missing: ${bhg.missing.join(", ")}`);
const properName = await page.evaluate(() => [...document.querySelectorAll(".pcol .pcard")].some((card) =>
  /pāṇḍava|bhīṣma|droṇa|draupadeya/i.test(card.textContent || "") && !card.querySelector(".mw-gloss"),
));
if (!properName) fail("BhG proper-name parse without an inline gloss was not preserved");
await page.screenshot({ path: new URL("bhg-1.1-interlinear.png", assets).pathname, fullPage: true });

for (const route of ["bhagavadgita?ref=1.1", "saddharmapundarika", "satakatraya", "ramayana", "yoga-sutra"]) {
  try {
    await reader(route);
    const result = await page.evaluate(() => ({
      inlineTranslation: document.querySelectorAll(".tl-line").length,
      forbidden: /行间|侧栏/.test(document.body.textContent || ""),
      sidebarButton: !!document.querySelector(".translation-sidebar-btn"),
    }));
    if (result.inlineTranslation || result.forbidden) fail(`${route}: inline or view-mode translation leaked`);
    if (result.sidebarButton) {
      await page.locator(".translation-sidebar-btn").click();
      await page.waitForSelector(".tr-sidebar:not(.hidden)");
      const divider = page.locator(".sb-divider");
      const box = await divider.boundingBox();
      if (box) await page.mouse.move(box.x + 2, box.y + 8), await page.mouse.down(), await page.mouse.move(box.x - 80, box.y + 8), await page.mouse.up();
      await page.locator(".sb-close").click();
      await page.waitForSelector(".tr-sidebar.hidden", { state: "attached" });
      const next = page.getByRole("button", { name: "Next →" });
      if (await next.isEnabled()) await next.click();
      if (await page.locator(".tr-sidebar:not(.hidden)").count()) fail(`${route}: sidebar reopened after page turn`);
    }
    report.pages.push({ route, ...result });
  } catch (error) { fail(`${route}: ${error.message}`); }
}

await page.goto(`${base}/#/about`, { waitUntil: "networkidle" });
for (const label of ["Export vocabulary", "Import vocabulary…", "Export bookmarks", "Import bookmarks…"]) {
  if (!await page.getByRole("button", { name: label }).isVisible()) fail(`${label} is not visible`);
}
const download = page.waitForEvent("download");
await page.getByRole("button", { name: "Export vocabulary" }).click();
if (!(await download).suggestedFilename().endsWith(".json")) fail("vocabulary export did not download JSON");
const input = page.locator('input[type="file"]').first();
await input.setInputFiles({ name: "vocab.json", mimeType: "application/json", buffer: Buffer.from('{"v":1,"known":{},"settings":{"mode":"off"}}') });

for (const width of [1440, 1024, 390]) {
  await page.setViewportSize({ width, height: 900 });
  await reader("bhagavadgita?ref=1.1");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  report.overflow[width] = overflow;
  if (overflow > 0) fail(`${width}px viewport overflow: ${overflow}px`);
}
await page.screenshot({ path: new URL("mobile-bhg-1.1.png", assets).pathname, fullPage: true });
await writeFile(new URL("interlinear-audit-dom.json", assets), JSON.stringify(report, null, 2));
await browser.close();
if (failures.length) throw new Error(failures.join("\n"));
console.log(JSON.stringify(report, null, 2));
