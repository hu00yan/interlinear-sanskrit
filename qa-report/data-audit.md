# Data Coverage Audit — interlinear-sanskrit (Phase-1 BhG vertical slice)

Date: 2026-08-24 · Auditor: independent subagent (read-only toward data/pipeline; own re-implemented normalizer & transliteration tables used for verification — pipeline code was inspected to diagnose root causes, never copied).

Scope: `public/data/{texts,morph,gloss,trans,catalog.json}`, `pipeline/sanscript.py`. `dist/` checked only as a mirror. Note: another agent is actively building (`git status`: `src/api.ts`, `src/render.ts` modified; new pipeline scripts untracked) — numbers below are a snapshot and may shift after their next build.

---

## Layer 1 — Texts (`public/data/texts/**`) ✅ production-ready

| File | Units | Ref range | Tokens | Encoding |
|---|---|---|---|---|
| `tlg9000/bhagavadgita-part01.json` | **700 / 700** | **1.1 – 18.78**, 0 gaps, 0 dupes | **8,474** | 100 % Devanagari |

- Verse-per-chapter matches GRETIL source exactly (`.cache-corpus/bhg_gretil.htm`): ch 13 ends at **13.34** in this edition — that *is* the canonical 700-verse convention; total is correct, not short one verse.
- Zero empty tokens, zero mixed-script tokens, zero Latin/diacritic contamination.
- Encoding consistency sampled across 3 surfaces: text tokens, morph `l` display lemmas, gloss `u` fields — Devanagari-only everywhere (only defect: 6 morph lemmas are a bare `"-"` placeholder).
- `kind:"verse"`, `alignment:"surface-form"` sensible.

## Layer 2 — Morphology (`public/data/morph/*`) ⚠️ gaps blocking

| Metric | Value |
|---|---|
| Shards | 22 lettered `[a-z].json` + `_surface_index.json` |
| Keyed forms | **2,568** (union of lettered shards) |
| Surface index | 2,948 Devanagari surface → key |
| Key scheme | Verified genuine lowercase SLP1 (`z`=ṣ, `f`=ṛ, `M`=anusvara…) — no IAST diacritics, no HK digraph leakage |
| **BhG token resolution (reader-visible: token → `_surface_index` → shard)** | **5,042 / 8,474 = 59.50 %** |
| BhG resolution, my independent normalizer, exact key | 56.0 % |

**Top unresolved tokens (count × surface):** स ×62, तत् ×31, तद् ×30, यो ×30, ये ×26, इदं ×24, ऽपि ×22, यद् ×22, त्व् ×21, ह्य् ×21, इत्य् ×19, किं ×18, योगी ×17, तं ×14, महाबाहो ×14 … Pattern: (a) ultra-short function words ≤3 chars that the ≥4-char stem-trim fallback can't reach, (b) sandhi remnants (`त्व्`, `ह्य्`, `कश्`, `ऽपि`), (c) basic content words that *should* be in the analysis source.

**Root cause — shipped shards are stale vs their own builder:** re-running `build_morph.main()` logic in-memory against the current `.cache-corpus/analysis.json` yields **4,151 keys**; shipped shards hold 2,568 (**2,072 missing**, incl. `kim`, `tat`, `idam`, `yo`, `ye`, `yogi`; 489 present-but-not-reproducible, i.e. expand-pass leftovers over an older base). Fresh-base coverage would be **76.2 %** exact (+MW-headword prefix pass → **84.4 %**). A plain rebuild recovers most of the gap without new code.

Minor: 37 shard keys carry a leaked trailing `;` (e.g. `tavadim;`, `mahatman;`) from DCS-row field separators; harmless for lookup, ugly for search.

## Layer 3 — Glosses (`public/data/gloss/*.json`) ❌ quality blocker

| Metric | Value |
|---|---|
| Entries | **40,869** across 26 shards, SLP1-keyed, `{u,g}` |
| Structure | Keys/u-fields clean; but text quality is broken at exactly the high-frequency lemmas |

Spot-check of BhG-core lemmas:

| Lemma (SLP1 key) | Present? | Stored gloss | Verdict |
|---|---|---|---|
| `karman` (karman/karma) | **MISSING** | — | ❌ |
| `yoga` | yes | "&c. See pp. 856, 858." | ❌ cross-reference junk, no sense |
| `atman` | yes | "[ Old Germ. ātum ; Angl.Sax. ædhm…]" | ❌ etymology note, not the sense ("breath/soul/self") |
| `darma` (dharma) | yes | "a thing, Sukh. i" | ❌ wrong homonym (sense 1 = "custom, law, duty") |

Root cause (diagnosed in `pipeline/build_glosses.py`): it prefers the accented `<k2>` headword over `<k1>`; Cologne k2 values usually contain accent slashes (`ka/rman`, `Atma/n`, `darma/`), which then fail the `[a-z~]+` emission filter and are **silently dropped — 144,868 of ~185.7 k records**; only 40,869 of 176,833 distinct MW headwords survive (~23 %). Where a homograph with a clean k2 exists, first-wins keeps whatever came first — hence cross-ref/etymology/wrong-homonym picks above.

Cosmetic-but-systemic: **100 %** of `g` strings begin with leaked catalog noise (`"<L><pc>"` digits, e.g. `"45453 259,2 …"`), and senses are hard-truncated at 200 chars mid-word.

## Layer 4 — Translation (`public/data/trans/bhagavadgita.json`) ⏳ in progress

