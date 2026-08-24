# Research: PD Sanskrit→English translation sources + Perseus Smyth anchors

*Verified 2026-08-24 by a research subagent. All URLs below were fetched and confirmed unless explicitly marked otherwise.*

---

## Goal 1 — Public-domain English translations for ingestion

### 0. Landscape correction (important)

The prompt conflates two different sources:

| Source | Translator | Covers | Where |
|---|---|---|---|
| **SBE vol. 1** (1879) | Max Müller | Chāndogya ("Khândogya"), Kena ("Talavakâra"), Aitareya-Āraṇyaka, Kauṣītaki, Vājasaneya-Saṃhitā (= Īśā) | sacred-texts.com/hin/sbe01/ |
| **SBE vol. 15** (1884) | Max Müller | Katha, Mundaka, Taittirīyaka, **Bṛhadāraṇyaka**, Śvetāśvatara, Praśna, Maitrāyaṇa | sacred-texts.com/hin/sbe15/ |
| **Hume** (1921, OUP) | Robert Ernest Hume | All 13 principal Upaniṣads in one volume | archive.org scans |

Both are US public domain (pre-1930 publication). Hume is *not* on sacred-texts (except one stray page, sbe15098.htm "VI,4: Hume Translation").

### Fetch-route facts (apply to ALL sacred-texts.com URLs)

- **Direct programmatic fetch is blocked**: `curl` returns **403** even with full browser UA/Accept headers (Cloudflare TLS-fingerprint/bot challenge). Python requests will hit the same wall.
- **Working routes (both verified)**:
  1. **Wayback Machine** — repo convention already (`build_translation.py`): `http://web.archive.org/web/{ts}id_/{original}` with `curl --compressed`. Availability-API confirmed status-200 snapshots exist for e.g. `/hin/rigveda/rv01001.htm` (2025-01-22) and `/hin/sbe15/sbe15010.htm` (2025-02-28); snapshot body matched live text ("I Laud Agni…"). Caveat: some `id_` captures are truncated (2446-byte headless capture seen once) — pick another timestamp or use the non-`id_` render if truncated.
  2. **archive.org raw text** for Hume (below).
- **Encoding**: pages declare `<META charset="UTF-8">`; diacritics are numeric HTML entities (`&#257;`=ā, `&#7751;`=ṇ, `&#347;`=ṣ) → plain `html.unescape`.
- **Attribution line printed on every text page** (use this as the license/byline to reproduce):
  - RV: *"Rig Veda*, tr. by Ralph T.H. Griffith, [1896], at sacred-texts.com"
  - SBE15: *"The Upanishads, Part 2 (SBE15)*, by Max Müller, [1879], at sacred-texts.com"
  - SBE01 analogous. Site-wide meta: `copyright = "Public Domain and Creative Commons"`.

---

### 1. Katha Upaniṣad — ✅ VERIFIED

