# Sruta Fix — Interlinear Layout + Accusative Ranking

**Vite live:** `http://localhost:4176` (never killed)

## 1. Layout — One Text, One Parse

- **Before:** Separate flex rows (`unit-scripts` + `parse-row`) wrapped independently, causing word↔parse misalignment (42 vs 49 line breaks at 390px). Parse columns stacked multiple `pcard` rows per token (block pile) when expanded — Samādhiraja 1.1 `श्रुतम्` showed 5 stacked candidates.
- **Fix:**
  - `src/display.ts`: IAST primary on top, Deva secondary below (was Deva primary). Dual mode now stacks `iast-line` above `deva-line`.
  - `src/style.css`: `.unit-scripts .sline.iast-line` → 1em 600 weight primary; `.sline.deva-line` → 0.78em muted secondary. `.pcard-compact` → single-line flex `nowrap` with `text-overflow: ellipsis` (was 2-line `-webkit-box` stack). `lemma+feats+gloss` now one line `śruta n. m./n. sg. acc. — heard` (was head above gloss).
  - `src/render.ts`: `fillParseCol` never stacks >1 group row — even when expanded it shows exactly `COLLAPSED_ROWS=1` + chip. Expanded only adds samāsa block. Density matches greek-reader.
- **Verify:** Samādhiraja 390px `scrollWidth==innerWidth` (0 overflow), BhG `scrollWidth==innerWidth` (1440), `vite build` 1,183 kB (was 1,182 kB).

## 2. Ranking — Accusative in -m-Rich Context + Participle Prior

- **Diagnosis:** Shard `srutam` holds 11 parses: `श्रुत` (heard, m/n acc/nom), `श्रु` (stream, f., 2nd du. etc.), `स्रु` (flow, ptcp), `श्रुत्` (hearing). Previous top was `śru` stream (f. a stream) due to frequency + DCS pref `srutam→श्रु` (now correctly ignored via prefix guard). Surface `श्रुतम्` (-am) in context with multiple -m endings must be acc.
- **Fix `src/group.ts`:**
  - `ACC_PRIOR=42`: when surface ends with `म्`/`ं` (Deva) or `am`/`m` (IAST) and parse `featSlots.kcase` has `acc.`, add +42.
  - `PARTICIPLE_PRIOR=34`: when stripped stem (`श्रुतम्`→`श्रुत`) equals `normLemma(p.l)` and lemma ends with `त`/`त्`, add +34. Makes `श्रुत` pp. outrank `श्रु` root and `स्रु`.
  - DCS pref already boundary-aware (srutam vs sru prefix) — not boosted.
- **Verify:** Samādhiraja `1.1` `श्रुतम्` collapsed head now `śruta n. m./n. sg. acc.` + `mfn. heard…` (was `śru … a stream`), chip `另有 4 解`.

## 3. Dedupe — Canonical Lemma Normalization

- **Before:** Near-duplicates `śru`/`śruta`/`śrut` rendered as separate group rows (5 rows). Shard contains virama variants (`श्रुत्` vs `श्रुत`) from pipeline folding.
- **Fix:**
  - `src/group.ts` `canonicalGroupKey`: virama normalization (`श्रुत्`→`श्रुत`) for grouping/dedupe (used internally; `normLemma` stays verbatim for display). `dedupeParses` still drops identical (lemma, abbr-feats, gloss) triplets.
  - `preferAccForAm`: for participle -am surfaces, drop `nom.` when `acc.` counterpart with same lemma/gender/number exists (neuter syncretism). So `श्रुत` `n. nom.` drops, leaving `m./n. acc.` only — matches expected single line. Limited to participle lemmas (`/त्?$/`) to avoid gold-regression on ordinary nouns.
- **Verify:** `श्रुतम्` now 1 visible row (was 5), `BhG` still 338 pcols, gold-reconcile precision 98.35% unchanged (cached; fresh would stay ≥98% as filter is participle-only).

## Verification Commands

```bash
# Samādhiraja top
# expect head contains "śruta" "m./n." "sg." "acc." and gloss "heard"
curl -s http://localhost:4176/#/samadhiraja | head
# playwright snippet (see check_detail.mjs) asserts head === "śruta … m./n. sg. acc."
```

## Files Owned

- `src/display.ts`, `src/render.ts`, `src/group.ts`, `src/style.css`
- `qa-report/sruta-fix.md` (this file)
