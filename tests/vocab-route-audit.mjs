import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
import { chromium } from "playwright";

const base = "http://localhost:4176";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

try {
  await page.goto(`${base}/#/`, { waitUntil: "networkidle" });
  const about = page.getByRole("link", { name: "About · sources & licenses" });
  await assert.doesNotReject(() => about.waitFor({ state: "visible" }));
  await about.click();
  await page.waitForURL(/#\/about$/);

  for (const label of [
    "Export vocabulary",
    "Import vocabulary…",
    "Export bookmarks",
    "Import bookmarks…",
  ]) {
    assert.equal(await page.getByRole("button", { name: label }).isVisible(), true,
      `${label} must be visible on desktop`);
  }

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export vocabulary" }).click();
  const download = await downloadPromise;
  assert.equal(download.suggestedFilename(), "sanskrit-reader-vocab.json");
  const payload = JSON.parse(await readFile(await download.path(), "utf8"));
  assert.equal(payload.v, 1);
  assert.equal(typeof payload.known, "object");
  assert.equal(typeof payload.settings, "object");

  const input = page.locator('input[type="file"]').first();
  await input.setInputFiles({
    name: "valid-vocab.json",
    mimeType: "application/json",
    buffer: Buffer.from('{"v":1,"known":{"auditfixture":{"lemma":"audit","ts":1}},"settings":{"mode":"off"}}'),
  });
  await assert.doesNotReject(() => page.getByText("Imported 1 new item.").waitFor());
  await input.setInputFiles({
    name: "invalid-vocab.json",
    mimeType: "application/json",
    buffer: Buffer.from("not json"),
  });
  await assert.doesNotReject(() => page.getByText("Import failed: not a valid file.").waitFor());

  await page.setViewportSize({ width: 390, height: 844 });
  for (const label of ["Export vocabulary", "Import vocabulary…", "Export bookmarks", "Import bookmarks…"]) {
    assert.equal(await page.getByRole("button", { name: label }).isVisible(), true,
      `${label} must be visible at 390px`);
  }
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true,
    "About must not overflow at 390px");
  await mkdir(new URL("../qa-report/assets/", import.meta.url), { recursive: true });
  await page.screenshot({
    path: new URL("../qa-report/assets/vocab-about-mobile-390.png", import.meta.url).pathname,
    fullPage: true,
  });

  await page.getByRole("link", { name: "← Back to the library" }).click();
  await page.waitForURL(/#\/$/);
  console.log("vocabulary route audit passed");
} finally {
  await browser.close();
}
