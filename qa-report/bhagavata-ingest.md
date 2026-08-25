# Bhāgavata Purāṇa ingest QA (2026-08-25)

- Source: GRETIL corpustei plaintext sa_bhAgavatapurANa.txt (CC BY-NC-SA 4.0, input U. Stiehl, legacy bhp1-12u.htm), curl 200 2.24MB. NOTE: curriculum-gaps.md's "separate -10 file" is stale → 404; single file covers all 12 cantos.
- Output: texts/purana/bhagavata-01..12.json, TEXT-ONLY works (no PD English, no Chinese trans exists) → catalog `"translation": null`, no translationZh. Refs `S.C.V` verse-level; units ≤60w split w/ letter suffixes; Devanagari tokens via sanscript IAST→DEVA.
- Units per canto: S1 813, S2 391, S3 1391, S4 1446, S5 662, S6 851, S7 749, S8 932, S9 964, **S10 3936**, S11 1366, S12 565 = **14,066**.
- Validation: refs unique+monotone ✓, all tokens Devanagari ✓, JSON round-trip ✓, parts ≤1.28MB (≤8MB cap) ✓, chapters per skandha = vulgate 19/10/33/31/26/19/15/24/24/90/31/13 ✓.
- Anchors: 1.1.1 जन्माद्यस्य…धीमहि ✓; Govardhan 10.25 ✓; rāsa 10.33 ✓; Kāliya 10.16–17 ✓; colophon श्रीमद् भागवतं पुराणम् अमलं at 12.13.18 ✓.
- Anomaly A: 30 refs occur twice with DIFFERENT text (recension-style variants: 3.32.22–43 two runs, 4.29.46/47+76/77, 5.26.2, 7.9.47, 8.8.3, 9.10.20). Policy keep-LAST — matches known vulgate at 4.29.46–47 & 7.9.47 and yields contiguous 3.32.1–43; orphan-only tail 3.32.44–48 kept as unique refs.
- Anomaly B: 842 verses carry doubled first halves (a,b,a,b,c,d data-entry artifact) → collapsed to a,b,c,d (verified vs vulgate on 1.1.2/1.1.3/2.7.2).
- Builder (untracked): .bhg-work/build_bhagavata.py; source cache .cache-corpus/purana/.
