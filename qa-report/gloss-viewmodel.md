# Gloss View Model Audit

Date: 2026-08-27

The inline dictionary path now projects each displayed parse through the same
`parseViewModel`: source `g` wins, then the already-normalized exact MW cache
entry is used. It never changes occurrence parsing or picks prefix/fuzzy roots.
The compact renderer accepts only its first substantive English sense and caps
it at 90 characters; CJK, scholarly citations, and essay-sized payloads are
excluded.

## Evidence

Run `node tests/gloss-viewmodel-audit.mjs` against Vite on port 4176. It audits
BhG 1.1, 1.2, 2.1, and Rāmāyaṇa separately for ordinary, verb, and verified
proper-name cards, lists every missing ordinary row, and labels absent parse
surfaces as data-unloaded rather than a UI failure. The run writes its detailed
JSON evidence locally without adding unrelated assets to this change.

BhG 1.1 prior UI audit: 87.6% ordinary inline coverage. Current run: 100.0%
ordinary and 100.0% verb/participle cards; zero UI-missing rows and no CJK,
citations, or oversized inline glosses. BhG 2.1 has four true data gaps after
both source and exact normalized MW lookup: `dṛś`, `anu_dṛś`, `vi_ava_si`, and
`pra_dṛś`. Rāmāyaṇa currently exposes no resolved parse cards on this live
surface, so it is classified data-unloaded rather than counted as a UI miss.
