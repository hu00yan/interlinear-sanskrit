# Parse Compact Audit — kim/ka paradigm-wall fix (display layer)

Closes the user-pasted किम् disaster: one token rendering ~22 stacked
gender×number×case rows, EACH repeating the full MW essay gloss, with
homographs (ka → "N. of Prajāpati") ranked above the interrogative particle.
Fix is display-layer ONLY (src/**); morph shards owned by the pipeline agent
were not touched.

**Standalone report** — `lh` CLI is not installed in this environment
(`command not found`), so per protocol this is a repo qa-report instead of a
LobeHub acceptance round. Evidence lives in `qa-report/assets/parse-compact/`.

## Before (pre-fix probe, quoted from live :4176 DOM)

- किम् collapsed card: 4 segments enumerating `kim n. m. pl. loc. / n. n. pl.
  loc. / n. n. sg. nom. / n. n. sg. acc.` + chip 「另有 22 解」 — 26 raw
  analyses behind one token.
- किम् word panel: **27 entries**, the MW essay gloss ("is very frequently
  connected with other particles… RV.") repeated on nearly every row.
- lookup "ka": TOP card = किम् noun स्त्री nom.sg (wrong word entirely); MW
  section led with "N. of Prajāpati".
- lookup "deva": TOP card = `ādin-deva` (hyphen homograph), not देव.

## Plan → cases (user-visible outcomes; evidence in assets/parse-compact/)

| # | Outcome a reader can judge | Evidence | Status |
|---|---|---|---|
| 1 | किम् renders as a compact reading set — 3 visible rows, interrogative `kim indecl.` FIRST, paradigm grid collapsed into `m./n. pl./sg./du. various cases` + 「另有 4 解」 | dom-snippets.txt §BhG; after-bhg-kim-card.png | pass |
| 2 | क shows the interrogative reading first; the ख "N. of Prajāpati" homograph ranks LAST with its duplicate gloss shown only once | after-lookup-ka.png; dom-snippets.txt §ka | pass |
| 3 | Glosses are clipped sentences (first sentence boundary ≤120 chars), never essay blobs; full text stays in the panel MW section / dict-gloss expander | after-bhg-kim-panel.png; parse-audit-results.json (glossMax ≤102 across all lookups) | pass |
| 4 | BhG 1–3, Lotus ch1–2, Meghadūta sarga 1, Raghuvaṃśa, Rāmāyaṇa bāla: every collapsed card ≤3 rows, zero duplicate (lemma+feats) rows, zero CJK in parse/gloss content | parse-audit-results.json (M1–M3, 10 466 tokens) | pass |
| 5 | Indeclinable tokens (531 checked in Lotus alone) render exactly ONE row; lookup ca = exactly 1 row | parse-audit-results.json (M4) | pass |
| 6 | Word-click panel groups readings ("7 readings", one entry per (lemma, POS-class) with "N attested combos" markers) instead of 27 stacked entries; compound samāsa blocks and the R4 honesty gate unchanged | after-bhg-kim-panel.png; dom-snippets.txt §panel | pass |

## Closed-loop audit (tests/parse-audit.mjs — the gate)

Hard metrics over BhG 1–3 / Lotus part01 ch1–2 range / Meghadūta sarga 1 /
Raghuvaṃśa opening / Rāmāyaṇa bāla sample / Dhammapada 1–20 (Pali) +
lookup {kim, ka, ca, vā, rāma, deva}:

| Metric | Final value |
|---|---|
| M1 collapsed rows/token ≤3 | max 3 across 10 466 tokens (6 pages) |
| M2 duplicate (lemma+feats) rows | 0 |
| M3 CJK in parse/gloss content nodes | 0 (sanctioned chrome exempt) |
| M4 indecl tokens == 1 row | 0 bad of 1 226 checked |
| M5 visible gloss ≤120 chars | max 102 (lookup), 0 violations |
| M6 function-word TOP row = particle reading | kim/ka/ca/vā/rāma/deva all pass |

## Iteration table

| it | red metrics | fix |
|---|---|---|
| 1 | EXP ×6 (audit artifact: index locators re-resolved after expansion — measured the WRONG column), M6-ka (top card was noun-class क, audit demanded literal "indecl." tag) | audit: stable element handles; ka asserts lemma identity. src: DCS `part` without tense/voice reclassifies nominal (inflected particles/pronouns group with noun homographs); proper-name demotion never applies to exact surface-form matches |
| 2 | — | ALL GREEN |
| 3 | — | ALL GREEN (confirmation run after rebase on pipeline agent's d291a93) |

## Fixes shipped (display layer only)

- `src/group.ts` (new): group by (lemma, POS-class); ranking priors
  (indecl +35, exact surface-form +12, proper-name-gloss demotion −15 for
  non-matching lemmas); compact-set feature summaries
  (`m./n. pl./sg./du. various cases`); sentence-boundary gloss clipping ≤120.
- `src/group-ui.ts` (new): shared group-row head builders.
- `src/render.ts`: collapsed = ≤3 ranked group rows + chip; expanded = all
  groups; panel = one entry per reading; compound scan / vocab / lexicon
  jumps use prior-ranked parses.
- `src/lookup.ts`: grouped reading cards ≤3 + inline expand chip; lemma
  glosses preloaded before ranking (homograph demotion needs them).
- `src/compound.ts`: attachMwGloss routes through clipGloss.

Supersession: tests/verify-merge-rows.mjs V1/V2 (exactly ONE merged card,
min(distinct,4) inline segments) describe the pre-grouping merge spec and
are superseded by the ≤3-group-rows spec audited here.

tsc clean; vite build ok. Gate: `node tests/parse-audit.mjs` → ALL METRICS
GREEN. Commits: 925bf45, b75c5e7.
