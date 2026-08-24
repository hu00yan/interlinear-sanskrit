# trans/REF-NOTES.md — reference-scheme contract notes

Written by the translation-acquisition lane, 2026-08-24.
`pipeline/build_upanishads.py` did not exist yet when these files were emitted
(texts builder still running), so refs below are this lane's best sequential
scheme derived from the GRETIL Sanskrit sources cached in `.cache-corpus/upanishad-*`
and from Hume's own print structure. The collector should remap via the rules here.

## Source of all ten Upaniṣad files
- Robert Ernest Hume, *The Thirteen Principal Upanishads*, Oxford University Press, 1921 (US public domain).
- Text: archive.org item `in.ernet.dli.2015.283814`, file `2015.283814.The-Thirteen_djvu.txt` (OCR).
  Cached locally at `.cache-trans-upan/hume283814.txt`; extractor `.cache-trans-upan/extract_upan.py`.
- `alignment` is `"loose"` by design: OCR noise remains (stray footnote fragments,
  garbled diacritics like `{zsa}` = īśa), and some verses merged into neighbours
  when their printed number was OCR-mangled.

## Ref schemes emitted (`<section>.<verse>` dotted, arabic)

| workId | ref shape | levels |
|---|---|---|
| isa | `N` | flat verse 1–18 (Kāṇva). Verse 11 missing (OCR of its number unreadable). |
| kena | `K.N` | K = khanda 1–4 **derived from Hume's continuous numbering**: Kh1=vv1–8, Kh2=9–13, Kh3=14–25, Kh4=26–34 (his khanda headings print only First/Second/Fourth; Third's heading is OCR-lost but the boundary vv are certain from his per-khanda parentheticals `(1)…`). |
| katha | `V.N` | V = vallī 1–6, N = Hume's printed verse within vallī (restarts per vallī). |
| prasna | `Q.N` | Q = praśna 1–6. Q1 verse 1 (the list of questioners) is missing — its number is OCR-garbled; text partially present in no unit. |
| mundaka | `M.K.N` | M = muṇḍaka 1–3 (**Hume prints THREE muṇḍakas** — old division; GRETIL may use two: M3 = GRETIL M2.2), K = khanda within, N = verse. |
| mandukya | `N` | flat 1–12, complete. |
| aitareya | `A.K.N` | A/K follow **Hume's layout** exactly: adhyāya 1 = khaṇḍas 1–3 (= Ār.II), adhyāya 2 = khaṇḍa 4, adhyāya 3 = khaṇḍa 5 (khaṇḍas numbered continuously across adhyāyas). Kaushītaki (which follows in Hume's volume) deliberately excluded. |
| taittiriya | `V.N.M` | V = vallī 1–3, N = anuvāka, M = Hume's printed section-verse. **Sparsest file (25 units)**: much of Taittirīya is unnumbered prose in Hume; whole anuvākas produced no anchored unit and their content was dropped rather than mis-attributed. Expect heavy remapping or re-extraction for TU. |
| brhadaranyaka | `A.B.N` | A = adhyāya 1–6, B = brāhmaṇa (Mādhyandina counts: 6/6/9/6/14/5), N = printed verse. Some B headings OCR-lost → those units sit under the previous B with shifted N; sections detected: see file. |
| chandogya | `P.K.N` | P = prapāṭhaka 1–8, K = khanda (canonical counts 12/24/19/17/24/16/26/15), N = printed verse. **P5 (5.1–5.24) is entirely missing** — its khanda headings did not survive OCR; units were dropped instead of mis-filed. |

## Known gaps / quirks (for the remapper)
- Verse numbers are Hume's *printed* numbers read through OCR; occasional digit
  misreads (`g.`→9, `I.` roman handled, split `1 1 .`→`11.` repaired) mean a few
  refs drift ±1 against critical editions.
- Units are deduplicated on exact ref; where a verse number repeated due to a
  footnote false-positive, only the first occurrence is kept.
- Famous-line spot checks that PASS: isa 1 ("By the Lord enveloped must this all be"),
  MaU 7 (fourth pāda description), MuU 3.1.1 ("Two birds…"), KaU 1.1 (Vājaśravasa),
  CU 6.2.2ff (sat-evom), BU 4.3–4.5 (Yājñavalkya dialogues).

## Ṛgveda files (this lane)
- `rigveda-mandala1.json` (and mandala2 if present): translator Ralph T.H. Griffith,
  sacred-texts.com `hin/rigveda/rv{MM}{HHH}.htm` fetched via Wayback
  (`https://web.archive.org/web/2024id_/<url>`), one unit per hymn,
  ref = `M.H` matching GRETIL pada files' hymn numbering exactly.
