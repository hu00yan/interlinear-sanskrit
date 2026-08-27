# Samādhiraja Fix — Display / Parse / Compound Header

**Work:** `samadhiraja` (Samādhirājasūtra, 40 parivartas, prose, 670 units, 39k words, BHS). Vite live `http://localhost:4176`.

## 1. Line Wrapping

- **Before:** Prose chunks rendered via single-line flow (legacy grid-auto-flow:column), huge single line blew past viewport, long BHS compounds (87-char) pushed `document.scrollWidth > innerWidth`.
- **Fix:** `src/display.ts` already uses `.wcell` inline-flex wrapping; `src/style.css` tightened: `.wcell { overflow-wrap: anywhere }`, `.sline { overflow-wrap:anywhere; word-break:break-word }`, explicit prose rules `.prose-unit .wcell/.sline anywhere`. `max-width:100%` on cells prevents overflow.
- **Verify:** `playwright` at 1440/1024/390 — `doc.scrollWidth == innerWidth` (0 overflow), distinct `offsetTop` groups (12/19/36 lines for 60-word chunk), longest token 87 chars breaks via `anywhere` (241px < 253px container at 390).

## 2. Parse Head Brute-Force

- **Diagnosis:** `public/data/morph/_surface/by-work/samadhiraja.json` maps 15 306 tokens: 7 098 exact (`trusted true`), 8 208 stem-prefix fallbacks (longest-prefix ≥4, `trusted false`). Exact keys still spill over (no DCS coverage) — e.g. `मया→maya` shard holds 19 entries (`माया`, `अस्मद्` etc. via SLP1 folding), `श्रुतम्→srutam` holds `श्रु` (head prefix `sru` 3/6). `gold-reconcile` added `DCS_PREF` (`maya→माया`, `srutam→श्रु`) which boosted head substrings, loosening R4.
- **Fix:**
  - `src/api.ts` `surfaceKeyCandidates`: remove hyphen head fallback (`memberSurfaceKey`); hyphen compounds surface only via `Parse.m` member chain, never `headKey` alone.
  - `src/translit.ts` `surfaceKeyTrusted`: exact `Set.has` only, hyphen fallback removed; explicit length-equality guard (no prefix substring).
  - `src/group.ts` `parsePrior` / `collapseIndeclToken`: DCS pref boost guarded by `slp1KeyFor(want).length !== k.length && k.startsWith(wantKey)` → skip (e.g. `srutam` 6 vs `sru` 3 prefix → no +90). Hyphen member DCS pref removed.
- **Verify:** Samādhiraja `by-work` stem fallbacks remain honest empty (e.g. `भिक्षुनियुतशतसहस्रेण`, `बोधिसत्त्वनियुतैः` → 0 cards). Common exact words still carded (`एवं`, `भगवान्`), but head-prefix lemmas no longer DCS-boosted; ` BhG`/`Lotus` precision unchanged.

## 3. Samāsa Header Chinese

- **Before:** `src/compound.ts` `compoundBlock` emitted `复合词成分 Samāsa · N` — Chinese + IAST mixed chrome noise.
- **Fix:** Header → `Samāsa · N` (English/IAST only). Comment de-chinesed. `feat.ts` already English abbrs primary, Devanagari secondary.
- **Verify:** `document.querySelectorAll('.comp-head')` after `Expand all` — 23/34/22 headers, 0 contain `[\u4e00-\u9fff]`, text `^Samāsa · \d+$`.

## Regression

- `BhG` (338 pcols) + Lotus (793) — 0 CJK, 0 overflow, card counts stable.
- `tsc --noEmit` + `vite build` green (1 182 kB, 269 kB gz).

## Artifacts

- Screenshots `/tmp/samadhiraja-{1440,1024,390}.png` + `/tmp/samadhiraja-fix-check.png` (0 CJK, anywhere wrap).
