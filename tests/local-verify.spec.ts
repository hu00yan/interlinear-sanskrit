// Throwaway local-verification spec (QA session) — run against the vite
// preview server on :4189. Not part of any CI pipeline.
import { expect, test } from "@playwright/test";

const BASE = "http://localhost:4189";
// QA-only: reuse the locally cached Chromium build (1187) because the
// ms-playwright cache predates the pinned driver (1.62 wants build 1234).
test.use({
  launchOptions: {
    executablePath:
      "/Users/huyan00/Library/Caches/ms-playwright/chromium-1187/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
  },
});

test("local verify: home, dual-script reader, MW gloss panel, toggle persistence", async ({
  page,
}) => {
  test.setTimeout(90_000);

  // ---- 1. home: Upaniṣads author group + Bhagavadgītā start card ----
  await page.goto(BASE + "/");
  const upaBlock = page.locator('.author-block:has(h2:text-is("Upaniṣads"))');
  await expect(upaBlock).toBeVisible({ timeout: 15_000 });
  await expect(upaBlock.locator(".work-link").first()).toBeVisible();
  const card = page.locator('[data-start-card="1"]');
  await expect(card).toHaveCount(1);
  await expect(card).toContainText("Bhagavadgītā");

  // ---- 2. open BhG reader; both scripts on -> stacked deva+IAST lines ----
  await page.goto(BASE + "/#/bhagavadgita");
  await page.evaluate(() =>
    localStorage.setItem(
      "interlinear-sanskrit.display",
      JSON.stringify({ iast: true, deva: true }),
    ),
  );
  await page.reload();
  const iastCb = page.locator("#script-iast");
  const devaCb = page.locator("#script-deva");
  await expect(iastCb).toBeChecked({ timeout: 15_000 });
  await expect(devaCb).toBeChecked();
  await expect(page.locator("body")).toHaveClass(/both-scripts/);
  const unit = page.locator(".unit-scripts.dual").first();
  await expect(unit).toBeVisible({ timeout: 15_000 });
  // stacked: first word cell renders Devanagari on top, IAST below
  const devaTok = unit.locator(".w.deva-line").first();
  const iastTok = unit.locator(".w.iast-line").first();
  await expect(devaTok).toBeVisible();
  await expect(iastTok).toBeVisible();
  expect(/\p{Script=Devanagari}/u.test(await devaTok.textContent())).toBe(true);
  expect(/[āīūṛṭḍṅñśṣṃai]/i.test(await iastTok.textContent())).toBe(true);

  // ---- 3a. MW gloss panel: POSITIVE CONTROL (lowercase-initial SLP1 key)
  // कुरुक्षेत्रे -> key "kurukzetre" -> prefix hit in k-shard. PASSES.
  await unit.locator(".w.deva-line").nth(1).click();
  const panel = page.locator("aside.side-panel");
  await expect(panel).toBeVisible();
  await expect(panel.locator('h3.mw-head:text-is("Monier-Williams")')).toBeVisible({
    timeout: 20_000,
  });
  await expect(panel.locator(".mw-entry").first()).toBeVisible();

  // ---- 3b. QA-LOCAL-1 REGRESSION: धर्मक्षेत्रे derives SLP1 "Darmakzetre";
  // shard keys are lowercase ("darma…"), so the lookup key must be
  // lowercased AFTER conversion. MW section MUST now render.
  await devaTok.click();
  await expect(panel.locator("h2")).toContainText(/धर्मक्षेत्रे|dharmak/);
  await expect(panel.locator('h3.mw-head:text-is("Monier-Williams")')).toBeVisible({
    timeout: 20_000,
  });
  await expect(panel.locator(".mw-entry").first()).toBeVisible();
  await page.keyboard.press("Escape"); // close panel between checks

  // ---- 3c. same normalization for a capital-bearing mid-word key:
  // कृष्ण -> "kfzRa" -> lookup "kfzra" (exact k-shard hit). Skips silently
  // when no कृष्ण token is mounted in this view.
  const krsna = page.locator('.w.deva-line', { hasText: "कृष्ण" }).first();
  if ((await krsna.count()) > 0) {
    await krsna.click();
    await expect(panel).toBeVisible();
    await expect(panel.locator('h3.mw-head:text-is("Monier-Williams")')).toBeVisible({
      timeout: 20_000,
    });
    await expect(panel.locator(".mw-entry").first()).toBeVisible();
    await page.keyboard.press("Escape");
  }

  // ---- 4. toggle persists after reload (both stay on) ----
  await page.reload();
  await expect(page.locator("#script-iast")).toBeChecked({ timeout: 15_000 });
  await expect(page.locator("#script-deva")).toBeChecked();
  await expect(page.locator("body")).toHaveClass(/both-scripts/);
});
