# Vocabulary Route Fix

## Route and controls

- The Sanskrit home footer now exposes the same visible `About · sources & licenses` link as Greek Reader, targeting `#/about`.
- The About route retains a separate visible `← Back to the library` link, so the vocabulary and bookmark backup controls are reachable without an undocumented hash.
- At a 390px-wide viewport, all four controls are visible and the About page has no horizontal overflow. Screenshot: `qa-report/assets/vocab-about-mobile-390.png`.

## Browser closed loop

`node tests/vocab-route-audit.mjs` against `http://localhost:4176` passed:

- Home -> About navigation succeeded.
- Vocabulary export downloaded `sanskrit-reader-vocab.json`; its inspected payload had `v: 1`, object `known`, and object `settings`.
- A non-destructive in-memory fixture imported one vocabulary item and reported `Imported 1 new item.`
- Invalid JSON reported `Import failed: not a valid file.`
- About -> library navigation succeeded.

The test launches an isolated browser context and never writes to a user's existing vocabulary or bookmark storage.

## Post-data BhG gloss audit

`node tests/interlinear-audit.mjs` was rerun after MW data commit `eb36e5f`. BhG 1.1 inline card coverage is **87.6%**, so the audit remains below its 90% gate.

This is a UI consumption discrepancy, not a data-coverage result: the MW data audit measures whether any non-stem candidate in the morphology shard has its embedded `g` gloss (96.4% over Bhagavadgita), while the browser audit counts only the single best-ranked displayed parse group and requires its `.mw-gloss` element. Proper names are intentionally excluded from the data denominator but remain present in the browser card set. No dictionary, morphology, or pipeline data was changed.