**Primary (chapter-level, clean HTML): SBE15**
- TOC: https://sacred-texts.com/hin/sbe15/index.htm (HTTP 200)
- Katha khaṇḍas = `sbe15010.htm`–`sbe15015.htm`, labelled I,1 / I,2 / I,3 / II,4 / II,5 / II,6 (Müller's vallī labelling — map carefully: his "II,4" is Adhyāya II Vallī 1).
- Verified `sbe15010.htm` (200, real English): verses numbered `1.` `2.` … inline at paragraph starts → regex `^(\d+)\.` per extracted paragraph is reliable. Footnotes collected at end keyed `page:note` (e.g. `1:1`) and referenced by superscript markers in prose.

**Secondary (single-file bulk): Hume 1921 on archive.org**
- Item: `in.ernet.dli.2015.149196` (1921 scan; metadata API confirms title/date).
- Raw text (⚠️ **non-standard filename**, not `{id}_djvu.txt`):
  `https://archive.org/download/in.ernet.dli.2015.149196/2015.149196.The-Thirteen-Principal-Upanishads_djvu.txt`
  → HTTP 200 after redirect; contains English (Chāndogya running headers found ~line 11.6k). Caveats: 1921-scan OCR noise (e.g. `H.4`, `a-]` artifacts, mangled diacritics) and archive.org rate-limits bursts — ingest with backoff. Other 1921 scans exist (`in.ernet.dli.2015.283814`, `ThirteenPrincipalUpanishadsByRobertErnestHume_201610`, …) as fallbacks.

### 2. Bṛhadāraṇyaka + Chāndogya — ✅ VERIFIED (one gap flagged)

**Chāndogya — SBE01, per-khaṇḍa granularity (ideal):**
- Full href map extracted from `hin/sbe01/index.htm`: Chāndogya = `sbe01022.htm` (I,1) → `sbe01175.htm` (VIII,15), sequential, every adhyāya/khanda present (154 pages).
- Kena = `sbe01176`–`sbe01179`; Īśā = `sbe01243`. Whole-volume plain text also linked: `sbe01.txt.gz` (linked from index; download itself untested because of CF block — pull it via Wayback).
- Khanda-level alignment to GRETIL ChUp files is trivial (same adhyāya/khanda units).

**Bṛhadāraṇyaka — SBE15, `sbe15053.htm`–`sbe15099.htm`:**
- ⚠️ **TOC skips I,3 entirely** (jumps I,2 → I,4) — either an etext omission or merged page; must inspect before relying on ST for BU. Also note quirk page `sbe15098.htm` = "VI,4: Hume Translation" (ST spliced in Hume for that khanda).
- Safer bulk path for BU: **Hume djvu.txt above** (complete BU incl. I,3) or spot-check `sbe15054.htm`/`sbe15055.htm` content for missing I,3.

### 3. Ṛgveda (Griffith) — ✅ VERIFIED, best alignment of the three

- **URL pattern CONFIRMED, one page per hymn**: `https://sacred-texts.com/hin/rigveda/rv{MM}{HHH}.htm` (mandala 2-digit, hymn 3-digit zero-padded).
  - `rv01001.htm` → "HYMN I. Agni. / 1 I Laud Agni, the chosen Priest…" ✓ 200
  - `rv10191.htm` → "HYMN CXCI" (RV 10.191, last hymn) ✓ 200 — boundary check passes.
- Book index pages: `rvi01.htm`…; each hymn page cross-links the Sanskrit (`../rvsan/rv01002.htm`).
- **Alignment verdict: EXACT hymn-level alignment with GRETIL pada files is feasible.** Repo's `.cache-corpus/sa_RgvedasaMhitApadapATha.txt` references verses as `rv_{M},{H}.{V}` (e.g. `rv_1,1.1`) → `rv_{M:02d}{H:03d}.htm` maps 1:1 per hymn. Verse-level: Griffith's etext prints verse numbers as leading digits inside one big `<p>` (lines separated by `<br>`); extract main `<p>` after the green attribution line, strip tags, split on digit-runs (`(?:^|\s)(\d{1,2})\s+`). Digit collisions are rare (Griffith spells most numerals as words) but alignment should be monotonic-with-lexicon-score like `build_translation.py` does, since some hymns merge/split verses differently than GRETIL.
- License line to print: *"Rig Veda*, tr. by Ralph T.H. Griffith, [1896], at sacred-texts.com" (+ translation is PD, 1889–92 ed.).

---

## Goal 2 — Smyth grammar section anchors (Perseus)

Work: Herbert Weir Smyth, *A Greek Grammar for Colleges* (1920), Perseus doc id `Perseus:text:1999.04.0007`.

### ✅ VERIFIED template for programmatic "Smyth §N" links

```
https://www.perseus.tufts.edu/hopper/text?doc=Perseus%3Atext%3A1999.04.0007%3Asmythp%3D{N}
```

where `{N}` = printed Smyth paragraph number (no `%A7`, just the integer).

Evidence (live fetches):
- `…:smythp=302` → HTTP 200, body contains "**302.** The vocative of all participles is the same as the nominative."
- `…:smythp=1000` → HTTP 200, body contains "**1000.** Plural.—The plural of proper names, of materials, and of abstracts…" (NB: §1000 is noun-syntax, not verb morphology — verb inflection lives ~§§355–680, syntax of the verb ~§§1685ff.; build the feature→§ table accordingly)
- `…:smythp=1481` → HTTP 200 ✓
- Page title renders as "… chapter {N}"; the requested paragraph appears first in the content pane.

### Invalid schemes (all 302-redirect to `invalidquery.jsp` — do NOT generate these)

`:id={N}`, `:section={N}`, `:subsection={N}`, `:chunk=…` → rejected.

Hierarchical scheme DOES work but its levels are internal outline units, **not** printed §s:
`…:part=2:chapter=19:section=53[:subsection=k]` → 200 with real content (verified). Use only if you ever need chapter-level landing pages. There are 5 parts (I Letters/Sounds/Accent, II Inflection, III Word-Formation, IV Syntax, Appendix verb list).

### Reliability / CORS / hotlink notes

- **Flaky host**: perseus.tufts.edu intermittently timed out during this session (transient transport errors, then success). Links are fine; anything server-side fetching Perseus needs retries/backoff.
- **CORS**: irrelevant — we only link out (`<a target="_blank">`); hopper sets no CORS headers but none are needed. No hotlink protection encountered for ordinary GETs; avoid iframing their pages.
- **Stable fallback mirrors** (static / alternate hosts):
  - Digital Smyth — http://neelsmith.github.io/smyth/ — static GitHub Pages edition derived from the Perseus XML, explicitly designed for *flat citation by printed § number* (good source for building the morph-feature→§ lookup table).
  - Chicago Philologic mirror — `perseus.uchicago.edu` (`NewPerseusMonographs.9`).
  - Wayback also archives hopper pages.
- **Attribution line to print** (appears on hopper pages): "American Book Company, 1920. The National Endowment for the Humanities provided support for entering this text." → credit: Smyth, *A Greek Grammar for Colleges*, American Book Company, 1920, via the Perseus Digital Library (`Perseus:text:1999.04.0007`).

---

## Verdict summary

| Target | Source | Status | Granularity | Machine-fetch |
|---|---|---|---|---|
| Katha | SBE15 `sbe15010–15` (Müller) | ✅ 200, English verified | khaṇḍa pages, `N.` verse markers | Wayback only (CF blocks direct) |
| Katha/all 13 UP | Hume 1921 djvu.txt @ archive.org | ✅ 200, OCR noise | continuous text | direct OK w/ backoff; non-standard filename |
| Chāndogya | SBE01 `sbe01022–1175` | ✅ mapped from index hrefs | per-khaṇḍa (perfect) | Wayback |
| Bṛhadāraṇyaka | SBE15 `sbe15053–99` | ⚠️ I,3 missing from TOC | per-khaṇḍa | Wayback; prefer Hume for full coverage |
| Ṛgveda | ST `rv{MM}{HHH}.htm` (Griffith) | ✅ incl. 10.191 boundary | **per-hymn** | Wayback; hymn #s == GRETIL `rv_M,H.V` → exact alignment |
| Smyth §N | hopper `:smythp={N}` | ✅ 302/1000/1481 verified | per printed § | link-out only; host flaky → consider mirror fallback |

### Blockers / action items

1. **No true blockers.** Biggest operational fact: sacred-texts.com 403s all non-browser clients → all ST ingestion must go through Wayback snapshots (`web.archive.org/web/{ts}id_/…`) exactly like `pipeline/build_translation.py` already does.
2. Resolve **Bṛhadāraṇyaka I,3** gap (check `sbe15054.htm` tail / `sbe01055.htm`; else use Hume for BU).
3. Hume djvu.txt = OCR quality (diacritics/numerals garbled); fine for gist-aligned interlinear, not for typographic fidelity.
4. Build a small **morph-feature → Smyth §** table manually (case uses §§334ff./1480ff., tense/mood ~§§400s–600s forms & §§1685ff. syntax, concord §§950ff. etc.); the *link mechanism* itself is solved (`smythp=`).
5. archive.org rate-limits rapid ranged downloads — batch with sleeps.
