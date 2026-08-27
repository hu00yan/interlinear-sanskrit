import { expect, test } from "@playwright/test";

const BASE = process.env.READER_BASE_URL ?? "http://localhost:4176";

test("catalog exposes only the two source-locked editions", async ({ page }) => {
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".work-link").getByText("Bhagavadgītā", { exact: true })).toBeVisible();
  await expect(page.locator(".work-link").getByText("Buddhacarita", { exact: true })).toBeVisible();
  await expect(page.locator(".work-link")).toHaveCount(2);
});

test("source-locked DCS cards render exact contextual rows", async ({ page }) => {
  await page.goto(`${BASE}/#/bhagavadgita?ref=1.1`, { waitUntil: "domcontentloaded" });
  await expect(page.locator('[data-ref="1.1"]')).toBeVisible({ timeout: 30_000 });
  const audit = await page.locator('[data-ref="1.1"]').evaluate((unit) => {
    const words = [...unit.querySelectorAll<HTMLElement>(".w[data-orig]")]
      .filter((word) => !word.classList.contains("iast-line"));
    const cards = [...unit.querySelectorAll<HTMLElement>(".parse-row > .pcol")];
    return words.map((word, i) => ({ word: word.dataset.orig, sourceRow: cards[i]?.dataset.dcsRow, card: cards[i]?.textContent?.replace(/\s+/g, " ").trim() }));
  });
  expect(audit).toHaveLength(11);
  expect(audit.every((row) => row.card && row.sourceRow !== undefined)).toBe(true);
  expect(audit.find((row) => row.word === "किम्")?.card).toMatch(/kim.*acc/i);
  expect(audit.find((row) => row.word === "अकुर्वत")?.card).toMatch(/did they do/i);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('[data-ref="1.1"]')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("BhG 18.72 śrutam keeps its own DCS row", async ({ page }) => {
  await page.goto(`${BASE}/#/bhagavadgita?ref=18.72`, { waitUntil: "domcontentloaded" });
  const unit = page.locator('[data-ref="18.72"]');
  await expect(unit).toBeVisible({ timeout: 30_000 });
  const srutam = await unit.evaluate((el) => {
    const words = [...el.querySelectorAll<HTMLElement>(".w[data-orig]")]
      .filter((word) => !word.classList.contains("iast-line"));
    const index = words.findIndex((word) => word.dataset.orig === "श्रुतम्");
    const cards = [...el.querySelectorAll<HTMLElement>(".parse-row > .pcol")];
    return { index, row: cards[index]?.dataset.dcsRow, card: cards[index]?.textContent };
  });
  expect(srutam).toEqual(expect.objectContaining({ index: 6, row: "4329" }));
  expect(srutam.card).toMatch(/heard/i);
});

test("DCS CoNLL-U edition has occurrence-only grammar", async ({ page }) => {
  await page.goto(`${BASE}/#/buddhacarita`, { waitUntil: "domcontentloaded" });
  const unit = page.locator('[data-ref="dcs-477192"]');
  await expect(unit).toBeVisible({ timeout: 30_000 });
  await expect(unit.locator(".parse-row > .pcol")).toHaveCount(8);
  await expect(unit.locator(".parse-row > .pcol .pcard")).toHaveCount(8);
  expect(await unit.locator(".more-chip").count()).toBe(0);
});
