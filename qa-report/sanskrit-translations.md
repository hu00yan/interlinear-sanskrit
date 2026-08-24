# Sanskrit translation-acquisition QA report

Lane: translation acquisition (Upaniṣads + Ṛgveda), 2026-08-24.
Files owned/emitted under this lane: `public/data/trans/{10 upanishad workIds}.json`,
`public/data/trans/rigveda-mandala1.json`, `public/data/trans/REF-NOTES.md`,
cache dirs `.cache-trans-upan/`, `.cache-trans-rv/` (gitignored).

## Upaniṣads — Hume 1921 (Deliverable A) ✅

Source: Robert Ernest Hume, *The Thirteen Principal Upanishads*, OUP 1921 (US PD),
archive.org item `in.ernet.dli.2015.283814` (`2015.283814.The-Thirteen_djvu.txt`;
cleaner OCR than the primary-suggested `in.ernet.dli.2015.149196`).
Extractor kept at `.cache-trans-upan/extract_upan.py`.

| workId | units | notes |
|---|---|---|
| isa | 17 | v11 lost (unreadable OCR number); vāsyam line verified |
| kena | 21 | khandas derived from Hume continuous numbering 1–34 |
| katha | 111 | all 6 vallīs |
| prasna | 53 | Q1v1 missing (OCR-garbled number) |
| mundaka | 59 | Hume prints THREE muṇḍakas (old division) |
| mandukya | 12 | complete |
| aitareya | 23 | Hume layout A1=K1–3, A2=K4, A3=K5; Kaushītaki excluded |
| taittiriya | 25 | sparsest — much of TU unnumbered prose in Hume |
| brhadaranyaka | 274 | some brāhmaṇa headings OCR-lost → verse drift within them |
| chandogya | 292 | **prapāṭhaka 5 absent** (khanda headings destroyed by OCR); dropped not mis-filed |

Total 887 units, all files valid JSON, header fields exact per spec
(`translator` Robert Ernest Hume / `year` 1921 / `license` Public domain /
`alignment` loose). Ref schemes + remap contract documented in
`public/data/trans/REF-NOTES.md`. Spot-checks pass: isa 1 "By the Lord enveloped…",
MaU 7, MuU 3.1.1 "Two birds", KaU 1.1, CU 6.2.x sat-only narrative.

## Ṛgveda Māṇḍala 1 — Griffith (Deliverable B) ✅ COMPLETION NOTE

- Hymn count verified against GRETIL pada source `.cache-corpus/sa_RgvedasaMhitApadapATha.txt`
  (refs run `rv_1,1.` … `rv_1,191.`) → **191 hymns**; matches sacred-texts index page.
- Fetched via Wayback `{ts}id_/https://sacred-texts.com/hin/rigveda/rv01HHH.htm`,
  timestamps tried in order 2024 → 20230101 → 2019 → latest-redirect; ~1/s politeness;
  pages cached in `.cache-trans-rv/pages_m1/` (crawler `.cache-trans-rv/fetch_rv.py`).
  Truncated captures (<1600 B or without attribution line) rejected and retried on
  another timestamp; head-block/footer nav chrome stripped from extraction.
- Result: **191/191 hymns fetched, 0 failures**, refs contiguous `1.1`…`1.191`,
  no empty/short units, chrome/entities leaks: none.
- Header fields: workId `rigveda-mandala1`, translator Ralph T.H. Griffith,
  year 1889, license Public domain, alignment loose. Hymn-level alignment to GRETIL
  pada files is exact by construction (same numbering).
- Spot-check: RV 1.1 opens "HYMN I. Agni. 1 I Laud Agni, the chosen Priest, God,
  minister of sacrifice…" — note Griffith's sacred-texts rendering is "I **Laud**
  Agni" (= agnim īḷe), not "Agni I invoke"; semantics verified against the famous
  opening. Last hymn 1.191 non-empty (2497 chars).
- File size: 348,456 bytes.
