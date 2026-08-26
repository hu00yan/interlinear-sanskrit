# QA: ref-marker / apparatus cleanup in words[] + permanent gate — 2026-08-26
**Verdict:** 21,239 tokens cleaned across 39 files — **11,571 removed** (ref-markers, standalone numbers, bracketed annotations), **9,668 repaired in place** (`<b>` strips niddesa/patisambhida; RV page-anchor strips rescue trailing words; `āsī3t`→`āsīt`; editorial brackets), refs/text untouched; **1 unit dropped** (kamasutra 2.7.6, was only markers). Epics/darshana/BhG/upanishads verified clean (Mbh_/Ram_ never leaked). Stems verified vs `.cache-corpus` sources (`Lal`×1515≈1,514 `लल्`; `KSak/Panc/Hit/BharSt/MSpv`) + lotus-keys.md (`Saddhp`); no false positives — legit `तत्/ह्य्/मनु` kept. Evidence: `qa-report/logs/refmarker-gate.json`.
| work | junk tokens | units dropped |
|---|---|---|
| pali mahaniddesa·culaniddesa·patisambhidamagga·petakopadesa | 9,997 (mostly `<b>…</b>`) | 0 |
| pali abhidhamma ×9 (ya/patthana×3/vb/ds/dt/pp/kv) | 6,671 (verse nos., `[Savipāka—5]`) | 0 |
| lalitavistara | 1,514 (`लल्` ← `{Lal_n.nn}`) | 0 |
| other pali ×8 (jataka/apadana/milinda/netti/vv/bv/petav/pj) | 1,256 | 0 |
| saddharmapundarika | 1,230 (`सद्ध्प्` ← `{Saddhp_n.nn}`) | 0 |
| shastra ×5 (pancatantra/hitopadesa/kamasutra/arthasastra/tantrakhyayika) | 280 | 1 |
| gandavyuha 248 · kavya ×5 36 (`क्सक्_n`·`भर्स्त्_n`·`म्स्प्व्_n`) · rigveda+maitri 8 | 292 | 0 |
**Gate live:** `pipeline/stages/90-qa/check_words_clean.py`, wired into worker.py post-tokenize — dirty artifact aborts chain before align/gloss/emit/publish (fail-loud); negative test exits 1. Pilots re-ran clean end-to-end: `pali-dn` ok 1.27s, `bhagavata` ok 5.55s; non-migrated builders covered by standalone corpus PASS (114 files). **Lotus morph impact** (lotus-keys.md method): strict hits ≈36,899 unchanged, occurrences 45,780→44,550 after −1,230 marker tokens → client-equivalent strict rate **80.6% → ~82.8%** (+2.2pp; residuals now genuinely linguistic: BHS forms, ch19–27 DCS gap).