- File **exists** (created today 09:40) but is a placeholder: `{"translator": "K. T. Telang", "year": 1882, "license": "Public domain (SBE 8)", "alignment": "chapter-loose", "units": []}` — **0 units vs 700**; BG 2.47 cannot be sampled yet.
- Source material staged: `.cache-corpus/sbe08.txt` / `.cache-trans/sbe08*.htm` (Telang SBE 8). An earlier Arnold attempt (`.cache-corpus/arnold_*.json`) appears abandoned.
- `catalog.json` still advertises *"Sir Edwin Arnold, The Song Celestial", 1885* → **contradicts the Telang trans file**.
- Stale `dist/data/trans/bhagavadgita.json` holds an old Arnold build: 18 chapter-level units whose `text` leaks raw HTML (`class="poem">\n…`).

## Layer 5 — Transliteration (`pipeline/sanscript.py`) ⚠️ one real bug

- Self-test: `python3 pipeline/sanscript.py` → **ALL PASS**, exit 0, canonical key `'bagavadgita'`.
- My independent verification, 5 words × DEVA↔IAST↔HK↔SLP1:

| Word | DEVA→IAST | DEVA→SLP1 | HK round-trip |
|---|---|---|---|
| dharma | dharma ✓ | darma ✓ | **✗ धर्म → "dharm" → डर्म** |
| yoga | yoga ✓ | yoga ✓ | ✓ |
| kṛṣṇa | kṛṣṇa ✓ | kfzrna ✓ | ✓ (kRiShNa) |
| arjuna | arjuna ✓ | arjuna ✓ | ✓ |
| īśvara | īśvara ✓ | isvara ✓ | ✓ (Izvara) |

DEVA↔IAST↔SLP1 chains are solid and agree with my from-scratch tables. **The HK pivot is not lossless**, contradicting its own docstring:
- Medial aspirate digraphs collide with the late single-letter rules: `dh`→`D` then `D`→`q` ⇒ dharma→डर्म; same collision class kills `gh` (`G`→`N`) and `jh` (`J`→`Y`). Battery: `kArzNi→kArShGi→kArzRi ✗`, `zwaNPara→ShwaGphara→zwaRPara ✗` (ṇ/ṅ effectively swapped: forward maps ṇ→`G`, leaves ṅ as `N`), `jJAnam→jjhAnam→jYAnam ✗`, `GYanam→ghJanam→RYanam ✗`.
- The fixed self-test battery happens to avoid every broken cluster ⇒ false-green. Any word with dh/gh/jh/ṅ/ṇ/jñ — i.e. much of Sanskrit — corrupts through HK.
- Minor documented quirk: bare ASCII input is assumed HK-shaped, so sloppy IAST-without-diacritics ("krsna") silently keys wrong. Acceptable if documented at call sites.

## Layer 6 — Catalog (`public/data/catalog.json`) ⚠️ minor fixes

| Check | Status |
|---|---|
| Entry correctness | 1 author / 1 work; URN, ids, `files[]` paths all resolve ✓; `unitCount:700` matches file ✓ |
| Author name Title Case | "Vyāsa (trad.)" ✓ |
| Dual-name convention | **Not applied** — no Devanagari companion (e.g. "Vyāsa (व्यास)") unlike the Greek-reader convention; translator stored as free-text string inside the work rather than structured like the trans file |
| Consistency | Translation block says **Arnold 1885** while `trans/bhagavadgita.json` says **Telang 1882** — must be reconciled when the Telang build lands |
| Adjacent UI copy (not data, but sign-off visible) | `src/home.ts` subtitle still reads "*interlinear reading environment for Ancient Greek — Homer to Plutarch… Morpheus, LSJ*" and starter links point at Greek TLG routes absent from this catalog |

---

## Top issues (ranked)

1. **Gloss join broken for core vocabulary** — karman missing; yoga/atman/dharma store junk/wrong senses; 77 % of MW headwords dropped by the k2-slash filter; 100 % of glosses carry leading page-number noise. Fix `build_glosses.py` (prefer k1, drop only truly malformed keys, strip `<L>/<pc>` noise, pick first real sense) — highest reader-visible impact.
2. **Morph shards stale** — rebuilding from existing `analysis.json` lifts BhG coverage 59.5 % → ~76 % (≈84 % with MW-prefix pass) with zero code changes; also clears `kim/tat/idam`-class misses.
3. **Translation layer empty** — Telang build pending; catalog must flip Arnold→Telang; watch the raw-HTML leak seen in the old dist Arnold units.
4. **sanscript HK pivot lossy** on dh/gh/jh/ṇ/ṅ/jñ (self-test passes vacuously) — fix before any consumer relies on HK keys or user HK input.
5. Minor: 37 `;`-contaminated morph keys; 6 `-` lemma placeholders; home-page copy still Greek.

## Coverage scoreboard

| Layer | Coverage | Production-ready? |
|---|---|---|
| Texts | 700/700 verses (100 %), 8,474 tokens, encoding clean | **Yes** |
| Morphology | 59.5 % reader-visible (would be ~76–84 % after rebuild) | **No — rebuild + fallback tuning** |
| Glosses | 40,869 entries but 0/4 probe core lemmas usable | **No — builder fix required** |
| Translation | 0/700 units | No — in progress |
| sanscript | 3 of 4 schemes verified lossless; HK lossy | Partial |
| Catalog | Structurally correct, translator mismatch | Near — needs sync |
